"""Build explicit information-flow projections from canonical edges."""

from __future__ import annotations

from l9_constellation_topology.domain import EdgeRecord, EdgeType, FlowRecord
from l9_constellation_topology.run import stable_id


def build_flows(edges: tuple[EdgeRecord, ...]) -> tuple[FlowRecord, ...]:
    flows: list[FlowRecord] = []
    for edge in edges:
        if edge.edge_type != EdgeType.depends_on:
            continue
        identity = {
            "source": edge.source_id,
            "target": edge.target_id,
            "type": "repository-dependency",
        }
        flows.append(
            FlowRecord(
                flow_id=stable_id("flow", identity),
                name=f"{edge.source_id} depends on {edge.target_id}",
                source_id=edge.source_id,
                target_id=edge.target_id,
                flow_type="repository-dependency",
                description="Repository dependency flow derived from canonical dependency evidence.",
                stage_sequence=(edge.source_id, edge.target_id),
                evidence_refs=edge.evidence_refs,
                confidence=edge.confidence,
            )
        )
    return tuple(sorted(flows, key=lambda item: item.flow_id))
