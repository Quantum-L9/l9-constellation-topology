"""Memory-effect identity must be local to the fact, not to the snapshot.

A publication effect is a claim about a repository. A Topology Packet is a
snapshot that happens to carry many such claims. Under identity v1 the two were
conflated: every effect key mixed in the whole topology semantic hash, so a
semantic change anywhere re-keyed every effect in the plan and downstream
admitted unchanged facts as new ones.

These tests pin the separation. Global hashes stay on the intent as provenance,
where they belong, and stop deciding whether a fact is the same fact.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.packets.topology_packet import MaterializedTopology
from l9_constellation_topology.publication import (
    PublicationPolicy,
    build_publication_plan,
    candidate_id,
    candidate_identity,
    idempotency_key,
    load_publication_policy,
)
from l9_constellation_topology.publication.contracts import (
    LOWERING_CONTRACT_VERSION,
    MEMORY_INGEST_OPERATION,
)
from l9_constellation_topology.publication.identity import IDEMPOTENCY_ALGORITHM_VERSION

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)
FIXED_TIME = datetime(2026, 3, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def materialized() -> MaterializedTopology:
    return compile_topology(ROOT, INPUTS, created_at=FIXED_TIME).materialized


@pytest.fixture(scope="module")
def policy() -> PublicationPolicy:
    return load_publication_policy(ROOT)


def _identity(**overrides):
    base = {
        "operation": MEMORY_INGEST_OPERATION,
        "candidate_kind": "repository",
        "namespace": "l9-topology/repository",
        "memory_class": "semantic",
        "content": "repo:golden is a FastAPI service",
        "assertion": {"subject": "repo:golden", "predicate": "framework", "object": "fastapi"},
        "source_topology_entity_ids": ("repo:golden",),
    }
    base.update(overrides)
    return candidate_identity(**base)


def _key(identity) -> str:
    return idempotency_key(identity, lowering_contract_version=LOWERING_CONTRACT_VERSION)


# --- the identity function itself -------------------------------------------


def test_equal_facts_built_independently_have_identical_identity() -> None:
    """Two separately constructed descriptions of one fact must agree.

    The payloads are built in different key order from separately allocated
    values, so this exercises canonicalization rather than merely re-evaluating
    one expression twice.
    """
    first = candidate_identity(
        operation=MEMORY_INGEST_OPERATION,
        candidate_kind="repository",
        namespace="l9-topology/repository",
        memory_class="semantic",
        content="repo:golden is a FastAPI service",
        assertion={"subject": "repo:golden", "predicate": "framework", "object": "fastapi"},
        source_topology_entity_ids=("repo:golden",),
    )
    second = candidate_identity(
        source_topology_entity_ids=tuple(["repo:" + "golden"]),
        assertion={"object": "fastapi", "predicate": "framework", "subject": "repo:golden"},
        content=" ".join(["repo:golden", "is", "a", "FastAPI", "service"]),
        memory_class="semantic",
        namespace="l9-topology/repository",
        candidate_kind="repository",
        operation=MEMORY_INGEST_OPERATION,
    )
    assert first is not second
    assert candidate_id(first) == candidate_id(second)
    assert _key(first) == _key(second)


def test_key_carries_an_explicit_algorithm_version() -> None:
    """A v1 key and a v2 key must never be mistaken for one another."""
    assert _key(_identity()).startswith(f"l9-topology-publication/{IDEMPOTENCY_ALGORITHM_VERSION}:")


@pytest.mark.parametrize(
    "field,value",
    [
        ("content", "repo:golden is a Django service"),
        ("memory_class", "episodic"),
        ("namespace", "l9-topology-relocated/repository"),
        ("operation", "memory.retract"),
        ("candidate_kind", "capability"),
        ("assertion", {"subject": "repo:golden", "predicate": "framework", "object": "django"}),
        ("source_topology_entity_ids", ("repo:other",)),
    ],
)
def test_changing_what_the_effect_asserts_changes_its_identity(field: str, value) -> None:
    baseline = _identity()
    changed = _identity(**{field: value})
    assert candidate_id(baseline) != candidate_id(changed), field
    assert _key(baseline) != _key(changed), field


def test_lowering_contract_version_participates() -> None:
    identity = _identity()
    assert idempotency_key(identity, lowering_contract_version="lowering/v1") != idempotency_key(
        identity, lowering_contract_version="lowering/v2"
    )


def test_identity_never_binds_snapshot_or_clock() -> None:
    """The identity payload must not contain any global or volatile field."""
    forbidden = {
        "topology_packet_id",
        "topology_semantic_hash",
        "repository_model_packet_id",
        "repository_model_semantic_hash",
        "publication_plan_id",
        "publication_plan_semantic_hash",
        "policy_hash",
        "created_at",
        "published_at",
        "artifact_hash",
    }
    assert forbidden.isdisjoint(_identity().keys())


# --- the property that motivated the change ---------------------------------


def test_unrelated_snapshot_movement_does_not_rekey_facts(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    """The whole point: a moved topology hash must not re-key unchanged facts.

    This is the exact failure the requalification surfaced — a legitimate
    change altered the topology hash and with it all 27 publication keys, while
    the facts themselves were untouched.
    """
    baseline = build_publication_plan(materialized, policy, published_at=FIXED_TIME)

    moved_packet = materialized.packet.model_copy(
        update={
            "semantic_hash": "sha256:" + "0" * 64,
            "packet_id": "packet:" + "0" * 64,
        }
    )
    moved = build_publication_plan(
        materialized.model_copy(update={"packet": moved_packet}),
        policy,
        published_at=FIXED_TIME,
    )

    assert moved_packet.semantic_hash != materialized.packet.semantic_hash
    assert [item.idempotency_key for item in baseline.candidates] == [
        item.idempotency_key for item in moved.candidates
    ]
    assert [item.candidate_id for item in baseline.candidates] == [
        item.candidate_id for item in moved.candidates
    ]


def test_moved_snapshot_is_still_recorded_as_provenance(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    """Dropping the snapshot from identity must not drop it from the record."""
    plan = build_publication_plan(materialized, policy, published_at=FIXED_TIME)
    for candidate in plan.candidates:
        metadata = candidate.memory_intent.request.metadata
        assert metadata["topology_packet_id"] == materialized.packet.packet_id
        assert metadata["topology_semantic_hash"] == materialized.packet.semantic_hash
        assert metadata["repository_model_packet_ids"]
        assert metadata["publication_policy"]
        assert metadata["idempotency_algorithm_version"] == IDEMPOTENCY_ALGORITHM_VERSION
        assert metadata["lowering_contract_version"] == LOWERING_CONTRACT_VERSION
        # Provenance still names the producing snapshot.
        provenance = candidate.memory_intent.request.provenance
        assert provenance.source_id == materialized.packet.packet_id


def test_keys_are_unique_per_fact(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    """Fact-local keying must not collapse distinct facts onto one key."""
    plan = build_publication_plan(materialized, policy, published_at=FIXED_TIME)
    keys = [item.idempotency_key for item in plan.candidates]
    assert len(set(keys)) == len(keys)
    assert keys, "fixture should produce candidates"


def test_publication_time_does_not_affect_identity(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    first = build_publication_plan(materialized, policy, published_at=FIXED_TIME)
    second = build_publication_plan(
        materialized, policy, published_at=datetime(2027, 12, 25, tzinfo=UTC)
    )
    assert [item.idempotency_key for item in first.candidates] == [
        item.idempotency_key for item in second.candidates
    ]
