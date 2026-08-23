"""What a corpus is allowed to publish as durable memory, and what it is not.

The line this suite defends: "these two files hold identical bytes" is a fact
and may become durable memory; "these files are the same project" is a candidate
and may not — not before a World Model or a human has adjudicated it, and not
however strong the analysis that proposed it.

The reason the line is worth defending mechanically is that durable memory is
where the epistemic class disappears. A candidate published as an observation
reads downstream exactly like an observation, and nothing in the record says it
was ever a proposal.

No intent is dispatched anywhere in this suite. A plan is a plan.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.domain.edge import EdgeType
from l9_constellation_topology.packets.topology_packet import MaterializedTopology
from l9_constellation_topology.publication import (
    PublicationPlan,
    build_publication_plan,
    load_publication_policy,
    validate_publication_plan,
)
from l9_constellation_topology.publication.eligibility import (
    SKIP_CANDIDATE_DOMAIN,
    SKIP_READINESS_DOMAIN,
    SKIP_REASONING_DOMAIN,
    SKIP_UNRESOLVED_WORK_TARGET,
)
from tests.corpus_fixtures import FIXED_TIME, write_corpus

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def materialized(tmp_path_factory: pytest.TempPathFactory) -> MaterializedTopology:
    root = tmp_path_factory.mktemp("publication")
    repositories, corpus = write_corpus(root)
    return compile_topology(
        ROOT, repositories, corpus_bundle_paths=(corpus,), created_at=FIXED_TIME
    ).materialized


@pytest.fixture(scope="module")
def plan(materialized: MaterializedTopology) -> PublicationPlan:
    return build_publication_plan(
        materialized, load_publication_policy(ROOT), published_at=FIXED_TIME
    )


def _skipped(plan: PublicationPlan, reason: str) -> set[str]:
    return {item.source_id for item in plan.skipped_candidates if item.reason == reason}


def test_the_plan_validates_against_the_bound_downstream_contract(
    plan: PublicationPlan,
) -> None:
    """Every intent the plan generates conforms to the memory contract as written."""
    assert validate_publication_plan(plan, repository_root=ROOT) == ()


def test_no_intent_is_dispatched(plan: PublicationPlan) -> None:
    """A plan is a plan.

    Asserted structurally rather than by counting calls: this repository carries
    no memory, Graphiti, or Neo4j client at all, which is what
    `scripts/architecture_boundary_check.py` enforces independently.
    """
    assert plan.plan_id.startswith("publication-plan:")
    assert not hasattr(plan, "dispatched")
    assert not hasattr(plan, "results")


def test_every_candidate_domain_is_held(
    plan: PublicationPlan, materialized: MaterializedTopology
) -> None:
    """Held explicitly, not merely absent.

    A plan that silently omitted candidates would be indistinguishable from a
    plan compiled over a corpus that produced none, and "we held six project
    candidates" and "there were no project candidates" are different facts.
    """
    state = materialized.state
    held = _skipped(plan, SKIP_CANDIDATE_DOMAIN)
    assert held == (
        {record.candidate_id for record in state.candidate_clusters}
        | {record.relation_id for record in state.candidate_relations}
    )
    assert held, "the fixture corpus carries candidates to hold"


def test_readiness_evidence_is_not_published(
    plan: PublicationPlan, materialized: MaterializedTopology
) -> None:
    """Counts published as durable memory read as a verdict about a body of work."""
    assert _skipped(plan, SKIP_READINESS_DOMAIN) == {
        record.readiness_id for record in materialized.state.readiness_evidence
    }


def test_reasoning_candidates_are_not_published(
    plan: PublicationPlan, materialized: MaterializedTopology
) -> None:
    """A request for adjudication is not a conclusion."""
    assert _skipped(plan, SKIP_REASONING_DOMAIN) == {
        record.reasoning_candidate_id for record in materialized.state.topology_reasoning_candidates
    }


def test_no_candidate_identity_appears_in_any_generated_intent(
    plan: PublicationPlan, materialized: MaterializedTopology
) -> None:
    """The end-to-end containment check, over the actual intent payloads."""
    state = materialized.state
    candidate_ids = {record.candidate_id for record in state.candidate_clusters} | {
        record.relation_id for record in state.candidate_relations
    }
    for candidate in plan.candidates:
        request = candidate.memory_intent.request
        assert not candidate_ids & set(candidate.source_topology_entity_ids)
        for identity in candidate_ids:
            assert identity not in request.content
            if request.assertion is not None:
                assert identity != request.assertion.subject
                assert identity != request.assertion.object


def test_no_intent_asserts_project_membership(plan: PublicationPlan) -> None:
    """ "These files are the same project" must not reach durable memory."""
    for candidate in plan.candidates:
        assertion = candidate.memory_intent.request.assertion
        if assertion is not None:
            assert assertion.predicate != "MEMBER_OF"


def test_an_exact_duplicate_is_eligible(
    plan: PublicationPlan, materialized: MaterializedTopology
) -> None:
    """Byte identity is decidable and re-checkable, so it is a canonical fact.

    The hash travels with the assertion, which is what makes it checkable
    downstream without re-running the producer.
    """
    duplicate_ids = {
        edge.edge_id
        for edge in materialized.state.edge_records
        if edge.edge_type is EdgeType.duplicate_of
    }
    published = [
        candidate
        for candidate in plan.candidates
        if candidate.memory_intent.request.assertion is not None
        and candidate.memory_intent.request.assertion.predicate == "DUPLICATE_OF"
    ]
    assert published, "the corpus carries duplicate edges to publish"
    assert duplicate_ids
    for candidate in published:
        assert candidate.eligibility.status in {"eligible", "held"}
        assert candidate.lowering.resolved_evidence_ids, (
            "a published byte-identity claim must carry the evidence behind it"
        )


def test_an_exactly_resolved_work_relation_is_eligible(plan: PublicationPlan) -> None:
    published = {
        candidate.memory_intent.request.assertion.predicate
        for candidate in plan.candidates
        if candidate.memory_intent.request.assertion is not None
    }
    assert "DEPENDS_ON" in published
    assert "BLOCKED_BY" in published


def test_an_unresolved_work_relation_is_never_published(
    plan: PublicationPlan, materialized: MaterializedTopology
) -> None:
    """The declaration is real; the endpoint is not.

    Publishing it would state a *resolved* relation downstream, and a consumer
    reading only the assertion cannot tell the endpoint was never observed.
    """
    skipped = _skipped(plan, SKIP_UNRESOLVED_WORK_TARGET)
    unresolved = {
        edge.edge_id
        for edge in materialized.state.edge_records
        if edge.properties.get("target_resolution") in {"ambiguous", "unresolved"}
    }
    assert unresolved, "the fixture corpus contains both an ambiguous and an unresolved target"
    assert skipped == unresolved


def test_a_conflicted_claim_is_held_rather_than_published(
    plan: PublicationPlan,
) -> None:
    """The DOCX/PPTX contradiction reaches publication as a hold, not a winner."""
    conflicted = [
        candidate
        for candidate in plan.candidates
        if candidate.lowering.assertion_predicate == "work.status"
    ]
    assert len(conflicted) == 2, "both competing claims survive"
    for candidate in conflicted:
        assert candidate.eligibility.status == "held"
        assert "conflict.unresolved_material" in candidate.eligibility.reasons


def test_every_topology_fact_is_either_lowered_or_recorded_as_skipped(
    plan: PublicationPlan, materialized: MaterializedTopology
) -> None:
    """Nothing disappears between topology and the plan.

    A fact that is neither published nor recorded as skipped has silently
    vanished, which is the one outcome that cannot be audited afterwards.
    """
    state = materialized.state
    accounted = (
        {item.source_id for item in plan.skipped_candidates}
        | {
            entity_id
            for candidate in plan.candidates
            for entity_id in candidate.source_topology_entity_ids
        }
        | {candidate.candidate_id for candidate in plan.candidates}
    )

    for edge in state.edge_records:
        assert edge.edge_id in accounted or any(
            edge.source_id in candidate.source_topology_entity_ids for candidate in plan.candidates
        )
    for record in state.candidate_clusters:
        assert record.candidate_id in accounted
    for record in state.readiness_evidence:
        assert record.readiness_id in accounted
    for record in state.topology_reasoning_candidates:
        assert record.reasoning_candidate_id in accounted


def test_the_plan_is_deterministic(materialized: MaterializedTopology) -> None:
    policy = load_publication_policy(ROOT)
    first = build_publication_plan(materialized, policy, published_at=FIXED_TIME)
    second = build_publication_plan(materialized, policy, published_at=FIXED_TIME)
    assert first.semantic_hash == second.semantic_hash
    assert first.plan_id == second.plan_id
