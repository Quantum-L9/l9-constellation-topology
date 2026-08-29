"""Deterministic lowering of canonical topology facts to memory intents.

Lowering reads a validated ``TopologyState`` and produces destination-neutral
``memory.ingest`` intents. It never mutates topology state, never resolves a
destination, and never performs an effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import TypeAdapter

from l9_constellation_topology.domain.assessment import ConflictRecord, UnknownRecord
from l9_constellation_topology.domain.capability import CapabilityRecord
from l9_constellation_topology.domain.claim import SemanticClaimRecord
from l9_constellation_topology.domain.confidence import ConfidenceAssessment
from l9_constellation_topology.domain.edge import EdgeRecord
from l9_constellation_topology.domain.repository import RepositoryRecord
from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.packets.topology_packet import TopologyPacket
from l9_constellation_topology.run.evidence import EvidenceRecord, canonical_data

from .contracts import (
    DERIVATION_EVIDENCE_KINDS,
    EVIDENCE_REQUIRING_METHODS,
    LOWERING_CONTRACT_VERSION,
    MEMORY_INGEST_OPERATION,
    CandidateKind,
    ConfidenceMethodName,
    EvidenceKindName,
    LoweringReceipt,
    MemoryAssertion,
    MemoryConfidence,
    MemoryEvidenceRef,
    MemoryIngestIntent,
    MemoryProvenance,
    MemorySourceLocator,
    MemoryWriteRequest,
)
from .identity import (
    IDEMPOTENCY_ALGORITHM_VERSION,
    bare_digest,
    candidate_id,
    candidate_identity,
    confidence_semantics,
    evidence_semantics,
    idempotency_key,
)
from .policy import PublicationPolicy

#: Validates a mirrored locator payload against the discriminated union.
_LOCATOR_ADAPTER: TypeAdapter[MemorySourceLocator] = TypeAdapter(MemorySourceLocator)

ENTITY_EXTRACTION_METHOD = "topology-entity-aggregation"
RELATIONSHIP_EXTRACTION_METHOD = "topology-relationship-compilation"
CLAIM_EXTRACTION_METHOD = "repository-model-assertion-reconciliation"
PUBLICATION_TOOL = "l9-constellation-topology/publication"


class LoweringError(ValueError):
    """Raised when a topology fact cannot be lowered under the active policy."""


@dataclass(frozen=True)
class AssertionProvenance:
    """Where a lowered fact came from in the repository-model assertion domain.

    Grouped rather than passed as three more parameters: only claim lowering
    supplies any of them, and they always travel together.
    """

    source_assertion_ids: tuple[str, ...] = ()
    predicate: str | None = None
    #: Registry classification of the predicate. ``unsupported`` is what holds
    #: such a candidate, so it is recorded rather than inferred downstream.
    support: str | None = None


#: The absence of assertion provenance, for facts not lowered from an assertion.
NO_ASSERTION_PROVENANCE = AssertionProvenance()


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


def _lower_locator(record: EvidenceRecord) -> MemorySourceLocator | None:
    """Carry the structured coordinate this evidence was read at, if any.

    Translated field-for-field rather than passed through: the two unions are
    separate contracts that happen to agree, and a mirror that forwarded the
    producer's object would silently export whatever this repository added to it
    next. ``None`` stays ``None`` — evidence that carries only a line number has
    no structured coordinate to state, and inventing one is the failure the
    locator union exists to prevent.
    """
    locator = record.source_ref.locator
    if locator is None:
        return None
    return _LOCATOR_ADAPTER.validate_python(locator.model_dump(mode="json"))


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
) -> tuple[
    tuple[MemoryEvidenceRef, ...],
    tuple[str, ...],
    int,
    EvidenceKindName | None,
    tuple[EvidenceRecord, ...],
]:
    """Lower topology evidence records into downstream evidence references.

    The kept topology records are returned alongside the lowered refs because
    effect identity needs what the downstream ``EvidenceRef`` contract has no
    field for: the source path the evidence was read at. Recomputing it from the
    lowered ref is impossible, and keying on the topology evidence id instead
    would bind the effect to the repository revision, which is exactly the
    coupling v3 removes.
    """
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
            source_locator=_lower_locator(record),
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
        kept,
    )


def _local_evidence_semantics(
    policy: PublicationPolicy,
    kept: tuple[EvidenceRecord, ...],
) -> tuple[dict[str, Any], ...]:
    """Return the evidence this write rests on, in snapshot-independent terms."""
    return tuple(
        evidence_semantics(
            evidence_kind=str(_evidence_kind(policy, record)),
            source_content_digest=bare_digest(record.source_ref.content_hash),
            # The path, never the packet id or repository revision: the same file
            # at the same content is the same support for the claim regardless of
            # which commit it was read at.
            stable_source_locator=record.source_ref.source_path or record.source_ref.uri,
        )
        for record in kept
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


def _source_locators(
    *,
    policy: PublicationPolicy,
    index: TopologyIndex,
    evidence_refs: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Collect the repository revisions and paths the evidence was observed at.

    The downstream `EvidenceRef` contract is frozen and forbids extra fields, so it has
    nowhere to carry either locator; today they survive only inside prose descriptions.
    Lowering them into request metadata keeps a published record able to state which
    commit it was true at without resolving its parent packet out of band.
    """
    revisions: set[str] = set()
    paths: set[str] = set()
    for ref in set(evidence_refs):
        record = index.evidence_by_id.get(ref)
        if record is None:
            continue
        if record.source_ref.source_revision:
            revisions.add(record.source_ref.source_revision)
        if record.source_ref.source_path:
            paths.add(record.source_ref.source_path)
    bound = policy.maximum_evidence_refs_per_candidate
    return tuple(sorted(revisions)), tuple(sorted(paths))[:bound]


def _metadata(
    *,
    packet: TopologyPacket,
    entity_ids: tuple[str, ...],
    candidate_kind: CandidateKind,
    policy: PublicationPolicy,
    conflicts: tuple[ConflictRecord, ...],
    unknowns: tuple[UnknownRecord, ...],
    source_revisions: tuple[str, ...],
    source_paths: tuple[str, ...],
    publication_candidate_id: str,
    source_assertion_ids: tuple[str, ...],
    assertion_predicate: str | None,
    relation: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "topology_packet_id": packet.packet_id,
        "topology_semantic_hash": packet.semantic_hash,
        "topology_entity_ids": list(entity_ids),
        "repository_model_packet_ids": [
            ref.packet_id for ref in packet.inputs.repository_model_packets
        ],
        "candidate_kind": candidate_kind,
        "publication_policy": policy.identity,
        # The snapshot hashes above are provenance. These name the algorithm
        # that produced this effect's identity, so a reader can tell which
        # keying rules a published record was admitted under.
        "idempotency_algorithm_version": IDEMPOTENCY_ALGORITHM_VERSION,
        "lowering_contract_version": LOWERING_CONTRACT_VERSION,
        "observed_conflict_ids": [item.conflict_id for item in conflicts],
        "observed_unknown_ids": [item.unknown_id for item in unknowns],
        "source_revisions": list(source_revisions),
        "source_paths": list(source_paths),
        # Names the logical fact rather than this particular write, so a later
        # execution layer can correlate successive operations on one fact and
        # resolve supersession against durable state. Topology does not fabricate
        # downstream record identities, so ``MemoryWriteRequest.supersedes`` stays
        # empty: a new effect key means "a new operation", not "replace record X".
        "publication_candidate_id": publication_candidate_id,
        "source_assertion_ids": list(source_assertion_ids),
        "assertion_predicate": assertion_predicate,
    }
    if relation is not None:
        # Namespaced under one topology-owned key rather than spread across the
        # flat metadata, so a downstream reader can tell what this repository
        # asserted about the edge from what it asserted about the snapshot.
        metadata["topology_relation"] = relation
    return metadata


def _build(
    *,
    policy: PublicationPolicy,
    packet: TopologyPacket,
    index: TopologyIndex,
    candidate_kind: CandidateKind,
    entity_ids: tuple[str, ...],
    content: str,
    assertion: MemoryAssertion | None,
    assessment: ConfidenceAssessment,
    evidence_refs: tuple[str, ...],
    source_fields: tuple[str, ...],
    extraction_method: str,
    published_at: datetime,
    provenance: AssertionProvenance = NO_ASSERTION_PROVENANCE,
    relation: dict[str, Any] | None = None,
) -> LoweredCandidate:
    # The subject is the first entity the fact was lowered from, in every kind:
    # a repository, a capability, a relationship's source, a claim's subject.
    # It used to be a second parameter that callers had to keep in agreement with
    # this one, which nothing enforced.
    if not entity_ids:
        raise LoweringError("a lowered fact must name at least one topology entity")
    subject_id = entity_ids[0]
    owning_repository_id = index.owning_repository_by_entity.get(subject_id)
    namespace = _namespace(policy, owning_repository_id)
    memory_class = {
        "entity": policy.entity_memory_class,
        "relationship": policy.relationship_memory_class,
        "claim": policy.claim_memory_class,
    }[candidate_kind]
    method = _confidence_method(policy, assessment)
    lowered_evidence, resolved_ids, truncated, derivation_kind, kept_evidence = _lower_evidence(
        policy=policy,
        index=index,
        evidence_refs=evidence_refs,
        published_at=published_at,
        required_method=method,
        subject_id=subject_id,
    )
    conflicts = index.conflicts_by_subject.get(subject_id, ())
    unknowns = index.unknowns_by_subject.get(subject_id, ())
    source_revisions, source_paths = _source_locators(
        policy=policy,
        index=index,
        evidence_refs=evidence_refs,
    )

    identity = candidate_identity(
        operation=MEMORY_INGEST_OPERATION,
        candidate_kind=candidate_kind,
        namespace=namespace,
        memory_class=memory_class,
        content=content,
        assertion=assertion.model_dump(mode="json") if assertion is not None else None,
        source_topology_entity_ids=entity_ids,
    )
    confidence = MemoryConfidence(
        score=_confidence_score(policy, assessment),
        method=method,
        evidence_count=len(lowered_evidence),
        policy_version=policy.confidence_policy_version,
        calibrated_at=published_at,
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
        confidence=confidence,
        valid_from=published_at,
        tags=("l9-topology", f"topology-{candidate_kind}"),
        metadata=_metadata(
            packet=packet,
            entity_ids=entity_ids,
            candidate_kind=candidate_kind,
            policy=policy,
            conflicts=conflicts,
            unknowns=unknowns,
            source_revisions=source_revisions,
            source_paths=source_paths,
            publication_candidate_id=candidate_id(identity),
            source_assertion_ids=provenance.source_assertion_ids,
            assertion_predicate=provenance.predicate,
            relation=relation,
        ),
        idempotency_key=idempotency_key(
            identity,
            lowering_contract_version=LOWERING_CONTRACT_VERSION,
            local_evidence=_local_evidence_semantics(policy, kept_evidence),
            confidence=confidence_semantics(
                score=confidence.score,
                method=str(confidence.method),
                evidence_count=confidence.evidence_count,
                confidence_policy_version=confidence.policy_version,
            ),
            derivation_kind=str(derivation_kind) if derivation_kind is not None else None,
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
            source_assertion_ids=provenance.source_assertion_ids,
            assertion_predicate=provenance.predicate,
            predicate_support=provenance.support,
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


def relation_metadata(record: EdgeRecord) -> dict[str, Any]:
    """Return the structured facts about an edge that prose cannot carry.

    ``direction`` and ``properties`` used to survive only inside the human
    ``content`` string, or not at all. That was worst for the one edge type
    whose whole meaning is in its properties: a ``DUPLICATE_OF`` edge carries
    the cluster it belongs to, the content hash both endpoints share, the method
    that decided the relation, the cluster size, and an explicit statement that
    the star's centre is arbitrary. Published without them it read as a
    directional relation between two files, with no cluster, nothing to
    re-check, and no sign that picking that centre meant nothing.

    The endpoints are repeated here even though the assertion carries them: an
    assertion is a triple, and a reader resolving a symmetric relation needs to
    know the triple's order was imposed rather than observed.
    """
    return {
        "edge_id": record.edge_id,
        "edge_type": str(record.edge_type),
        "source_id": record.source_id,
        "target_id": record.target_id,
        "direction": str(record.direction),
        "properties": canonical_data(record.properties),
    }


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
        content=content,
        assertion=assertion,
        assessment=record.confidence,
        evidence_refs=record.evidence_refs,
        source_fields=("source_id", "edge_type", "target_id", "direction"),
        extraction_method=RELATIONSHIP_EXTRACTION_METHOD,
        published_at=published_at,
        relation=relation_metadata(record),
    )


def lower_semantic_claim(
    record: SemanticClaimRecord,
    *,
    policy: PublicationPolicy,
    packet: TopologyPacket,
    index: TopologyIndex,
    published_at: datetime,
) -> LoweredCandidate:
    """Lower a reconciled semantic claim into a structured memory assertion.

    The downstream assertion is the claim verbatim — subject, predicate, object —
    so a claim publishes as the triple it is even when no richer graph projection
    exists for its predicate. The prose ``content`` restates the same triple and
    adds nothing to it: a reader of the content alone learns exactly what the
    assertion says, and no more.
    """
    assertion = MemoryAssertion(
        subject=record.subject_id[:500],
        predicate=record.predicate[:200],
        object=record.object[:2_000],
    )
    if not assertion.is_structured:
        raise LoweringError(f"claim {record.claim_id} does not provide a structured assertion")
    content = (
        f"Repository-model assertion: {record.subject_id} {record.predicate} {record.object}. "
        f"Cardinality {record.cardinality}; registry support {record.support}; "
        f"conflict status {record.conflict_status}."
    )
    return _build(
        policy=policy,
        packet=packet,
        index=index,
        candidate_kind="claim",
        # The subject is the only topology entity a claim is guaranteed to
        # resolve. A claim's object is frequently an external name, and naming it
        # as a topology entity would assert a membership that was never observed.
        entity_ids=(record.subject_id,),
        content=content,
        assertion=assertion,
        assessment=record.confidence,
        evidence_refs=record.evidence_refs,
        # The predicate is a source field, so a conflict or unknown recorded
        # against that predicate is material to exactly this claim and not to
        # unrelated facts about the same repository.
        source_fields=("subject_id", "predicate", "object", record.predicate),
        extraction_method=CLAIM_EXTRACTION_METHOD,
        published_at=published_at,
        provenance=AssertionProvenance(
            source_assertion_ids=record.source_assertion_ids,
            predicate=record.predicate,
            support=record.support,
        ),
    )
