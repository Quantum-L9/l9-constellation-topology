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
    confidence_semantics,
    evidence_semantics,
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


def _restated_identity():
    """The same fact as ``_identity()``, assembled from separately built values."""
    return candidate_identity(
        source_topology_entity_ids=tuple(["repo:" + "golden"]),
        assertion={"object": "fastapi", "predicate": "framework", "subject": "repo:golden"},
        content=" ".join(["repo:golden", "is", "a", "FastAPI", "service"]),
        memory_class="semantic",
        namespace="/".join(("l9-topology", "repository")),
        candidate_kind="repository",
        operation=MEMORY_INGEST_OPERATION,
    )


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
    """Keys from different algorithm generations must never be confusable."""
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


# --- v3: the fact and the requested write are different identities -----------
#
# v2 keyed a write by the fact alone. Downstream, ``idempotency_key`` names an
# *operation*: a matching key is answered DUPLICATE and the request's content is
# never admitted. So a re-publication carrying new evidence or a recalibrated
# confidence under the old key was read as a retry, and the new epistemic state
# was silently discarded. These tests pin the fix in both directions — the write
# identity must move when the epistemic state moves, and the *fact* identity
# must not.


def _confidence(score: float = 0.9, evidence_count: int = 1, method: str = "extracted"):
    return confidence_semantics(
        score=score,
        method=method,
        evidence_count=evidence_count,
        confidence_policy_version="l9-topology-publication/1.0.0",
    )


def _evidence(digest: str = "a" * 64, locator: str = "pyproject.toml", kind: str = "explicit"):
    return evidence_semantics(
        evidence_kind=kind,
        source_content_digest=digest,
        stable_source_locator=locator,
    )


def _effect_key(
    *,
    local_evidence=(),
    confidence=None,
    derivation_kind: str | None = None,
) -> str:
    return idempotency_key(
        _identity(),
        lowering_contract_version=LOWERING_CONTRACT_VERSION,
        local_evidence=local_evidence,
        confidence=confidence if confidence is not None else _confidence(),
        derivation_kind=derivation_kind,
    )


def test_identical_epistemic_state_is_the_same_write() -> None:
    """Two independently described writes over one epistemic state are one write.

    The two descriptions are assembled from separately allocated values in
    different argument order, so this exercises canonicalization rather than
    re-evaluating one expression twice.
    """
    first = _effect_key(
        local_evidence=(
            evidence_semantics(
                evidence_kind="explicit",
                source_content_digest="a" * 64,
                stable_source_locator="pyproject.toml",
            ),
        ),
        confidence=confidence_semantics(
            score=0.9,
            method="extracted",
            evidence_count=1,
            confidence_policy_version="l9-topology-publication/1.0.0",
        ),
    )
    second = _effect_key(
        confidence=confidence_semantics(
            confidence_policy_version="l9-topology-publication/" + "1.0.0",
            evidence_count=1,
            method="extracted",
            score=float("0.9"),
        ),
        local_evidence=(
            evidence_semantics(
                stable_source_locator="/".join(("pyproject.toml",)),
                source_content_digest="a" * 32 + "a" * 32,
                evidence_kind="explicit",
            ),
        ),
    )
    assert first == second


def test_evidence_order_does_not_change_the_write() -> None:
    """Two writes resting on the same evidence are one write, whatever the order."""
    first = _evidence(digest="a" * 64, locator="a.toml")
    second = _evidence(digest="b" * 64, locator="b.toml")
    assert _effect_key(local_evidence=(first, second)) == _effect_key(
        local_evidence=(second, first)
    )


@pytest.mark.parametrize(
    "local_evidence",
    [
        pytest.param((_evidence(), _evidence(digest="b" * 64, locator="b.toml")), id="stronger"),
        pytest.param((), id="weaker"),
        pytest.param((_evidence(digest="c" * 64),), id="different-content"),
        pytest.param((_evidence(locator="moved.toml"),), id="different-file"),
        pytest.param((_evidence(kind="observation"),), id="different-kind"),
    ],
)
def test_a_change_of_supporting_evidence_is_a_different_write(local_evidence) -> None:
    baseline = _effect_key(local_evidence=(_evidence(),))
    assert _effect_key(local_evidence=local_evidence) != baseline
    # ...and the logical fact is untouched throughout: an identity assembled
    # from separately built values still names the same candidate.
    assert candidate_id(_identity()) == candidate_id(_restated_identity())


@pytest.mark.parametrize(
    "confidence",
    [
        pytest.param(_confidence(score=0.6), id="score"),
        pytest.param(_confidence(method="inferred"), id="method"),
        pytest.param(_confidence(evidence_count=2), id="evidence-count"),
        pytest.param(
            confidence_semantics(
                score=0.9,
                method="extracted",
                evidence_count=1,
                confidence_policy_version="l9-topology-publication/2.0.0",
            ),
            id="policy-version",
        ),
    ],
)
def test_a_change_of_claimed_confidence_is_a_different_write(confidence) -> None:
    baseline = _effect_key(local_evidence=(_evidence(),))
    assert _effect_key(local_evidence=(_evidence(),), confidence=confidence) != baseline


def test_a_synthesized_derivation_kind_participates() -> None:
    """A derived support the request carries is part of what it asks for."""
    baseline = _effect_key(local_evidence=(_evidence(),))
    assert _effect_key(local_evidence=(_evidence(),), derivation_kind="aggregation") != baseline


def test_the_fact_identity_ignores_evidence_and_confidence_entirely() -> None:
    """candidate_id names the fact; only the effect key knows how well it is known."""
    identity = _identity()
    strong = _effect_key(local_evidence=(_evidence(),), confidence=_confidence(score=0.9))
    weak = _effect_key(local_evidence=(), confidence=_confidence(score=0.3))

    # The two writes disagree about how well the fact is known...
    assert strong != weak
    # ...and the fact identity is unmoved by either, because neither is an
    # argument to it. The comparison is against a separately assembled
    # description of the same fact, not a re-evaluation of the same expression.
    assert candidate_id(identity) == candidate_id(_restated_identity())


def test_compiled_plans_separate_fact_identity_from_write_identity(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    """End to end: recalibrating confidence re-keys the write, not the fact."""
    baseline = build_publication_plan(materialized, policy, published_at=FIXED_TIME)
    recalibrated_policy = policy.model_copy(
        update={"confidence_score_by_level": {"low": 0.2, "medium": 0.5, "high": 0.8}}
    )
    recalibrated = build_publication_plan(
        materialized, recalibrated_policy, published_at=FIXED_TIME
    )

    assert [item.candidate_id for item in baseline.candidates] == [
        item.candidate_id for item in recalibrated.candidates
    ]
    moved = [
        (before.idempotency_key, after.idempotency_key)
        for before, after in zip(baseline.candidates, recalibrated.candidates, strict=True)
        if before.memory_intent.request.confidence.score
        != after.memory_intent.request.confidence.score
    ]
    assert moved, "the fixture must contain at least one recalibrated candidate"
    assert all(before != after for before, after in moved)
