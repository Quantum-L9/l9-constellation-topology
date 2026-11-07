"""Evidence-qualified relation publication and predicate-selective claims (ADR-0036).

Every comparison here is built from identical pinned source packets — the checked-in
Repository Model Packet fixtures and the producer-emitted corpus fixture — under the
pre-ADR-0036 policy (``tests/fixtures/publication_policies/legacy-v1``, a byte copy
of the 1.0.0 policy) and the checked-in strict policy. The Topology Packet is the
same object in both; only the publication policy differs.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.domain.confidence import ConflictStatus
from l9_constellation_topology.domain.edge import EdgeRecord, EdgeType
from l9_constellation_topology.packets.topology_packet import MaterializedTopology
from l9_constellation_topology.publication import (
    PublicationPolicy,
    PublicationPolicyError,
    build_publication_plan,
    load_publication_policy,
)
from l9_constellation_topology.publication import qualification as q
from l9_constellation_topology.publication.eligibility import (
    SKIP_CLAIM_PREDICATE,
    SKIP_DECLARATION_ONLY_CLAIM,
    SKIP_EDGE_TYPE,
)
from l9_constellation_topology.publication.qualification import (
    QualificationIndex,
    qualify_relation,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
LEGACY_POLICY_ROOT = FIXTURES / "publication_policies/legacy-v1"
PRODUCER = FIXTURES / "corpus_intelligence/producer-emitted"
FIXED_TIME = datetime(2026, 7, 21, tzinfo=UTC)


@pytest.fixture(scope="module")
def repository_topology() -> MaterializedTopology:
    inputs = tuple(sorted((FIXTURES / "repository_model_packets").iterdir()))
    return compile_topology(ROOT, inputs, created_at=FIXED_TIME).materialized


@pytest.fixture(scope="module")
def corpus_topology() -> MaterializedTopology:
    return compile_topology(
        ROOT,
        tuple(sorted((PRODUCER / "roots").iterdir())),
        corpus_bundle_paths=(PRODUCER / "corpus-intelligence",),
        created_at=FIXED_TIME,
    ).materialized


@pytest.fixture(scope="module")
def strict() -> PublicationPolicy:
    return load_publication_policy(ROOT)


@pytest.fixture(scope="module")
def legacy() -> PublicationPolicy:
    return load_publication_policy(LEGACY_POLICY_ROOT)


def _qualifications(topology: MaterializedTopology) -> dict[str, q.RelationQualification]:
    index = QualificationIndex.build(topology.state)
    return {edge.edge_id: qualify_relation(edge, index) for edge in topology.state.edge_records}


def _edge(topology: MaterializedTopology, origin: str) -> EdgeRecord:
    index = QualificationIndex.build(topology.state)
    return next(
        edge for edge in topology.state.edge_records if q.relation_origin(edge, index) == origin
    )


# --- policy ----------------------------------------------------------------------


def test_legacy_policy_keeps_its_pre_qualification_identity(legacy: PublicationPolicy) -> None:
    assert legacy.identity == "foundational-topology-publication/1.0.0"
    assert legacy.relation_qualification == "legacy"
    assert legacy.claim_publication == "all"
    raw = legacy.raw()
    for key in (
        "relation_qualification",
        "claim_publication",
        "eligible_claim_predicates",
        "declaration_only_claim_predicates",
    ):
        assert key not in raw


def test_strict_policy_states_its_qualification_fields(strict: PublicationPolicy) -> None:
    raw = strict.raw()
    assert raw["relation_qualification"] == "strict"
    assert raw["claim_publication"] == "selective"
    assert raw["declaration_only_claim_predicates"] == []
    assert strict.policy_hash() != load_publication_policy(LEGACY_POLICY_ROOT).policy_hash()


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"eligible_claim_predicates": ("package.name",)}, "require claim_publication"),
        (
            {"claim_publication": "selective", "eligible_claim_predicates": ("no.such",)},
            "does not declare",
        ),
        (
            {
                "claim_publication": "selective",
                "eligible_claim_predicates": ("meta.managed.identity.id",),
            },
            "must be opted in",
        ),
        (
            {
                "claim_publication": "selective",
                "declaration_only_claim_predicates": ("package.name",),
            },
            "not declaration-only",
        ),
        (
            {
                "claim_publication": "selective",
                "eligible_claim_predicates": ("package.name", "package.name"),
            },
            "more than once",
        ),
    ],
)
def test_claim_selection_fails_closed_on_ambiguity(
    legacy: PublicationPolicy, update: dict[str, object], message: str
) -> None:
    candidate = {**legacy.model_dump(), **update}
    with pytest.raises(ValueError, match=message):
        PublicationPolicy.model_validate(candidate)


def test_policy_file_errors_surface_as_policy_errors(tmp_path: Path) -> None:
    text = (LEGACY_POLICY_ROOT / ".l9/publication-policy.yaml").read_text(encoding="utf-8")
    (tmp_path / ".l9").mkdir()
    (tmp_path / ".l9/publication-policy.yaml").write_text(
        text + "\nrelation_qualification: lenient\n", encoding="utf-8"
    )
    with pytest.raises(PublicationPolicyError):
        load_publication_policy(tmp_path)


# --- the qualification function -----------------------------------------------------


def test_every_edge_type_has_a_declared_qualification_rule() -> None:
    assert set(q.ADMISSIBLE_ORIGINS) == set(EdgeType)


def test_qualification_is_pure_and_deterministic(
    repository_topology: MaterializedTopology,
) -> None:
    before = repository_topology.state.model_copy(deep=True)
    first = _qualifications(repository_topology)
    second = _qualifications(repository_topology)
    assert first == second
    assert repository_topology.state == before


def test_every_pinned_edge_has_an_identified_producer(
    repository_topology: MaterializedTopology, corpus_topology: MaterializedTopology
) -> None:
    for topology in (repository_topology, corpus_topology):
        assert "unrecognized" not in {item.origin for item in _qualifications(topology).values()}


def test_artifact_type_promotion_is_classification_only(
    repository_topology: MaterializedTopology, corpus_topology: MaterializedTopology
) -> None:
    promoted = [
        item
        for topology in (repository_topology, corpus_topology)
        for item in _qualifications(topology).values()
        if item.origin == "artifact-classification"
    ]
    assert {item.edge_type for item in promoted} == {
        "DOCUMENTED_BY",
        "GOVERNED_BY",
        "VALIDATED_BY",
    }
    assert {item.reason for item in promoted} == {q.REASON_CLASSIFICATION_ONLY}


def test_claim_projected_relations_qualify_on_an_eligible_claim(
    repository_topology: MaterializedTopology,
) -> None:
    by_origin = Counter(
        (item.origin, item.edge_type, item.status, item.reason)
        for item in _qualifications(repository_topology).values()
        if item.origin == "claim-projector"
    )
    assert by_origin == {
        ("claim-projector", "DEPENDS_ON", "qualified", "projection-eligible-claim"): 4,
        ("claim-projector", "GOVERNED_BY", "qualified", "projection-eligible-claim"): 2,
        ("claim-projector", "SUPERSEDES", "qualified", "projection-eligible-claim"): 1,
    }


def test_conflicted_originating_claim_never_qualifies_a_relation(
    repository_topology: MaterializedTopology,
) -> None:
    """D5a: the claim gate is reused, not restated."""
    state = repository_topology.state
    edge = _edge(repository_topology, "claim-projector")
    claim_id = edge.properties["projected_from_claim_id"]
    claims = tuple(
        claim.model_copy(update={"conflict_status": ConflictStatus.possible})
        if claim.claim_id == claim_id
        else claim
        for claim in state.semantic_claims
    )
    index = QualificationIndex.build(state.model_copy(update={"semantic_claims": claims}))
    result = qualify_relation(edge, index)
    assert (result.status, result.reason) == ("unqualified", q.REASON_CLAIM_NOT_PROJECTABLE)


def test_missing_originating_claim_is_missing_evidence(
    repository_topology: MaterializedTopology,
) -> None:
    edge = _edge(repository_topology, "claim-projector")
    index = QualificationIndex.build(
        repository_topology.state.model_copy(update={"semantic_claims": ()})
    )
    assert qualify_relation(edge, index).reason == q.REASON_EVIDENCE_MISSING


def test_claim_projected_endpoint_must_match_its_family(
    repository_topology: MaterializedTopology,
) -> None:
    edge = _edge(repository_topology, "claim-projector")
    wrong = edge.model_copy(
        update={"properties": {**edge.properties, "endpoint_kind": "something-else"}}
    )
    index = QualificationIndex.build(repository_topology.state)
    assert qualify_relation(wrong, index).reason == q.REASON_ENDPOINT_MISMATCH


def test_work_relations_qualify_only_on_exact_resolution(
    corpus_topology: MaterializedTopology,
) -> None:
    """D5b: the producer's own recorded resolution decides; absent is never resolved."""
    work = [
        item
        for item in _qualifications(corpus_topology).values()
        if item.origin == "work-projector"
    ]
    # Every work target in the producer-emitted corpus is ambiguous or unresolved.
    assert work
    assert {(item.status, item.reason) for item in work} == {
        ("unqualified", q.REASON_WORK_TARGET_UNRESOLVED)
    }
    edge = _edge(corpus_topology, "work-projector")
    index = QualificationIndex.build(corpus_topology.state)
    exact = edge.model_copy(
        update={"properties": {**edge.properties, "target_resolution": "exact-artifact"}}
    )
    assert qualify_relation(exact, index).reason == "exact-artifact-resolution"
    absent = {key: value for key, value in edge.properties.items() if key != "target_resolution"}
    # Without the producer's recorded resolution the edge is no longer the work
    # projector's, and nothing else claims it: never read as resolved.
    assert not qualify_relation(edge.model_copy(update={"properties": absent}), index).qualified


def test_graph_builder_dependency_requires_an_observed_target(
    repository_topology: MaterializedTopology,
) -> None:
    edge = _edge(repository_topology, "repository-upstream")
    index = QualificationIndex.build(repository_topology.state)
    assert qualify_relation(edge, index).reason == "observed-repository-target"
    unobserved = index.repositories.copy()
    del unobserved[edge.target_id]
    detached = QualificationIndex(**{**index.__dict__, "repositories": unobserved})
    # Removing the target also removes the record the edge mirrored; still
    # fail-closed either way, never resolved.
    assert not qualify_relation(edge, detached).qualified


def test_producer_declared_relation_needs_relation_field_evidence(
    corpus_topology: MaterializedTopology,
) -> None:
    edge = _edge(corpus_topology, "producer-declared")
    assert edge.edge_type is EdgeType.derived_from
    index = QualificationIndex.build(corpus_topology.state)
    assert qualify_relation(edge, index).reason == "relation-field-evidence"
    stripped = edge.model_copy(update={"evidence_refs": ("evidence:absent",)})
    assert qualify_relation(stripped, index).reason == q.REASON_ORIGIN_UNSUPPORTED
    # The same relation-field evidence cited by an edge between other endpoints
    # is about a different fact and does not qualify it.
    other = next(
        artifact_id
        for artifact_id in index.artifacts
        if artifact_id not in (edge.source_id, edge.target_id)
    )
    unrelated = edge.model_copy(update={"source_id": other})
    assert not qualify_relation(unrelated, index).qualified


def test_exact_duplicates_qualify_on_content_hash_equality(
    corpus_topology: MaterializedTopology,
) -> None:
    edge = _edge(corpus_topology, "exact-duplicate")
    index = QualificationIndex.build(corpus_topology.state)
    assert qualify_relation(edge, index).reason == "content-hash-equality"
    no_hash = edge.model_copy(update={"properties": {**edge.properties, "content_hash": ""}})
    assert qualify_relation(no_hash, index).reason == q.REASON_EVIDENCE_MISSING
    # A non-empty hash that neither endpoint carries is not byte identity.
    forged = edge.model_copy(
        update={"properties": {**edge.properties, "content_hash": "sha256:" + "0" * 64}}
    )
    assert qualify_relation(forged, index).reason == q.REASON_EVIDENCE_MISSING
    # Nor is one that only one endpoint carries.
    target = index.artifacts[edge.target_id]
    drifted = dict(index.artifacts)
    drifted[edge.target_id] = target.model_copy(update={"content_hash": "sha256:" + "1" * 64})
    detached = QualificationIndex(**{**index.__dict__, "artifacts": drifted})
    assert qualify_relation(edge, detached).reason == q.REASON_EVIDENCE_MISSING


def test_recognized_producer_without_resolvable_evidence_is_unqualified(
    repository_topology: MaterializedTopology,
) -> None:
    edge = _edge(repository_topology, "repository-owner")
    index = QualificationIndex.build(repository_topology.state)
    orphan = edge.model_copy(update={"evidence_refs": ()})
    assert qualify_relation(orphan, index).reason == q.REASON_EVIDENCE_MISSING


def test_relation_type_without_a_rule_fails_closed(
    repository_topology: MaterializedTopology, monkeypatch: pytest.MonkeyPatch
) -> None:
    edge = _edge(repository_topology, "repository-owner")
    rules = dict(q.ADMISSIBLE_ORIGINS)
    del rules[EdgeType.owned_by]
    monkeypatch.setattr(q, "ADMISSIBLE_ORIGINS", rules)
    index = QualificationIndex.build(repository_topology.state)
    assert qualify_relation(edge, index).reason == q.REASON_TYPE_UNRECOGNIZED


# --- the plan effect, from identical pinned packets ----------------------------------


@pytest.mark.parametrize("topology_name", ["repository_topology", "corpus_topology"])
def test_strict_effect_is_exactly_the_unqualified_relations_and_unselected_claims(
    topology_name: str,
    request: pytest.FixtureRequest,
    strict: PublicationPolicy,
    legacy: PublicationPolicy,
) -> None:
    topology: MaterializedTopology = request.getfixturevalue(topology_name)
    packet_before = topology.packet.model_copy(deep=True)
    legacy_plan = build_publication_plan(topology, legacy, published_at=FIXED_TIME)
    strict_plan = build_publication_plan(topology, strict, published_at=FIXED_TIME)
    assert topology.packet == packet_before
    assert legacy_plan.source_topology_semantic_hash == strict_plan.source_topology_semantic_hash

    legacy_ids = {item.candidate_id for item in legacy_plan.candidates}
    strict_ids = {item.candidate_id for item in strict_plan.candidates}
    # Strict only removes; it never invents a candidate and never re-identifies a fact.
    assert strict_ids <= legacy_ids

    removed = {
        item.candidate_id: item
        for item in legacy_plan.candidates
        if item.candidate_id not in strict_ids
    }
    qualifications = _qualifications(topology)
    strict_skips = {item.source_id: item.reason for item in strict_plan.skipped_candidates}
    for candidate in removed.values():
        if candidate.candidate_kind == "relationship":
            edge_id = candidate.memory_intent.request.metadata["topology_relation"]["edge_id"]
            assert not qualifications[edge_id].qualified
            assert strict_skips[edge_id] == qualifications[edge_id].reason
        else:
            assert candidate.candidate_kind == "claim"
            predicate = candidate.lowering.assertion_predicate
            assert predicate is not None
            assert strict.claim_predicate_selection(predicate) is False
    selection_skips = {
        item.reason
        for item in strict_plan.skipped_candidates
        if item.source_kind == "claim" and item.reason != "policy.entity_kind_not_selected"
    }
    assert selection_skips <= {SKIP_CLAIM_PREDICATE, SKIP_DECLARATION_ONLY_CLAIM}
    assert len([c for c in removed.values() if c.candidate_kind == "claim"]) == len(
        [
            item
            for item in strict_plan.skipped_candidates
            if item.reason in {SKIP_CLAIM_PREDICATE, SKIP_DECLARATION_ONLY_CLAIM}
        ]
    )

    # Every qualification skip names a relationship and an ADR-0036 reason.
    for item in strict_plan.skipped_candidates:
        if item.reason in q.UNQUALIFIED_REASONS:
            assert item.source_kind == "relationship"
    # An edge skipped by selection under strict was qualified first.
    for item in strict_plan.skipped_candidates:
        if item.reason == SKIP_EDGE_TYPE:
            assert qualifications[item.source_id].qualified


def test_strict_effect_counts_on_pinned_packets(
    repository_topology: MaterializedTopology,
    corpus_topology: MaterializedTopology,
    strict: PublicationPolicy,
    legacy: PublicationPolicy,
) -> None:
    def removed(topology: MaterializedTopology) -> Counter[str]:
        legacy_plan = build_publication_plan(topology, legacy, published_at=FIXED_TIME)
        strict_plan = build_publication_plan(topology, strict, published_at=FIXED_TIME)
        strict_ids = {item.candidate_id for item in strict_plan.candidates}
        return Counter(
            item.candidate_kind
            for item in legacy_plan.candidates
            if item.candidate_id not in strict_ids
        )

    # Nine classification-promoted relations and two auxiliary claims.
    assert removed(repository_topology) == {"relationship": 9, "claim": 2}
    # Fourteen classification-promoted DOCUMENTED_BY relations.
    assert removed(corpus_topology) == {"relationship": 14}


def test_retained_facts_keep_fact_identity_and_rekey_only_by_policy_version(
    repository_topology: MaterializedTopology,
    strict: PublicationPolicy,
    legacy: PublicationPolicy,
) -> None:
    """ADR-0025: a policy version bump re-keys effects; nothing else does here."""
    legacy_plan = build_publication_plan(repository_topology, legacy, published_at=FIXED_TIME)
    strict_plan = build_publication_plan(repository_topology, strict, published_at=FIXED_TIME)
    unversioned = strict.model_copy(update={"version": legacy.version})
    same_version_plan = build_publication_plan(
        repository_topology, unversioned, published_at=FIXED_TIME
    )
    legacy_keys = {item.candidate_id: item.idempotency_key for item in legacy_plan.candidates}
    for item in strict_plan.candidates:
        assert item.idempotency_key != legacy_keys[item.candidate_id]
    for item in same_version_plan.candidates:
        assert item.idempotency_key == legacy_keys[item.candidate_id]


def test_qualified_relationship_states_its_basis_only_under_strict(
    repository_topology: MaterializedTopology,
    strict: PublicationPolicy,
    legacy: PublicationPolicy,
) -> None:
    strict_plan = build_publication_plan(repository_topology, strict, published_at=FIXED_TIME)
    legacy_plan = build_publication_plan(repository_topology, legacy, published_at=FIXED_TIME)
    for item in strict_plan.candidates:
        if item.candidate_kind == "relationship":
            basis = item.memory_intent.request.metadata["topology_relation"]["qualification"]
            assert basis["status"] == "qualified"
    for item in legacy_plan.candidates:
        if item.candidate_kind == "relationship":
            assert "qualification" not in item.memory_intent.request.metadata["topology_relation"]


def test_declaration_only_claims_publish_only_when_opted_in(
    repository_topology: MaterializedTopology, strict: PublicationPolicy
) -> None:
    state = repository_topology.state
    template = state.semantic_claims[0]
    header = template.model_copy(
        update={
            "claim_id": "claim:managed-header-sample",
            "predicate": "meta.managed.identity.id",
            "object": "sample-artifact",
            "support": "single",
        }
    )
    topology = MaterializedTopology(
        packet=repository_topology.packet,
        state=state.model_copy(update={"semantic_claims": (*state.semantic_claims, header)}),
    )
    plan = build_publication_plan(topology, strict, published_at=FIXED_TIME)
    assert {
        item.reason for item in plan.skipped_candidates if item.source_id == header.claim_id
    } == {SKIP_DECLARATION_ONLY_CLAIM}

    opted_in = strict.model_copy(
        update={"declaration_only_claim_predicates": ("meta.managed.identity.id",)}
    )
    plan = build_publication_plan(topology, opted_in, published_at=FIXED_TIME)
    assert [
        item.lowering.assertion_predicate
        for item in plan.candidates
        if item.source_topology_entity_ids == (header.subject_id,)
        and item.lowering.assertion_predicate == "meta.managed.identity.id"
    ] == ["meta.managed.identity.id"]


def test_unsupported_predicate_is_still_held_under_selective_publication(
    repository_topology: MaterializedTopology, strict: PublicationPolicy
) -> None:
    state = repository_topology.state
    template = state.semantic_claims[0]
    unknown = template.model_copy(
        update={
            "claim_id": "claim:unsupported-sample",
            "predicate": "vendor.unregistered",
            "support": "unsupported",
        }
    )
    topology = MaterializedTopology(
        packet=repository_topology.packet,
        state=state.model_copy(update={"semantic_claims": (*state.semantic_claims, unknown)}),
    )
    plan = build_publication_plan(topology, strict, published_at=FIXED_TIME)
    held = [
        item
        for item in plan.held_candidates
        if item.lowering.assertion_predicate == "vendor.unregistered"
    ]
    assert len(held) == 1
    assert "predicate.unsupported_by_registry" in held[0].eligibility.reasons


def test_strict_plan_is_replay_deterministic(
    corpus_topology: MaterializedTopology, strict: PublicationPolicy
) -> None:
    first = build_publication_plan(corpus_topology, strict, published_at=FIXED_TIME)
    second = build_publication_plan(
        corpus_topology, strict, published_at=datetime(2027, 1, 1, tzinfo=UTC)
    )
    assert first.plan_id == second.plan_id
    assert first.semantic_hash == second.semantic_hash
