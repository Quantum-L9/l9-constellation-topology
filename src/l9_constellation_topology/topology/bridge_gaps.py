"""Pure bridge-gap projection from canonical topology records.

This module does not scan repositories, inspect live control planes, activate a
feature, dispatch an effect, or decide that a dormant capability should be
enabled. It reports only lifecycle transitions that the supplied topology can
prove are missing, then keeps operator intent explicit so optional or prohibited
capabilities are not misreported as work.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Literal

from l9_constellation_topology.domain import (
    ActivationIntent,
    BridgeDisposition,
    BridgeGapProjection,
    BridgeGapRecord,
    BridgeGapType,
    BridgeLifecycleState,
    CapabilityRecord,
    ConfidenceAssessment,
    EdgeRecord,
    EdgeType,
    TopologyState,
)
from l9_constellation_topology.run import semantic_hash, stable_id

BRIDGE_GAP_POLICY_ID = "l9.bridge-gap-policy"
BRIDGE_GAP_POLICY_VERSION = "1.0.0"


def bridge_gap_policy_view() -> dict[str, object]:
    """Return the exact deterministic rules applied by this projector."""

    return {
        "policy_id": BRIDGE_GAP_POLICY_ID,
        "policy_version": BRIDGE_GAP_POLICY_VERSION,
        "rules": {
            BridgeGapType.built_unreachable.value: {
                "subject_kind": "capability",
                "requires": ["IMPLEMENTS"],
                "missing_all": ["EXPOSES", "ROUTES_TO"],
                "expected_state": BridgeLifecycleState.exposed.value,
            },
            BridgeGapType.exposed_unconsumed.value: {
                "subject_kind": "capability",
                "requires_any": ["EXPOSES", "ROUTES_TO"],
                "missing": "CONSUMES",
                "expected_state": BridgeLifecycleState.consumed.value,
            },
            BridgeGapType.orphan_output.value: {
                "subject_kind": "output",
                "requires": ["PRODUCES"],
                "missing": "CONSUMES",
                "expected_state": BridgeLifecycleState.consumed.value,
            },
        },
        "precedence": [
            BridgeGapType.built_unreachable.value,
            BridgeGapType.exposed_unconsumed.value,
            BridgeGapType.orphan_output.value,
        ],
        "default_activation_intent": ActivationIntent.unknown.value,
        "effect_authority": "none",
    }


def bridge_gap_policy_hash() -> str:
    return semantic_hash(bridge_gap_policy_view())


def _disposition(intent: ActivationIntent) -> BridgeDisposition:
    if intent is ActivationIntent.required:
        return BridgeDisposition.action_required
    if intent in {ActivationIntent.optional, ActivationIntent.deferred}:
        return BridgeDisposition.intentional_dormancy
    if intent is ActivationIntent.prohibited:
        return BridgeDisposition.correctly_disconnected
    return BridgeDisposition.decision_required


def _recommended_action(gap_type: BridgeGapType, intent: ActivationIntent) -> str:
    if intent is ActivationIntent.prohibited:
        return "Preserve the disconnection and retain explicit prohibition evidence."
    if intent in {ActivationIntent.optional, ActivationIntent.deferred}:
        return "Record the intentional dormant state and avoid an activation claim."
    if intent is ActivationIntent.unknown:
        return "Assign activation intent before wiring, retiring, or promoting this subject."
    if gap_type is BridgeGapType.built_unreachable:
        return "Wire an existing entry surface to the capability and attach runtime proof."
    if gap_type is BridgeGapType.exposed_unconsumed:
        return "Bind a real consumer to the existing interface and prove the handoff."
    return "Bind a consumer to the produced output and prove boundary survival."


def _edges_by_endpoint(
    edges: tuple[EdgeRecord, ...],
) -> tuple[dict[str, tuple[EdgeRecord, ...]], dict[str, tuple[EdgeRecord, ...]]]:
    incoming: dict[str, list[EdgeRecord]] = defaultdict(list)
    outgoing: dict[str, list[EdgeRecord]] = defaultdict(list)
    for edge in edges:
        incoming[edge.target_id].append(edge)
        outgoing[edge.source_id].append(edge)
    return (
        {
            key: tuple(sorted(value, key=lambda item: item.edge_id))
            for key, value in incoming.items()
        },
        {
            key: tuple(sorted(value, key=lambda item: item.edge_id))
            for key, value in outgoing.items()
        },
    )


def _of_type(edges: tuple[EdgeRecord, ...], *edge_types: EdgeType) -> tuple[EdgeRecord, ...]:
    allowed = set(edge_types)
    return tuple(edge for edge in edges if edge.edge_type in allowed)


def _evidence(*groups: tuple[EdgeRecord, ...], direct: tuple[str, ...] = ()) -> tuple[str, ...]:
    refs = set(direct)
    for group in groups:
        for edge in group:
            refs.update(edge.evidence_refs)
    return tuple(sorted(refs))


def _confidence(
    *,
    edge_groups: tuple[tuple[EdgeRecord, ...], ...],
    direct_refs: tuple[str, ...] = (),
) -> ConfidenceAssessment:
    relation_count = sum(len(group) for group in edge_groups)
    evidence_count = len(_evidence(*edge_groups, direct=direct_refs))
    return ConfidenceAssessment.deterministic(
        corroborated=(relation_count > 1 or evidence_count > 1)
    )


def _declared_intents(state: TopologyState) -> dict[str, ActivationIntent]:
    intents: dict[str, ActivationIntent] = {}
    for record in state.graph_records:
        if record.record_type != "node":
            continue
        raw = record.properties.get("activation_intent")
        if not isinstance(raw, str):
            continue
        try:
            intents[record.entity_id] = ActivationIntent(raw.upper())
        except ValueError:
            # An unsupported value is not silently promoted into intent. The
            # subject remains UNKNOWN and therefore requires a decision.
            continue
    return intents


def _intent_for(
    subject_id: str,
    intent_by_subject: Mapping[str, ActivationIntent],
) -> ActivationIntent:
    return intent_by_subject.get(subject_id, ActivationIntent.unknown)


def _record(
    *,
    subject_id: str,
    subject_kind: Literal["capability", "output"],
    gap_type: BridgeGapType,
    observed_state: BridgeLifecycleState,
    expected_state: BridgeLifecycleState,
    intent: ActivationIntent,
    producer_ids: tuple[str, ...],
    consumer_ids: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    reason: str,
    confidence: ConfidenceAssessment,
) -> BridgeGapRecord:
    identity = {
        "policy_id": BRIDGE_GAP_POLICY_ID,
        "policy_version": BRIDGE_GAP_POLICY_VERSION,
        "subject_id": subject_id,
        "gap_type": gap_type.value,
    }
    return BridgeGapRecord(
        bridge_gap_id=stable_id("bridge-gap", identity),
        subject_id=subject_id,
        subject_kind=subject_kind,
        gap_type=gap_type,
        observed_state=observed_state,
        expected_state=expected_state,
        missing_transition=f"{observed_state.value}_TO_{expected_state.value}",
        activation_intent=intent,
        disposition=_disposition(intent),
        producer_ids=tuple(sorted(set(producer_ids))),
        consumer_ids=tuple(sorted(set(consumer_ids))),
        evidence_refs=evidence_refs,
        reason=reason,
        recommended_action=_recommended_action(gap_type, intent),
        confidence=confidence,
    )


def _capability_gap(
    capability: CapabilityRecord,
    *,
    incoming: dict[str, tuple[EdgeRecord, ...]],
    outgoing: dict[str, tuple[EdgeRecord, ...]],
    intent_by_subject: Mapping[str, ActivationIntent],
) -> BridgeGapRecord | None:
    incoming_edges = incoming.get(capability.capability_id, ())
    outgoing_edges = outgoing.get(capability.capability_id, ())
    implementation_edges = _of_type(incoming_edges, EdgeType.implements)
    validation_edges = _of_type(incoming_edges, EdgeType.validated_by)
    exposure_edges = _of_type(incoming_edges, EdgeType.exposes, EdgeType.routes_to)
    routed_edges = _of_type(outgoing_edges, EdgeType.routes_to)
    consumer_edges = _of_type(incoming_edges, EdgeType.consumes)

    implementers = tuple(
        sorted(
            set(capability.implemented_by)
            | {edge.source_id for edge in implementation_edges}
        )
    )
    validators = tuple(
        sorted(set(capability.validated_by) | {edge.source_id for edge in validation_edges})
    )
    exposers = tuple(
        sorted(
            set(capability.exposed_by)
            | {edge.source_id for edge in exposure_edges}
            | {edge.target_id for edge in routed_edges}
        )
    )
    consumers = tuple(sorted({edge.source_id for edge in consumer_edges}))
    intent = _intent_for(capability.capability_id, intent_by_subject)

    # A real consumer is stronger evidence than an absent intermediate EXPOSES
    # edge. Consumption proves the subject is reachable in the compiled
    # topology, so do not manufacture an earlier lifecycle gap merely because a
    # producer omitted a redundant exposure relation.
    if consumers:
        return None

    if implementers and not exposers:
        observed = (
            BridgeLifecycleState.validated if validators else BridgeLifecycleState.implemented
        )
        evidence_refs = _evidence(
            implementation_edges,
            validation_edges,
            direct=capability.evidence_refs,
        )
        return _record(
            subject_id=capability.capability_id,
            subject_kind="capability",
            gap_type=BridgeGapType.built_unreachable,
            observed_state=observed,
            expected_state=BridgeLifecycleState.exposed,
            intent=intent,
            producer_ids=implementers,
            consumer_ids=(),
            evidence_refs=evidence_refs,
            reason=(
                f"Capability has {len(implementers)} observed implementer(s)"
                + (f" and {len(validators)} validator(s)" if validators else "")
                + " but no EXPOSES or ROUTES_TO path."
            ),
            confidence=_confidence(
                edge_groups=(implementation_edges, validation_edges),
                direct_refs=capability.evidence_refs,
            ),
        )

    if exposers and not consumers:
        evidence_refs = _evidence(
            exposure_edges,
            routed_edges,
            direct=capability.evidence_refs,
        )
        return _record(
            subject_id=capability.capability_id,
            subject_kind="capability",
            gap_type=BridgeGapType.exposed_unconsumed,
            observed_state=BridgeLifecycleState.exposed,
            expected_state=BridgeLifecycleState.consumed,
            intent=intent,
            producer_ids=implementers or exposers,
            consumer_ids=(),
            evidence_refs=evidence_refs,
            reason=(
                f"Capability has {len(exposers)} observed exposure or route path(s) "
                "but no CONSUMES edge."
            ),
            confidence=_confidence(
                edge_groups=(exposure_edges, routed_edges),
                direct_refs=capability.evidence_refs,
            ),
        )
    return None


def _output_gaps(
    state: TopologyState,
    *,
    incoming: dict[str, tuple[EdgeRecord, ...]],
    intent_by_subject: Mapping[str, ActivationIntent],
    excluded_subject_ids: set[str],
) -> tuple[BridgeGapRecord, ...]:
    capability_ids = {item.capability_id for item in state.capability_records}
    records: list[BridgeGapRecord] = []
    for subject_id in sorted(incoming):
        if subject_id in capability_ids or subject_id in excluded_subject_ids:
            continue
        incoming_edges = incoming[subject_id]
        producer_edges = _of_type(incoming_edges, EdgeType.produces)
        if not producer_edges:
            continue
        consumer_edges = _of_type(incoming_edges, EdgeType.consumes)
        if consumer_edges:
            continue
        producers = tuple(sorted({edge.source_id for edge in producer_edges}))
        intent = _intent_for(subject_id, intent_by_subject)
        evidence_refs = _evidence(producer_edges)
        records.append(
            _record(
                subject_id=subject_id,
                subject_kind="output",
                gap_type=BridgeGapType.orphan_output,
                observed_state=BridgeLifecycleState.produced,
                expected_state=BridgeLifecycleState.consumed,
                intent=intent,
                producer_ids=producers,
                consumer_ids=(),
                evidence_refs=evidence_refs,
                reason=(
                    f"Output has {len(producers)} observed producer(s) but no CONSUMES edge."
                ),
                confidence=_confidence(edge_groups=(producer_edges,)),
            )
        )
    return tuple(records)


def bridge_gap_projection_semantic_view(
    projection: BridgeGapProjection,
) -> dict[str, object]:
    return {
        "schema_version": projection.schema_version,
        "source_packet_id": projection.source_packet_id,
        "source_semantic_hash": projection.source_semantic_hash,
        "policy_id": projection.policy_id,
        "policy_version": projection.policy_version,
        "policy_hash": projection.policy_hash,
        "gaps": projection.gaps,
        "counts_by_type": projection.counts_by_type,
        "counts_by_disposition": projection.counts_by_disposition,
        "unknown_intent_count": projection.unknown_intent_count,
    }


def project_bridge_gaps(
    state: TopologyState,
    *,
    source_packet_id: str,
    source_semantic_hash: str,
    intent_by_subject: Mapping[str, ActivationIntent] | None = None,
) -> BridgeGapProjection:
    """Project provable missing transitions without deciding activation policy."""

    intents: dict[str, ActivationIntent] = _declared_intents(state)
    if intent_by_subject is not None:
        intents.update(intent_by_subject)
    incoming, outgoing = _edges_by_endpoint(state.edge_records)
    gaps: list[BridgeGapRecord] = []
    capability_gap_subjects: set[str] = set()

    for capability in sorted(state.capability_records, key=lambda item: item.capability_id):
        gap = _capability_gap(
            capability,
            incoming=incoming,
            outgoing=outgoing,
            intent_by_subject=intents,
        )
        if gap is not None:
            gaps.append(gap)
            capability_gap_subjects.add(gap.subject_id)

    gaps.extend(
        _output_gaps(
            state,
            incoming=incoming,
            intent_by_subject=intents,
            excluded_subject_ids=capability_gap_subjects,
        )
    )
    ordered = tuple(sorted(gaps, key=lambda item: (item.gap_type.value, item.subject_id)))
    by_type = Counter(item.gap_type.value for item in ordered)
    by_disposition = Counter(item.disposition.value for item in ordered)
    candidate = BridgeGapProjection(
        source_packet_id=source_packet_id,
        source_semantic_hash=source_semantic_hash,
        policy_id=BRIDGE_GAP_POLICY_ID,
        policy_version=BRIDGE_GAP_POLICY_VERSION,
        policy_hash=bridge_gap_policy_hash(),
        gaps=ordered,
        counts_by_type=dict(sorted(by_type.items())),
        counts_by_disposition=dict(sorted(by_disposition.items())),
        unknown_intent_count=sum(
            item.activation_intent is ActivationIntent.unknown for item in ordered
        ),
        semantic_hash="sha256:pending",
    )
    return candidate.model_copy(
        update={"semantic_hash": semantic_hash(bridge_gap_projection_semantic_view(candidate))}
    )
