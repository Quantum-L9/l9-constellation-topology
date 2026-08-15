"""Deterministic lowering of canonical topology facts to memory intents.

Lowering reads a validated ``TopologyState`` and produces destination-neutral
``memory.ingest`` intents. It never mutates topology state, never resolves a
destination, and never performs an effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from l9_constellation_topology.domain.assessment import ConflictRecord, UnknownRecord
from l9_constellation_topology.domain.capability import CapabilityRecord
from l9_constellation_topology.domain.confidence import ConfidenceAssessment
from l9_constellation_topology.domain.edge import EdgeRecord
from l9_constellation_topology.domain.repository import RepositoryRecord
from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.packets.topology_packet import TopologyPacket
from l9_constellation_topology.run.evidence import EvidenceRecord

from .contracts import (
    DERIVATION_EVIDENCE_KINDS,
    EVIDENCE_REQUIRING_METHODS,
    CandidateKind,
    ConfidenceMethodName,
    EvidenceKindName,
    LoweringReceipt,
    MemoryAssertion,
    MemoryConfidence,
    MemoryEvidenceRef,
    MemoryIngestIntent,
    MemoryProvenance,
    MemoryWriteRequest,
)
from .identity import bare_digest, candidate_id, candidate_identity, idempotency_key
from .policy import PublicationPolicy

ENTITY_EXTRACTION_METHOD = "topology-entity-aggregation"
RELATIONSHIP_EXTRACTION_METHOD = "topology-relationship-compilation"
PUBLICATION_TOOL = "l9-constellation-topology/publication"


class LoweringError(ValueError):
    """Raised when a topology fact cannot be lowered under the active policy."""


@dataclass(frozen=True)
class LoweredCandidate:
    """A lowered fact awaiting an eligibility decision."""

    candidate_kind: CandidateKind
    source_topology_entity_ids: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    intent: MemoryIngestIntent
    receipt: LoweringReceipt
    identity: dict[str, Any]
    candidate_id: str
    idempotency_key: str
    has_resolved_evidence: bool
    requires_evidence: bool


@dataclass(frozen=True)
class TopologyIndex:
    """Pre-computed lookups over a topology state."""

    evidence_by_id: dict[str, EvidenceRecord]
    conflicts_by_subject: dict[str, tuple[ConflictRecord, ...]]
    unknowns_by_subject: dict[str, tuple[UnknownRecord, ...]]
    owning_repository_by_entity: dict[str, str]

    @classmethod
    def build(cls, state: TopologyState) -> TopologyIndex:
        conflicts: dict[str, list[ConflictRecord]] = {}
        for conflict in state.conflicts:
            conflicts.setdefault(conflict.subject_id, []).append(conflict)
        unknowns: dict[str, list[UnknownRecord]] = {}
        for unknown in state.unknowns:
            unknowns.setdefault(unknown.subject_id, []).append(unknown)
        owning: dict[str, str] = {}
        for repository in state.repository_records:
            owning[repository.repository_id] = repository.repository_id
            for entity_id in (*repository.artifact_ids, *repository.capability_ids):
                owning.setdefault(entity_id, repository.repository_id)
        return cls(
            evidence_by_id={record.evidence_id: record for record in state.evidence},
            conflicts_by_subject={
                key: tuple(sorted(value, key=lambda item: item.conflict_id))
                for key, value in conflicts.items()
            },
            unknowns_by_subject={
                key: tuple(sorted(value, key=lambda item: item.unknown_id))
                for key, value in unknowns.items()
            },
            owning_repository_by_entity=owning,
        )


def _namespace(policy: PublicationPolicy, owning_repository_id: str | None) -> str:
    scope = "unscoped"
    if owning_repository_id:
        scope = owning_repository_id.split(":", 1)[-1] or "unscoped"
    namespace = f"{policy.namespace_root}/{scope}"
    return namespace[:300]


def _describe_list(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none observed"


def _confidence_score(policy: PublicationPolicy, assessment: ConfidenceAssessment) -> float:
    level = str(assessment.level)
    if level not in policy.confidence_score_by_level:
        raise LoweringError(f"publication policy has no confidence score for level {level!r}")
    conflict_status = str(assessment.conflict_status)
    if conflict_status not in policy.confidence_conflict_ceiling:
        raise LoweringError(
            f"publication policy has no conflict ceiling for status {conflict_status!r}"
        )
    score = min(
        policy.confidence_score_by_level[level],
        policy.confidence_conflict_ceiling[conflict_status],
    )
    return max(0.0, min(1.0, score))


def _confidence_method(
    policy: PublicationPolicy, assessment: ConfidenceAssessment
) -> ConfidenceMethodName:
    derivation = str(assessment.derivation_method)
    if derivation not in policy.confidence_method_by_derivation:
        raise LoweringError(
            f"publication policy has no confidence method for derivation {derivation!r}"
        )
    return policy.confidence_method_by_derivation[derivation]


def _source_trust(policy: PublicationPolicy, assessment: ConfidenceAssessment) -> float:
    authority = str(assessment.authority)
    trust = policy.source_trust_by_authority.get(authority)
    if trust is None:
        raise LoweringError(f"publication policy has no source trust for authority {authority!r}")
    return max(0.0, min(1.0, trust))


def _evidence_kind(policy: PublicationPolicy, record: EvidenceRecord) -> EvidenceKindName:
    evidence_class = str(record.evidence_class)
    if evidence_class not in policy.evidence_kind_by_class:
        raise LoweringError(f"publication policy has no evidence kind for class {evidence_class!r}")
    return policy.evidence_kind_by_class[evidence_class]


def _evidence_description(record: EvidenceRecord) -> str:
    subject = record.field or record.subject_id
    location = record.source_ref.source_path or record.source_ref.uri or record.source_ref.packet_id
    suffix = f" from {location}" if location else ""
    description = (
        f"Topology stage {record.stage} recorded {record.evidence_class} "
        f"{record.source_type} evidence for {subject}{suffix}."
    )
    return description[:2_000]


def _lower_evidence(
    *,
    policy: PublicationPolicy,
    index: TopologyIndex,
    evidence_refs: tuple[str, ...],
    published_at: datetime,
    required_method: ConfidenceMethodName,
    subject_id: str,
) -> tuple[tuple[MemoryEvidenceRef, ...], tuple[str, ...], int, EvidenceKindName | None]:
    """Lower topology evidence records into downstream evidence references."""
    resolved = tuple(
        sorted(
            (
                index.evidence_by_id[ref]
                for ref in set(evidence_refs)
                if ref in index.evidence_by_id
            ),
            key=lambda record: record.evidence_id,
        )
    )
    kept = resolved[: policy.maximum_evidence_refs_per_candidate]
    truncated = len(resolved) - len(kept)
    lowered = [
        MemoryEvidenceRef(
            kind=_evidence_kind(policy, record),
            description=_evidence_description(record),
            source_id=record.evidence_id[:500],
            source_digest=bare_digest(record.source_ref.content_hash),
            observed_at=published_at,
        )
        for record in kept
    ]

    derivation_kind: EvidenceKindName | None = None
    needs_derivation_evidence = (
        bool(resolved)
        and required_method in EVIDENCE_REQUIRING_METHODS
        and not any(item.kind in DERIVATION_EVIDENCE_KINDS for item in lowered)
    )
    if needs_derivation_evidence:
        derivation_kind = "aggregation" if required_method == "aggregated" else "inference"
        lowered.append(
            MemoryEvidenceRef(
                kind=derivation_kind,
                description=(
                    f"Topology compiler derived this fact for {subject_id} by "
                    f"{required_method} reconciliation over "
                    f"{len(resolved)} evidence record(s)."
                )[:2_000],
                source_id=subject_id[:500],
                observed_at=published_at,
            )
        )
    return (
        tuple(lowered),
        tuple(record.evidence_id for record in resolved),
        truncated,
        derivation_kind,
    )


def _provenance(
    *,
    policy: PublicationPolicy,
    packet: TopologyPacket,
    assessment: ConfidenceAssessment,
    owning_repository_id: str | None,
    extraction_method: str,
    published_at: datetime,
) -> MemoryProvenance:
    return MemoryProvenance(
        source=packet.producer.name[:200],
        source_id=packet.packet_id[:500],
        source_digest=bare_digest(packet.semantic_hash),
        source_agent_id=f"{packet.producer.name}/{packet.producer.version}"[:200],
        repository=(owning_repository_id or None),
        tool=PUBLICATION_TOOL,
        extraction_method=extraction_method,
        source_trust=_source_trust(policy, assessment),
        transformed_at=published_at,
    )


def _metadata(
    *,
    packet: TopologyPacket,
    entity_ids: tuple[str, ...],
    candidate_kind: CandidateKind,
    policy: PublicationPolicy,
    conflicts: tuple[ConflictRecord, ...],
    unknowns: tuple[UnknownRecord, ...],
) -> dict[str, Any]:
    return {
        "topology_packet_id": packet.packet_id,
        "topology_semantic_hash": packet.semantic_hash,
        "topology_entity_ids": list(entity_ids),
        "repository_model_packet_ids": [
            ref.packet_id for ref in packet.inputs.repository_model_packets
        ],
        "candidate_kind": candidate_kind,
        "publication_policy": policy.identity,
        "observed_conflict_ids": [item.conflict_id for item in conflicts],
        "observed_unknown_ids": [item.unknown_id for item in unknowns],
    }


def _build(
    *,
    policy: PublicationPolicy,
    packet: TopologyPacket,
    index: TopologyIndex,
    candidate_kind: CandidateKind,
    entity_ids: tuple[str, ...],
    subject_id: str,
    content: str,
    assertion: MemoryAssertion | None,
    assessment: ConfidenceAssessment,
    evidence_refs: tuple[str, ...],
    source_fields: tuple[str, ...],
    extraction_method: str,
    published_at: datetime,
) -> LoweredCandidate:
    owning_repository_id = index.owning_repository_by_entity.get(subject_id)
    namespace = _namespace(policy, owning_repository_id)
    memory_class = (
        policy.entity_memory_class
        if candidate_kind == "entity"
        else policy.relationship_memory_class
    )
    method = _confidence_method(policy, assessment)
    lowered_evidence, resolved_ids, truncated, derivation_kind = _lower_evidence(
        policy=policy,
        index=index,
        evidence_refs=evidence_refs,
        published_at=published_at,
        required_method=method,
        subject_id=subject_id,
    )
    conflicts = index.conflicts_by_subject.get(subject_id, ())
    unknowns = index.unknowns_by_subject.get(subject_id, ())

    identity = candidate_identity(
        candidate_kind=candidate_kind,
        namespace=namespace,
        memory_class=memory_class,
        content=content,
        assertion=assertion.model_dump(mode="json") if assertion is not None else None,
        source_topology_entity_ids=entity_ids,
    )
    request = MemoryWriteRequest(
        namespace=namespace,
        memory_class=memory_class,
        content=content[:64_000],
        assertion=assertion,
        provenance=_provenance(
            policy=policy,
            packet=packet,
            assessment=assessment,
            owning_repository_id=owning_repository_id,
            extraction_method=extraction_method,
            published_at=published_at,
        ),
        evidence=lowered_evidence,
        confidence=MemoryConfidence(
            score=_confidence_score(policy, assessment),
            method=method,
            evidence_count=len(lowered_evidence),
            policy_version=policy.confidence_policy_version,
            calibrated_at=published_at,
        ),
        valid_from=published_at,
        tags=("l9-topology", f"topology-{candidate_kind}"),
        metadata=_metadata(
            packet=packet,
            entity_ids=entity_ids,
            candidate_kind=candidate_kind,
            policy=policy,
            conflicts=conflicts,
            unknowns=unknowns,
        ),
        idempotency_key=idempotency_key(
            identity,
            topology_semantic_hash=packet.semantic_hash,
            policy_hash=policy.policy_hash(),
        ),
    )
    key = request.idempotency_key
    if key is None:
        raise LoweringError("lowered intent is missing a deterministic idempotency key")
    return LoweredCandidate(
        candidate_kind=candidate_kind,
        source_topology_entity_ids=entity_ids,
        source_evidence_ids=resolved_ids,
        intent=MemoryIngestIntent(request=request),
        receipt=LoweringReceipt(
            source_fields=source_fields,
            resolved_evidence_ids=resolved_ids,
            truncated_evidence_count=truncated,
            derivation_evidence_kind=derivation_kind,
            confidence_level=str(assessment.level),
            confidence_method=method,
            conflict_status=str(assessment.conflict_status),
            observed_conflict_ids=tuple(item.conflict_id for item in conflicts),
            observed_unknown_ids=tuple(item.unknown_id for item in unknowns),
            owning_repository_id=owning_repository_id,
        ),
        identity=identity,
        candidate_id=candidate_id(identity),
        idempotency_key=key,
        has_resolved_evidence=bool(resolved_ids),
        requires_evidence=method in EVIDENCE_REQUIRING_METHODS,
    )


def lower_repository(
    record: RepositoryRecord,
    *,
    policy: PublicationPolicy,
    packet: TopologyPacket,
    index: TopologyIndex,
    published_at: datetime,
) -> LoweredCandidate:
    """Lower a repository record into a durable-memory observation."""
    content = (
        f"Repository {record.name} ({record.repository_id}) has primary role "
        f"{record.primary_role} at source revision {record.source_revision}. "
        f"Languages: {_describe_list(record.languages)}. "
        f"Package managers: {_describe_list(record.package_managers)}."
    )
    return _build(
        policy=policy,
        packet=packet,
        index=index,
        candidate_kind="entity",
        entity_ids=(record.repository_id,),
        subject_id=record.repository_id,
        content=content,
        assertion=None,
        assessment=record.confidence,
        evidence_refs=record.evidence_refs,
        source_fields=(
            "name",
            "repository_id",
            "primary_role",
            "source_revision",
            "languages",
            "package_managers",
        ),
        extraction_method=ENTITY_EXTRACTION_METHOD,
        published_at=published_at,
    )


def lower_capability(
    record: CapabilityRecord,
    *,
    policy: PublicationPolicy,
    packet: TopologyPacket,
    index: TopologyIndex,
    published_at: datetime,
) -> LoweredCandidate:
    """Lower a capability record into a durable-memory observation."""
    content = (
        f"Capability {record.name} ({record.capability_id}): {record.description} "
        f"Implemented by: {_describe_list(record.implemented_by)}. "
        f"Exposed by: {_describe_list(record.exposed_by)}."
    )
    return _build(
        policy=policy,
        packet=packet,
        index=index,
        candidate_kind="entity",
        entity_ids=(record.capability_id,),
        subject_id=record.capability_id,
        content=content,
        assertion=None,
        assessment=record.confidence,
        evidence_refs=record.evidence_refs,
        source_fields=(
            "capability_id",
            "name",
            "description",
            "implemented_by",
            "exposed_by",
        ),
        extraction_method=ENTITY_EXTRACTION_METHOD,
        published_at=published_at,
    )


def lower_relationship(
    record: EdgeRecord,
    *,
    policy: PublicationPolicy,
    packet: TopologyPacket,
    index: TopologyIndex,
    published_at: datetime,
) -> LoweredCandidate:
    """Lower a topology edge into a structured memory assertion."""
    predicate = str(record.edge_type)
    content = (
        f"Topology relationship: {record.source_id} {predicate} {record.target_id} "
        f"(direction {record.direction})."
    )
    assertion = MemoryAssertion(
        subject=record.source_id[:500],
        predicate=predicate[:200],
        object=record.target_id[:2_000],
    )
    if not assertion.is_structured:
        raise LoweringError(f"edge {record.edge_id} does not provide a structured assertion")
    return _build(
        policy=policy,
        packet=packet,
        index=index,
        candidate_kind="relationship",
        entity_ids=(record.source_id, record.target_id),
        subject_id=record.source_id,
        content=content,
        assertion=assertion,
        assessment=record.confidence,
        evidence_refs=record.evidence_refs,
        source_fields=("source_id", "edge_type", "target_id", "direction"),
        extraction_method=RELATIONSHIP_EXTRACTION_METHOD,
        published_at=published_at,
    )
