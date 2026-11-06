"""Shared builders for tests that reconcile repository-model assertions into claims."""

from __future__ import annotations

from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.packets.assertion_evidence import (
    assertion_evidence_record,
    assertion_semantic_inputs,
)
from l9_constellation_topology.packets.repository_model import (
    RepositoryModelAssertion,
    RepositoryModelPacket,
    RepositoryModelPayload,
)
from l9_constellation_topology.stages.reconcile_assertions import run as reconcile_assertions


def reconciled_state(
    assertions: tuple[RepositoryModelAssertion, ...],
    *,
    repository_id: str = "repo:sample",
) -> TopologyState:
    """Reconcile ``assertions`` from a fixture packet into claims, evidence and findings."""
    packet = RepositoryModelPacket(
        packet_version="1.1.0",
        packet_id="packet:fixture",
        subject={"repository_id": repository_id},
        source_snapshot={"revision": "git:" + "0" * 40, "semantic_hash": "sha256:" + "b" * 64},
        validation={"status": "passed"},
        producer={"name": "fixture-producer", "version": "1.0.0"},
        profile={"id": "p", "version": "1.0.0", "hash": "sha256:" + "c" * 64},
        schema_hash="sha256:" + "d" * 64,
        semantic_hash="sha256:" + "e" * 64,
        payload=RepositoryModelPayload(assertions=assertions),
    )
    evidence = tuple(assertion_evidence_record(a, packet=packet) for a in assertions)
    claims, conflicts, unknowns, _ = reconcile_assertions(
        assertion_semantic_inputs(assertions), evidence
    )
    return TopologyState(
        semantic_claims=claims, evidence=evidence, conflicts=conflicts, unknowns=unknowns
    )
