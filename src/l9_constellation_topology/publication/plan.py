"""Deterministic publication plan construction.

A publication plan is derived from a validated Topology Packet. It is never an
alternate source of topology truth: it adds no facts, and every candidate cites
the topology entities, evidence, and Repository Model Packets it came from.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from l9_constellation_topology.domain.claim import SemanticClaimRecord
from l9_constellation_topology.packets.refs import PacketRef
from l9_constellation_topology.packets.topology_packet import (
    MaterializedTopology,
    TopologyPacket,
)
from l9_constellation_topology.run.evidence import utc_now

from .contracts import (
    PUBLICATION_PLAN_VERSION,
    PublicationCandidate,
    PublicationDiagnostic,
    PublicationPlan,
    SkippedCandidate,
)
from .eligibility import (
    SKIP_CANDIDATE_DOMAIN,
    SKIP_EDGE_TYPE,
    SKIP_ENTITY_KIND,
    SKIP_READINESS_DOMAIN,
    SKIP_REASONING_DOMAIN,
    SKIP_UNRESOLVED_WORK_TARGET,
    SKIP_UNSTATEABLE_CLAIM,
    EligibilityContext,
    decide,
    require_publishable_topology,
)
from .identity import plan_id, publication_semantic_hash
from .lowering import (
    LoweredCandidate,
    LoweringError,
    TopologyIndex,
    lower_capability,
    lower_relationship,
    lower_repository,
    lower_semantic_claim,
)
from .policy import PublicationPolicy, load_publication_policy

PUBLICATION_PRODUCER_SUFFIX = "publication"


def _topology_packet_ref(materialized: MaterializedTopology) -> PacketRef:
    packet = materialized.packet
    return PacketRef(
        packet_id=packet.packet_id,
        packet_type=packet.packet_type,
        packet_version=packet.packet_version,
        uri=f"packet://{packet.packet_id}",
        semantic_hash=packet.semantic_hash,
        artifact_hash=packet.artifact_hash,
        validation_status=packet.validation.status,
        subject_id=None,
        source_revision=None,
    )


def _plan_semantic_view(
    *,
    plan_version: str,
    producer_name: str,
    producer_version: str,
    packet_ref: PacketRef,
    topology_semantic_hash: str,
    policy_hash: str,
    candidates: tuple[PublicationCandidate, ...],
    skipped: tuple[SkippedCandidate, ...],
) -> dict[str, object]:
    return {
        "plan_type": "l9.topology-publication-plan",
        "plan_version": plan_version,
        "producer_name": producer_name,
        "producer_version": producer_version,
        "source_topology_packet_id": packet_ref.packet_id,
        "source_topology_semantic_hash": topology_semantic_hash,
        "policy_hash": policy_hash,
        "candidates": candidates,
        "skipped_candidates": skipped,
    }


def _to_candidate(lowered: LoweredCandidate, context: EligibilityContext) -> PublicationCandidate:
    return PublicationCandidate(
        candidate_id=lowered.candidate_id,
        candidate_kind=lowered.candidate_kind,
        source_topology_entity_ids=lowered.source_topology_entity_ids,
        source_evidence_ids=lowered.source_evidence_ids,
        source_repository_model_packet_ids=tuple(
            ref.packet_id for ref in context.packet.inputs.repository_model_packets
        ),
        eligibility=decide(lowered, context),
        lowering=lowered.receipt,
        memory_intent=lowered.intent,
        idempotency_key=lowered.idempotency_key,
    )


def _diagnostics(
    candidates: tuple[PublicationCandidate, ...],
    skipped: tuple[SkippedCandidate, ...],
) -> tuple[PublicationDiagnostic, ...]:
    status_counts: Counter[str] = Counter(str(item.eligibility.status) for item in candidates)
    reason_counts: Counter[str] = Counter()
    for candidate in candidates:
        reason_counts.update(candidate.eligibility.reasons)
    skip_counts = Counter(item.reason for item in skipped)
    truncated = sum(item.lowering.truncated_evidence_count for item in candidates)

    diagnostics = [
        PublicationDiagnostic(
            code=f"candidates.{status}",
            detail=f"Candidates with eligibility status {status}.",
            count=status_counts.get(status, 0),
        )
        for status in ("eligible", "held", "rejected")
    ]
    diagnostics.extend(
        PublicationDiagnostic(
            code=f"reason.{reason}",
            detail=f"Candidates carrying eligibility reason {reason}.",
            count=count,
        )
        for reason, count in sorted(reason_counts.items())
    )
    diagnostics.extend(
        PublicationDiagnostic(
            code=f"skipped.{reason}",
            detail=f"Topology facts the policy did not select: {reason}.",
            count=count,
        )
        for reason, count in sorted(skip_counts.items())
    )
    diagnostics.append(
        PublicationDiagnostic(
            code="evidence.truncated",
            detail="Evidence references dropped by the per-candidate policy ceiling.",
            count=truncated,
        )
    )
    return tuple(diagnostics)


def _lower_claims(
    claims: tuple[SemanticClaimRecord, ...],
    *,
    policy: PublicationPolicy,
    packet: TopologyPacket,
    index: TopologyIndex,
    published_at: datetime,
    selected: bool,
) -> tuple[list[LoweredCandidate], list[SkippedCandidate]]:
    """Lower semantic claims, recording rather than raising on the ones that cannot be."""
    lowered: list[LoweredCandidate] = []
    skipped: list[SkippedCandidate] = []
    for record in claims:
        if not selected:
            skipped.append(
                SkippedCandidate(
                    source_kind="claim", source_id=record.claim_id, reason=SKIP_ENTITY_KIND
                )
            )
            continue
        try:
            lowered.append(
                lower_semantic_claim(
                    record, policy=policy, packet=packet, index=index, published_at=published_at
                )
            )
        except LoweringError:
            # The claim survives in canonical topology either way; what cannot be
            # done is state it downstream as a subject/predicate/object.
            skipped.append(
                SkippedCandidate(
                    source_kind="claim",
                    source_id=record.claim_id,
                    reason=SKIP_UNSTATEABLE_CLAIM,
                )
            )
    return lowered, skipped


def build_publication_plan(
    materialized: MaterializedTopology,
    policy: PublicationPolicy,
    *,
    published_at: datetime | None = None,
) -> PublicationPlan:
    """Build a deterministic publication plan from validated topology truth."""
    packet = materialized.packet
    state = materialized.state
    require_publishable_topology(packet, policy)

    timestamp = published_at or utc_now()
    index = TopologyIndex.build(state)
    context = EligibilityContext.build(policy=policy, packet=packet, state=state, index=index)
    eligible_entity_kinds = set(policy.eligible_entity_kinds)
    eligible_edge_types = set(policy.eligible_edge_types)

    lowered: list[LoweredCandidate] = []
    skipped: list[SkippedCandidate] = []

    if "repository" in eligible_entity_kinds:
        lowered.extend(
            lower_repository(
                record, policy=policy, packet=packet, index=index, published_at=timestamp
            )
            for record in state.repository_records
        )
    else:
        skipped.extend(
            SkippedCandidate(
                source_kind="entity", source_id=record.repository_id, reason=SKIP_ENTITY_KIND
            )
            for record in state.repository_records
        )

    if "capability" in eligible_entity_kinds:
        lowered.extend(
            lower_capability(
                record, policy=policy, packet=packet, index=index, published_at=timestamp
            )
            for record in state.capability_records
        )
    else:
        skipped.extend(
            SkippedCandidate(
                source_kind="entity", source_id=record.capability_id, reason=SKIP_ENTITY_KIND
            )
            for record in state.capability_records
        )

    claim_lowered, claim_skipped = _lower_claims(
        state.semantic_claims,
        policy=policy,
        packet=packet,
        index=index,
        published_at=timestamp,
        selected="semantic_claim" in eligible_entity_kinds,
    )
    lowered.extend(claim_lowered)
    skipped.extend(claim_skipped)

    if "artifact" in eligible_entity_kinds:
        raise ValueError(
            "artifact entities have no supported memory lowering in publication policy v1"
        )
    skipped.extend(
        SkippedCandidate(
            source_kind="entity", source_id=record.artifact_id, reason=SKIP_ENTITY_KIND
        )
        for record in state.artifact_records
    )

    for edge in state.edge_records:
        if str(edge.edge_type) not in eligible_edge_types:
            skipped.append(
                SkippedCandidate(
                    source_kind="relationship", source_id=edge.edge_id, reason=SKIP_EDGE_TYPE
                )
            )
            continue
        # An explicit work relation publishes only when its target resolved to
        # exactly one observed artifact. An ambiguous or unresolved target still
        # produced a canonical edge — the declaration happened — but publishing
        # it would state a *resolved* relation downstream, and a consumer reading
        # only the assertion cannot tell that the endpoint was never observed.
        resolution = edge.properties.get("target_resolution")
        if resolution is not None and resolution != "exact-artifact":
            skipped.append(
                SkippedCandidate(
                    source_kind="relationship",
                    source_id=edge.edge_id,
                    reason=SKIP_UNRESOLVED_WORK_TARGET,
                )
            )
            continue
        lowered.append(
            lower_relationship(
                edge, policy=policy, packet=packet, index=index, published_at=timestamp
            )
        )

    # The non-canonical domains, recorded as held rather than left absent. None
    # of them has a lowering function and none can acquire one by accident: they
    # are enumerated here only so the plan states the containment it performs.
    skipped.extend(
        SkippedCandidate(
            source_kind="relationship",
            source_id=record.relation_id,
            reason=SKIP_CANDIDATE_DOMAIN,
        )
        for record in state.candidate_relations
    )
    skipped.extend(
        SkippedCandidate(
            source_kind="entity",
            source_id=record.candidate_id,
            reason=SKIP_CANDIDATE_DOMAIN,
        )
        for record in state.candidate_clusters
    )
    skipped.extend(
        SkippedCandidate(
            source_kind="entity",
            source_id=record.readiness_id,
            reason=SKIP_READINESS_DOMAIN,
        )
        for record in state.readiness_evidence
    )
    skipped.extend(
        SkippedCandidate(
            source_kind="entity",
            source_id=record.reasoning_candidate_id,
            reason=SKIP_REASONING_DOMAIN,
        )
        for record in state.topology_reasoning_candidates
    )

    candidates = tuple(
        sorted(
            (_to_candidate(item, context) for item in lowered),
            key=lambda item: item.candidate_id,
        )
    )
    skipped_candidates = tuple(sorted(skipped, key=lambda item: (item.source_kind, item.source_id)))
    diagnostics = _diagnostics(candidates, skipped_candidates)
    packet_ref = _topology_packet_ref(materialized)
    producer_name = f"{packet.producer.name}/{PUBLICATION_PRODUCER_SUFFIX}"
    digest = publication_semantic_hash(
        _plan_semantic_view(
            plan_version=PUBLICATION_PLAN_VERSION,
            producer_name=producer_name,
            producer_version=packet.producer.version,
            packet_ref=packet_ref,
            topology_semantic_hash=packet.semantic_hash,
            policy_hash=policy.policy_hash(),
            candidates=candidates,
            skipped=skipped_candidates,
        )
    )
    return PublicationPlan(
        plan_id=plan_id(digest),
        producer=packet.producer.model_copy(update={"name": producer_name}),
        source_topology_packet=packet_ref,
        source_topology_semantic_hash=packet.semantic_hash,
        policy=policy.raw(),
        policy_hash=policy.policy_hash(),
        candidates=candidates,
        skipped_candidates=skipped_candidates,
        diagnostics=diagnostics,
        semantic_hash=digest,
        published_at=timestamp,
    )


def plan_publication_from_repository(
    materialized: MaterializedTopology,
    repository_root: Path,
    *,
    published_at: datetime | None = None,
) -> PublicationPlan:
    """Resolve the checked-in publication policy and build a plan."""
    policy = load_publication_policy(repository_root)
    return build_publication_plan(materialized, policy, published_at=published_at)
