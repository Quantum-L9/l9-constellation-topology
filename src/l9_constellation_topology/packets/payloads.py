"""Canonical topology payload serialization shared by compiler and validator."""

from __future__ import annotations

from l9_constellation_topology.domain import TopologyState
from l9_constellation_topology.run.evidence import artifact_hash, canonical_bytes

TOPOLOGY_PAYLOAD_FIELDS: tuple[str, ...] = (
    "repository_records",
    "artifact_records",
    "capability_records",
    "semantic_claims",
    "edge_records",
    "flow_records",
    "graph_records",
    "risks",
    "maturity",
    "impact_indexes",
    "evidence",
    "diagnostics",
    "unknowns",
    "conflicts",
)


def topology_payload_path(field: str) -> str:
    if field not in TOPOLOGY_PAYLOAD_FIELDS:
        raise ValueError(f"unsupported topology payload field: {field}")
    return f"payload/{field.replace('_', '-')}.json"


def topology_payload_bytes(state: TopologyState) -> dict[str, bytes]:
    return {
        field: canonical_bytes(getattr(state, field)) + b"\n" for field in TOPOLOGY_PAYLOAD_FIELDS
    }


def topology_payload_refs() -> dict[str, str]:
    return {field: topology_payload_path(field) for field in TOPOLOGY_PAYLOAD_FIELDS}


def topology_payload_hashes(state: TopologyState) -> dict[str, str]:
    return {
        field: artifact_hash(content) for field, content in topology_payload_bytes(state).items()
    }
