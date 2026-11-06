"""Conflict-aware canonical projection and resolution-aware impact (ADR-0035).

Canonical relations must not outrun their evidence: a conflicting claim stays a
claim and a conflict, and an impact query separates resolved dependency paths
from declared references whose target nothing resolved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from l9_constellation_topology.cli import RESOLUTION_AWARE_IMPACT_INTERPRETATION, run
from l9_constellation_topology.domain.assessment import ImpactIndex
from l9_constellation_topology.domain.claim import SemanticClaimRecord
from l9_constellation_topology.domain.confidence import ConflictStatus
from l9_constellation_topology.domain.edge import EdgeRecord, EdgeType
from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.packets.repository_model import (
    AssertionSourceRange,
    RepositoryModelAssertion,
)
from l9_constellation_topology.reconciliation import predicate_policy_hash, predicate_policy_view
from l9_constellation_topology.topology.claim_projection import (
    eligible_for_canonical_projection,
    project_claims,
    projection_ineligibility,
)
from l9_constellation_topology.topology.claim_view import ClaimQuery, SemanticClaimIndex
from l9_constellation_topology.topology.impact import (
    DEPENDENCY_EDGE_TYPES,
    assess_impact,
    dependency_target_resolution,
    edge_is_resolved,
)
from l9_constellation_topology.topology.work_projection import project_work_relations
from tests.test_claim_view import _state as reconciled_state

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests/fixtures/repository_model_packets/l9-assertion-sample"
REPO = "repo:sample"
#: Entities a packet observed, for resolution-aware tests that need none in particular.
OBSERVED = frozenset({REPO})
PLAN = "artifact:sample:docs-plan-md"


def _assertion(
    predicate: str,
    obj: str,
    *,
    subject: str = REPO,
    path: str = "README.md",
    line: int = 1,
    authority: str = "source",
) -> RepositoryModelAssertion:
    return RepositoryModelAssertion(
        assertion_id=f"assertion:{predicate}:{obj}:{path}:{line}",
        subject_id=subject,
        predicate=predicate,
        object=obj,
        source_path=path,
        source_range=AssertionSourceRange(start_line=line, end_line=line),
        evidence_excerpt=f"{predicate}: {obj}",
        source_content_hash="sha256:" + "a" * 64,
        extractor_id="fixture/v1",
        evidence_class="declared",
        authority=authority,
        confidence="high",
    )


def _reconciled(assertions: tuple[RepositoryModelAssertion, ...]) -> TopologyState:
    return reconciled_state(assertions)


def _claim(state: TopologyState, predicate: str, obj: str) -> SemanticClaimRecord:
    return next(c for c in state.semantic_claims if c.predicate == predicate and c.object == obj)


# ── Case G: conflicting projectable declarations ──────────────────────────────


def test_case_g_conflicting_successors_project_no_supersession_edge() -> None:
    state = _reconciled(
        (
            _assertion("repository.replaced_by", "next-repo", line=2),
            _assertion("repository.replaced_by", "other-repo", path="docs/STATUS.md", line=5),
        )
    )
    assert len(state.conflicts) == 1
    assert len(state.semantic_claims) == 2
    for claim in state.semantic_claims:
        assert claim.conflict_status is ConflictStatus.confirmed
        assert projection_ineligibility(claim) == "conflicted"
    projection = project_claims(state.semantic_claims)
    assert projection.edges == ()
    assert projection.nodes == ()
    assert projection.entities_by_claim == {}


def test_an_unconflicted_successor_still_projects() -> None:
    state = _reconciled((_assertion("repository.replaced_by", "next-repo"),))
    projection = project_claims(state.semantic_claims)
    assert [edge.edge_type for edge in projection.edges] == [EdgeType.supersedes]


def test_a_possible_conflict_also_withholds_projection() -> None:
    state = _reconciled((_assertion("repository.replaced_by", "next-repo"),))
    claim = state.semantic_claims[0].model_copy(update={"conflict_status": ConflictStatus.possible})
    assert projection_ineligibility(claim) == "conflicted"
    assert project_claims((claim,)).edges == ()


def test_no_global_authority_gate_sits_at_the_projection_boundary() -> None:
    """Freeze D5a: authority is decided inside each projector, not globally.

    The existing package projector has no authority requirement of its own, so
    an unconflicted candidate-authority dependency claim projects exactly as it
    did before ADR-0035; the claim's confidence travels with the edge.
    """
    state = _reconciled((_assertion("package.dependency", "fastapi", authority="candidate"),))
    claim = state.semantic_claims[0]
    assert projection_ineligibility(claim) is None
    edges = project_claims(state.semantic_claims).edges
    assert [edge.target_id for edge in edges] == ["package:fastapi"]
    assert edges[0].confidence.authority == claim.authority


def test_the_conflict_rule_is_bound_into_the_predicate_policy_hash() -> None:
    """F12: changing which conflict states withhold projection moves packet identity."""
    import l9_constellation_topology.reconciliation.predicates as predicates

    view = predicate_policy_view()
    assert view["version"] == "1.4.0"
    assert view["projection_eligibility"] == {
        "decided_at": "individual-claim",
        "withheld_conflict_statuses": ["confirmed", "possible"],
        "withheld_when_conflict_ids_present": True,
        "relation_authority": "decided-inside-each-projector",
    }
    before = predicate_policy_hash()
    original = predicates.PROJECTION_WITHHELD_CONFLICT_STATUSES
    try:
        predicates.PROJECTION_WITHHELD_CONFLICT_STATUSES = frozenset({ConflictStatus.confirmed})
        assert predicate_policy_hash() != before
    finally:
        predicates.PROJECTION_WITHHELD_CONFLICT_STATUSES = original
    assert predicate_policy_hash() == before


def test_compiled_packets_carry_the_bound_projection_policy() -> None:
    from datetime import UTC, datetime

    from l9_constellation_topology.compiler import compile_topology

    result = compile_topology(ROOT, (SAMPLE,), created_at=datetime(2026, 7, 21, tzinfo=UTC))
    assert result.materialized.packet.policy_hashes["assertion_predicates"] == (
        predicate_policy_hash()
    )


def test_declaration_only_predicates_report_their_own_reason() -> None:
    state = _reconciled((_assertion("meta.managed.governance.owner", "platform"),))
    assert projection_ineligibility(state.semantic_claims[0]) == "predicate-not-projectable"
    assert not eligible_for_canonical_projection(state.semantic_claims[0])


def test_the_claim_view_says_why_projection_was_withheld() -> None:
    state = _reconciled(
        (
            _assertion("repository.replaced_by", "next-repo", line=2),
            _assertion("repository.replaced_by", "other-repo", line=3),
            _assertion("meta.managed.governance.owner", "platform", line=4),
        )
    )
    index = SemanticClaimIndex.from_state(state)
    withheld = index.query(ClaimQuery(predicate="repository.replaced_by"))
    assert {view.projection_status for view in withheld.claims} == {"withheld"}
    assert {view.projection_withheld_reason for view in withheld.claims} == {"conflicted"}
    owner = index.query(ClaimQuery(predicate="meta.managed.governance.owner")).claims[0]
    assert owner.projection_status == "not-projectable"
    assert owner.projection_withheld_reason is None


def test_a_conflicted_work_claim_projects_no_work_edge() -> None:
    state = _reconciled((_assertion("work.depends_on", "engine/main.py", subject=PLAN),))
    conflicted = state.semantic_claims[0].model_copy(
        update={"conflict_status": ConflictStatus.confirmed, "conflict_ids": ("conflict:x",)}
    )
    assert project_work_relations((conflicted,), ()).edges == ()
    assert len(project_work_relations(state.semantic_claims, ()).edges) == 1


# ── Case E / Case H: resolution-aware impact ──────────────────────────────────


def _unresolved_dependency_edges() -> tuple[EdgeRecord, ...]:
    """A plan declares a dependency nothing resolves, plus an external package."""
    state = _reconciled(
        (
            _assertion("work.depends_on", "engine/missing.py", subject=PLAN, path="docs/plan.md"),
            _assertion("package.dependency", "fastapi"),
        )
    )
    work = project_work_relations(state.semantic_claims, ())
    claims = project_claims(state.semantic_claims)
    return work.edges + claims.edges


def test_case_e_an_unresolved_target_is_reported_not_traversed() -> None:
    edges = _unresolved_dependency_edges()
    work_edge = next(edge for edge in edges if edge.source_id == PLAN)
    assert work_edge.properties["target_resolution"] == "unresolved"
    assert not edge_is_resolved(work_edge, OBSERVED)

    aware = assess_impact(PLAN, edges, direction="upstream", resolution_aware=True)
    assert aware.affected_entity_ids == ()
    assert aware.paths == ()
    assert aware.unresolved_edge_ids == (work_edge.edge_id,)

    # The established generic reachability is unchanged.
    generic = assess_impact(PLAN, edges, direction="upstream")
    assert generic.affected_entity_ids == (work_edge.target_id,)
    assert generic.unresolved_edge_ids == ()


def test_case_h_an_external_package_dependency_stays_resolved() -> None:
    edges = _unresolved_dependency_edges()
    package_edge = next(edge for edge in edges if edge.target_id == "package:fastapi")
    assert edge_is_resolved(package_edge, frozenset())
    assert dependency_target_resolution(package_edge, frozenset()) == "resolved-external-package"
    aware = assess_impact(REPO, edges, direction="upstream", resolution_aware=True)
    assert aware.affected_entity_ids == ("package:fastapi",)
    assert aware.unresolved_edge_ids == ()
    downstream = assess_impact("package:fastapi", edges, resolution_aware=True)
    assert downstream.affected_entity_ids == (REPO,)


def test_an_ambiguous_target_is_unresolved_for_impact() -> None:
    edges = _unresolved_dependency_edges()
    work_edge = next(edge for edge in edges if edge.source_id == PLAN)
    ambiguous = work_edge.model_copy(
        update={"properties": {**work_edge.properties, "target_resolution": "ambiguous"}}
    )
    assert not edge_is_resolved(ambiguous, OBSERVED)
    resolved = work_edge.model_copy(
        update={"properties": {**work_edge.properties, "target_resolution": "exact-artifact"}}
    )
    assert edge_is_resolved(resolved, frozenset())


def test_resolution_aware_traversal_stops_at_the_unresolved_hop_only() -> None:
    """A resolved path is still walked past the node that also declares an unresolved one."""
    edges = _unresolved_dependency_edges()
    work_edge = next(edge for edge in edges if edge.source_id == PLAN)
    bridge = work_edge.model_copy(
        update={
            "edge_id": "edge:bridge",
            "source_id": "repo:caller",
            "target_id": PLAN,
            "edge_type": EdgeType.depends_on,
            "properties": {"target_resolution": "exact-artifact"},
        }
    )
    aware = assess_impact(
        "repo:caller", (*edges, bridge), direction="upstream", resolution_aware=True
    )
    assert aware.affected_entity_ids == (PLAN,)
    assert aware.paths == (("repo:caller", PLAN),)
    assert aware.unresolved_edge_ids == (work_edge.edge_id,)


def _bare_edge(edge_id: str, source: str, target: str, edge_type: EdgeType) -> EdgeRecord:
    """An edge carrying no producer resolution evidence, as the graph builder emits."""
    template = _unresolved_dependency_edges()[0]
    return template.model_copy(
        update={
            "edge_id": edge_id,
            "source_id": source,
            "target_id": target,
            "edge_type": edge_type,
            "properties": {},
        }
    )


def test_an_absent_target_resolution_is_not_read_as_resolved() -> None:
    """Freeze D5b: no producer evidence means unresolved, never exact-artifact."""
    edge = _bare_edge("edge:bare", REPO, "repo:never-observed", EdgeType.depends_on)
    assert dependency_target_resolution(edge, OBSERVED) == "unresolved-no-producer-evidence"
    aware = assess_impact(REPO, (edge,), direction="upstream", resolution_aware=True)
    assert aware.affected_entity_ids == ()
    assert aware.unresolved_edge_ids == ("edge:bare",)
    # Generic reachability still walks it: the two readings stay distinguishable.
    assert assess_impact(REPO, (edge,), direction="upstream").affected_entity_ids == (
        "repo:never-observed",
    )


def test_a_graph_builder_dependency_on_an_observed_repository_is_resolved() -> None:
    edge = _bare_edge("edge:upstream", REPO, "repo:other", EdgeType.depends_on)
    observed = frozenset({REPO, "repo:other"})
    assert dependency_target_resolution(edge, observed) == "resolved-observed-entity"
    aware = assess_impact(
        REPO, (edge,), direction="upstream", resolution_aware=True, observed_entity_ids=observed
    )
    assert aware.affected_entity_ids == ("repo:other",)
    assert aware.unresolved_edge_ids == ()


def test_resolution_aware_impact_walks_dependency_relations_only() -> None:
    contains = _bare_edge("edge:contains", REPO, "artifact:sample:readme", EdgeType.contains)
    documented = _bare_edge("edge:doc", REPO, "artifact:sample:docs", EdgeType.documented_by)
    governed = _bare_edge("edge:gov", REPO, "artifact:sample:adr", EdgeType.governed_by)
    observed = frozenset(
        {REPO, "artifact:sample:readme", "artifact:sample:docs", "artifact:sample:adr"}
    )
    edges = (contains, documented, governed)
    aware = assess_impact(
        REPO, edges, direction="upstream", resolution_aware=True, observed_entity_ids=observed
    )
    assert aware.affected_entity_ids == ()
    assert aware.unresolved_edge_ids == ()
    assert len(assess_impact(REPO, edges, direction="upstream").affected_entity_ids) == 3
    assert frozenset({EdgeType.depends_on, EdgeType.blocked_by}) == DEPENDENCY_EDGE_TYPES


def test_resolution_aware_impact_refuses_non_dependency_edge_types() -> None:
    with pytest.raises(ValueError, match="dependency relations only"):
        assess_impact(REPO, (), resolution_aware=True, edge_types={EdgeType.contains})
    narrowed = assess_impact(REPO, (), resolution_aware=True, edge_types={EdgeType.blocked_by})
    assert narrowed.affected_entity_ids == ()


@pytest.mark.parametrize("flag", [[], ["--resolution-aware"]])
def test_impact_cli_accepts_the_resolution_aware_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], flag: list[str]
) -> None:
    bundle = tmp_path / "bundle"
    args = ["compile-packet", "--repo-root", str(ROOT), "--input-bundle", str(SAMPLE)]
    assert run([*args, "--out", str(bundle)]) == 0
    capsys.readouterr()
    impact = ["impact", "--input-bundle", str(bundle), "--entity", "repo:l9-assertion-sample"]
    assert run([*impact, "--direction", "upstream", *flag]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["subject_id"] == "repo:l9-assertion-sample"
    assert "unresolved_edge_ids" in output
    if flag:
        # The opt-in reading names itself; the rest is exactly an ImpactIndex.
        assert output.pop("interpretation") == RESOLUTION_AWARE_IMPACT_INTERPRETATION
    else:
        # Generic reachability keeps its established output: a bare ImpactIndex.
        assert "interpretation" not in output
    ImpactIndex.model_validate(output)
