"""Canonical topology payload serialization shared by compiler and validator."""

from __future__ import annotations

from l9_constellation_topology.domain import TopologyState
from l9_constellation_topology.run.evidence import artifact_hash, canonical_bytes

#: Every payload domain, each serialized to its own file and its own hash.
#:
#: Order is the order a reader meets them: canonical records, then corpus scope,
#: then the explicitly non-canonical domains, then provenance. A domain's hash is
#: the hash of exactly the bytes written for it, so a change confined to one
#: domain moves one hash — which is what makes `payload_hashes` usable for
#: locating what changed rather than merely detecting that something did.
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
    "corpus_records",
    "root_records",
    "candidate_relations",
    "candidate_clusters",
    "readiness_evidence",
    "topology_reasoning_candidates",
    "evidence",
    "diagnostics",
    "unknowns",
    "conflicts",
)

#: Domains introduced by Topology Packet 1.1.0.
#:
#: A 1.0.0 bundle declares no payload ref for any of these, and the loader reads
#: an absent ref as an empty domain rather than as a missing file. That is what
#: lets a packet compiled before corpus intelligence existed still load, without
#: 1.1.0 having to pretend it emitted files it did not.
CORPUS_PAYLOAD_FIELDS: frozenset[str] = frozenset(
    {
        "corpus_records",
        "root_records",
        "candidate_relations",
        "candidate_clusters",
        "readiness_evidence",
        "topology_reasoning_candidates",
    }
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
