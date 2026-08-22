"""Predicate-registry semantics, including the predicate nobody declared.

The real interpretation profile only emits predicates the registry knows, so the
unsupported path cannot be reached from a producer emission. It is reached here
with hand-built assertions, which is the right instrument: what is under test is
the compiler's behaviour when it meets a predicate it has no rule for, not what
the producer happens to emit today.
"""

from __future__ import annotations

import pytest

from l9_constellation_topology.domain.confidence import Authority, ConflictStatus
from l9_constellation_topology.packets.assertion_evidence import (
    ASSERTION_EVIDENCE_STAGE,
    assertion_evidence_record,
)
from l9_constellation_topology.packets.repository_model import (
    AssertionSourceRange,
    RepositoryModelAssertion,
    RepositoryModelPacket,
    RepositoryModelPayload,
)
from l9_constellation_topology.reconciliation import (
    AUXILIARY_PREDICATES,
    SET_VALUED_PREDICATES,
    SINGLE_VALUED_PREDICATES,
    UNSUPPORTED_PREDICATE_CODE,
    is_projectable,
    predicate_cardinality,
    predicate_policy_hash,
    predicate_support,
)
from l9_constellation_topology.stages.reconcile_assertions import run as reconcile_assertions
from l9_constellation_topology.topology.claim_projection import project_claims

SUBJECT = "repo:sample"


def _assertion(
    predicate: str,
    obj: str,
    *,
    path: str = "pyproject.toml",
    line: int = 1,
    digest: str = "a",
    evidence_class: str = "declared",
    confidence: str = "high",
    authority: str = "source",
) -> RepositoryModelAssertion:
    return RepositoryModelAssertion(
        assertion_id=f"assertion:{predicate}:{obj}:{path}:{line}",
        subject_id=SUBJECT,
        predicate=predicate,
        object=obj,
        source_path=path,
        source_range=AssertionSourceRange(start_line=line, end_line=line),
        evidence_excerpt=f"{predicate} = {obj}",
        source_content_hash="sha256:" + digest * 64,
        extractor_id="fixture/v1",
        evidence_class=evidence_class,  # type: ignore[arg-type]
        authority=authority,
        confidence=confidence,
    )


def _packet(assertions: tuple[RepositoryModelAssertion, ...]) -> RepositoryModelPacket:
    return RepositoryModelPacket(
        packet_version="1.1.0",
        packet_id="packet:fixture",
        subject={"repository_id": SUBJECT},
        source_snapshot={"revision": "git:" + "0" * 40, "semantic_hash": "sha256:" + "b" * 64},
        validation={"status": "passed"},
        producer={"name": "fixture-producer", "version": "1.0.0"},
        profile={"id": "p", "version": "1.0.0", "hash": "sha256:" + "c" * 64},
        schema_hash="sha256:" + "d" * 64,
        semantic_hash="sha256:" + "e" * 64,
        payload=RepositoryModelPayload(assertions=assertions),
    )


def _reconcile(assertions: tuple[RepositoryModelAssertion, ...]):
    packet = _packet(assertions)
    evidence = tuple(
        assertion_evidence_record(assertion, packet=packet) for assertion in assertions
    )
    return reconcile_assertions(assertions, evidence)


def test_registry_classifications_are_disjoint_and_complete() -> None:
    assert SET_VALUED_PREDICATES.isdisjoint(SINGLE_VALUED_PREDICATES)
    assert SET_VALUED_PREDICATES.isdisjoint(AUXILIARY_PREDICATES)
    assert SINGLE_VALUED_PREDICATES.isdisjoint(AUXILIARY_PREDICATES)
    for predicate in SET_VALUED_PREDICATES:
        assert predicate_cardinality(predicate) == "set"
        assert is_projectable(predicate)
    for predicate in SINGLE_VALUED_PREDICATES:
        assert predicate_cardinality(predicate) == "single"
        assert is_projectable(predicate)
    for predicate in AUXILIARY_PREDICATES:
        # Auxiliary predicates aggregate like sets but carry no further meaning.
        assert predicate_cardinality(predicate) == "set"
        assert not is_projectable(predicate)


def test_an_undeclared_predicate_is_unknown_and_unprojectable() -> None:
    assert predicate_support("nobody.declared.this") == "unsupported"
    assert predicate_cardinality("nobody.declared.this") == "unknown"
    assert not is_projectable("nobody.declared.this")


def test_the_registry_hash_moves_when_its_meaning_moves() -> None:
    """A stable hash across a meaning change would let identity be reused."""
    import l9_constellation_topology.reconciliation.predicates as predicates

    before = predicate_policy_hash()
    original = predicates.SET_VALUED_PREDICATES
    try:
        predicates.SET_VALUED_PREDICATES = original | {"newly.declared"}
        assert predicate_policy_hash() != before
    finally:
        predicates.SET_VALUED_PREDICATES = original
    assert predicate_policy_hash() == before


def test_an_unsupported_predicate_is_preserved_with_a_diagnostic() -> None:
    claims, conflicts, unknowns, diagnostics = _reconcile(
        (
            _assertion("nobody.declared.this", "first", line=1),
            _assertion("nobody.declared.this", "second", line=2),
        )
    )
    # Nothing aggregated, nothing contradicted, nothing dropped.
    assert {claim.object for claim in claims} == {"first", "second"}
    assert all(claim.support == "unsupported" for claim in claims)
    assert all(claim.cardinality == "unknown" for claim in claims)
    assert conflicts == ()
    # Divergence with no declared arity is "possible", never "confirmed":
    # asserting a contradiction here would be inventing one.
    assert {claim.conflict_status for claim in claims} == {ConflictStatus.possible}
    assert all(claim.evidence_refs for claim in claims)
    assert all(claim.projected is False for claim in claims)

    assert [unknown.field for unknown in unknowns] == ["nobody.declared.this"]
    assert [diagnostic.code for diagnostic in diagnostics] == [UNSUPPORTED_PREDICATE_CODE]
    assert diagnostics[0].details["objects"] == ["first", "second"]
    # Compiler-raised, so it must not claim the disposition reserved for
    # conserved upstream diagnostics.
    assert diagnostics[0].disposition == "translated"


def test_a_single_valued_predicate_conflicts_without_electing_a_winner() -> None:
    claims, conflicts, unknowns, _ = _reconcile(
        (
            _assertion("package.name", "alpha", path="pyproject.toml"),
            _assertion("package.name", "beta", path="package.json"),
        )
    )
    assert {claim.object for claim in claims} == {"alpha", "beta"}
    assert len(conflicts) == 1
    assert conflicts[0].values == ("alpha", "beta")
    assert conflicts[0].resolution is None
    assert unknowns == ()
    assert all(claim.conflict_status is ConflictStatus.confirmed for claim in claims)


def test_repeated_agreement_aggregates_evidence_into_one_claim() -> None:
    claims, conflicts, _, _ = _reconcile(
        (
            _assertion("package.name", "alpha", path="pyproject.toml", digest="a"),
            _assertion("package.name", "alpha", path="setup.cfg", digest="b"),
        )
    )
    assert len(claims) == 1
    assert len(claims[0].source_assertion_ids) == 2
    assert len(claims[0].evidence_refs) == 2
    assert conflicts == ()


def test_claim_confidence_is_never_stronger_than_its_weakest_support() -> None:
    claims, _, _, _ = _reconcile(
        (
            _assertion("package.name", "alpha", path="a.toml", confidence="high"),
            _assertion("package.name", "alpha", path="b.toml", confidence="medium"),
        )
    )
    assert claims[0].confidence.level == "medium"
    assert claims[0].authority is Authority.source
    assert claims[0].confidence.authority is claims[0].authority


def test_an_unrecognized_authority_falls_to_unknown_rather_than_upward() -> None:
    claims, _, _, _ = _reconcile(
        (_assertion("package.name", "alpha", authority="something-invented"),)
    )
    assert claims[0].authority is Authority.unknown


def test_claim_identity_is_the_claim_and_nothing_else() -> None:
    """The same claim from a different packet, path, and digest is one claim."""
    first, *_ = _reconcile((_assertion("package.name", "alpha", path="a.toml", digest="a"),))
    second, *_ = _reconcile(
        (_assertion("package.name", "alpha", path="b.toml", digest="b", line=99),)
    )
    assert first[0].claim_id == second[0].claim_id
    # ...and a different object is a different claim.
    other, *_ = _reconcile((_assertion("package.name", "beta"),))
    assert other[0].claim_id != first[0].claim_id


def test_assertion_evidence_binds_the_file_not_the_snapshot() -> None:
    assertion = _assertion("package.name", "alpha", digest="f")
    packet = _packet((assertion,))
    record = assertion_evidence_record(assertion, packet=packet)
    assert record.stage == ASSERTION_EVIDENCE_STAGE
    assert record.source_ref.content_hash == assertion.source_content_hash
    assert record.source_ref.content_hash != packet.source_snapshot.semantic_hash
    assert record.source_ref.source_revision == packet.source_snapshot.revision
    assert record.source_ref.packet_id == packet.packet_id
    assert record.field == assertion.predicate


@pytest.mark.parametrize(
    "predicate",
    sorted(AUXILIARY_PREDICATES),
)
def test_auxiliary_predicates_project_nothing(predicate: str) -> None:
    claims, _, _, _ = _reconcile((_assertion(predicate, "some-object"),))
    projection = project_claims(claims)
    assert projection.capabilities == ()
    assert projection.edges == ()
    assert projection.nodes == ()
    assert projection.entities_by_claim == {}


def test_predicates_are_adjudicated_once_by_the_right_policy() -> None:
    """Assertion evidence must not also be judged by the field-cardinality contract.

    ``reconcile_evidence`` reads the *field* cardinality contract, which knows
    nothing about assertion predicates. Letting it see assertion evidence made it
    report fourteen true dependencies as an undeclared-cardinality unknown and
    two competing package names as an unknown rather than the conflict they are —
    and the resulting unknowns then held nearly every claim in the plan for a
    doubt that did not exist.
    """
    from l9_constellation_topology.stages.reconcile_evidence import run as reconcile_evidence

    assertions = (
        _assertion("package.dependency", "fastapi", line=1),
        _assertion("package.dependency", "httpx", line=2),
        _assertion("package.name", "alpha", path="pyproject.toml"),
        _assertion("package.name", "beta", path="package.json"),
    )
    packet = _packet(assertions)
    evidence = tuple(
        assertion_evidence_record(assertion, packet=packet) for assertion in assertions
    )

    kept, conflicts, unknowns = reconcile_evidence(evidence)
    # Deduplicated and carried through...
    assert len(kept) == len(evidence)
    # ...but judged by nothing here.
    assert conflicts == ()
    assert unknowns == ()

    # The predicate registry reaches the correct verdicts instead.
    _, claim_conflicts, claim_unknowns, _ = reconcile_assertions(assertions, evidence)
    assert [item.field for item in claim_conflicts] == ["package.name"]
    assert claim_unknowns == ()


def test_a_claim_that_cannot_be_stated_is_skipped_with_a_reason() -> None:
    """One malformed claim must not fail the whole plan, or vanish quietly."""
    from datetime import UTC, datetime
    from pathlib import Path

    from l9_constellation_topology.compiler import compile_topology
    from l9_constellation_topology.publication import (
        build_publication_plan,
        load_publication_policy,
    )
    from l9_constellation_topology.publication.eligibility import SKIP_UNSTATEABLE_CLAIM

    root = Path(__file__).resolve().parents[1]
    fixed = datetime(2026, 7, 21, tzinfo=UTC)
    result = compile_topology(
        root,
        (root / "tests/fixtures/repository_model_packets/l9-assertion-sample",),
        created_at=fixed,
    )
    state = result.materialized.state
    # An object no downstream assertion can carry. The claim still exists in
    # canonical topology; only its statement downstream is impossible.
    damaged = state.model_copy(
        update={
            "semantic_claims": (
                state.semantic_claims[0].model_copy(update={"object": ""}),
                *state.semantic_claims[1:],
            )
        }
    )
    plan = build_publication_plan(
        result.materialized.model_copy(update={"state": damaged}),
        load_publication_policy(root),
        published_at=fixed,
    )
    skipped = [item for item in plan.skipped_candidates if item.reason == SKIP_UNSTATEABLE_CLAIM]
    assert [item.source_id for item in skipped] == [state.semantic_claims[0].claim_id]
    # Every other claim published normally.
    claim_candidates = [item for item in plan.candidates if item.candidate_kind == "claim"]
    assert len(claim_candidates) == len(state.semantic_claims) - 1
