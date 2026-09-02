from __future__ import annotations

import json

from l9_constellation_topology.domain import (
    ActivationIntent,
    BridgeDisposition,
    BridgeGapType,
    CapabilityRecord,
    ConfidenceAssessment,
    Direction,
    EdgeRecord,
    EdgeType,
    GraphRecord,
    TopologyState,
)
from l9_constellation_topology.run import stable_id
from l9_constellation_topology.topology.bridge_gaps import project_bridge_gaps


def _edge(source: str, target: str, edge_type: EdgeType, evidence: str) -> EdgeRecord:
    return EdgeRecord(
        edge_id=stable_id(
            "edge",
            {"source": source, "target": target, "edge_type": edge_type.value},
        ),
        source_id=source,
        target_id=target,
        edge_type=edge_type,
        direction=Direction.outbound,
        evidence_refs=(evidence,),
        confidence=ConfidenceAssessment.direct(),
    )


def _project(
    state: TopologyState,
    intents: dict[str, ActivationIntent] | None = None,
):
    return project_bridge_gaps(
        state,
        source_packet_id="packet:topology",
        source_semantic_hash="sha256:topology",
        intent_by_subject=intents,
    )


def test_implemented_validated_but_unreachable_capability_is_reported() -> None:
    capability = CapabilityRecord(
        capability_id="capability:planner",
        name="planner",
        description="Plans work.",
        implemented_by=("artifact:planner",),
        validated_by=("artifact:test-planner",),
        evidence_refs=("evidence:capability",),
        confidence=ConfidenceAssessment.direct(),
    )
    projection = _project(TopologyState(capability_records=(capability,)))

    assert len(projection.gaps) == 1
    gap = projection.gaps[0]
    assert gap.gap_type is BridgeGapType.built_unreachable
    assert gap.missing_transition == "VALIDATED_TO_EXPOSED"
    assert gap.disposition is BridgeDisposition.decision_required
    assert gap.activation_intent is ActivationIntent.unknown


def test_exposed_capability_without_consumer_is_reported() -> None:
    capability = CapabilityRecord(
        capability_id="capability:api",
        name="api",
        description="Public API.",
        implemented_by=("artifact:api",),
        exposed_by=("interface:http",),
        confidence=ConfidenceAssessment.direct(),
    )
    projection = _project(TopologyState(capability_records=(capability,)))

    assert [gap.gap_type for gap in projection.gaps] == [
        BridgeGapType.exposed_unconsumed
    ]
    assert projection.gaps[0].missing_transition == "EXPOSED_TO_CONSUMED"


def test_real_consumer_closes_capability_and_output_gaps() -> None:
    capability = CapabilityRecord(
        capability_id="capability:api",
        name="api",
        description="Public API.",
        implemented_by=("artifact:api",),
        exposed_by=("interface:http",),
        confidence=ConfidenceAssessment.direct(),
    )
    state = TopologyState(
        capability_records=(capability,),
        edge_records=(
            _edge("repo:consumer", "capability:api", EdgeType.consumes, "evidence:consume-api"),
            _edge("repo:producer", "artifact:receipt", EdgeType.produces, "evidence:produce"),
            _edge("repo:consumer", "artifact:receipt", EdgeType.consumes, "evidence:consume"),
        ),
    )

    assert _project(state).gaps == ()



def test_direct_consumer_closes_earlier_reachability_gap() -> None:
    capability = CapabilityRecord(
        capability_id="capability:direct",
        name="direct",
        description="Consumed through a direct contract edge.",
        implemented_by=("artifact:direct",),
        confidence=ConfidenceAssessment.direct(),
    )
    state = TopologyState(
        capability_records=(capability,),
        edge_records=(
            _edge(
                "repo:consumer",
                capability.capability_id,
                EdgeType.consumes,
                "evidence:direct-consumer",
            ),
        ),
    )

    assert _project(state).gaps == ()

def test_produced_output_without_consumer_is_reported() -> None:
    state = TopologyState(
        edge_records=(
            _edge("repo:producer", "contract:handoff", EdgeType.produces, "evidence:produce"),
        )
    )
    projection = _project(state)

    assert len(projection.gaps) == 1
    gap = projection.gaps[0]
    assert gap.gap_type is BridgeGapType.orphan_output
    assert gap.subject_id == "contract:handoff"
    assert gap.producer_ids == ("repo:producer",)


def test_intent_changes_disposition_without_hiding_observed_state() -> None:
    capability = CapabilityRecord(
        capability_id="capability:optional-observability",
        name="optional-observability",
        description="Optional library.",
        implemented_by=("repo:observability",),
        evidence_refs=("evidence:library",),
        confidence=ConfidenceAssessment.direct(),
    )
    projection = _project(
        TopologyState(capability_records=(capability,)),
        {capability.capability_id: ActivationIntent.optional},
    )

    gap = projection.gaps[0]
    assert gap.gap_type is BridgeGapType.built_unreachable
    assert gap.activation_intent is ActivationIntent.optional
    assert gap.disposition is BridgeDisposition.intentional_dormancy
    assert projection.unknown_intent_count == 0


def test_graph_node_activation_intent_is_consumed_without_external_overlay() -> None:
    capability = CapabilityRecord(
        capability_id="capability:forbidden",
        name="forbidden",
        description="Must remain disconnected.",
        implemented_by=("repo:owner",),
        confidence=ConfidenceAssessment.direct(),
    )
    state = TopologyState(
        capability_records=(capability,),
        graph_records=(
            GraphRecord(
                record_type="node",
                label="Capability",
                entity_id=capability.capability_id,
                properties={"activation_intent": "PROHIBITED"},
                confidence=ConfidenceAssessment.direct(),
            ),
        ),
    )

    gap = _project(state).gaps[0]
    assert gap.activation_intent is ActivationIntent.prohibited
    assert gap.disposition is BridgeDisposition.correctly_disconnected


def test_projection_identity_is_deterministic_and_json_serializable() -> None:
    edges = (
        _edge("repo:z", "output:z", EdgeType.produces, "evidence:z"),
        _edge("repo:a", "output:a", EdgeType.produces, "evidence:a"),
    )
    first = _project(TopologyState(edge_records=edges))
    second = _project(TopologyState(edge_records=tuple(reversed(edges))))

    assert first == second
    assert [gap.subject_id for gap in first.gaps] == ["output:a", "output:z"]
    assert first.semantic_hash.startswith("sha256:")
    json.dumps(first.model_dump(mode="json"), sort_keys=True)
