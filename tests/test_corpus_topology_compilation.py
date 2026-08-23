"""Compiling a corpus: what becomes canonical, what stays candidate, and why.

One module-scoped compile of the synthetic corpus, asserted from many angles.
The corpus is built to be awkward in specific ways — a DOCX and a PPTX
contradicting each other, an ambiguous reference, a duplicate inside a ZIP — and
each test names the awkwardness it is about.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.domain.candidate import (
    AMBIGUITY_CONFLICTING_STATUS,
    AMBIGUITY_STRUCTURALLY_DISCONNECTED,
)
from l9_constellation_topology.domain.confidence import Authority, ConflictStatus
from l9_constellation_topology.domain.edge import (
    TRAVERSABLE_EDGE_TYPES,
    Direction,
    EdgeType,
)
from l9_constellation_topology.domain.readiness import FORBIDDEN_READINESS_FIELDS
from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.packets.corpus_intelligence import ExactDuplicateRelation
from l9_constellation_topology.topology.candidates import CANDIDATE_MARKER
from l9_constellation_topology.topology.impact import assess_impact
from l9_constellation_topology.topology.work_projection import WORK_REFERENCE_PREFIX
from tests.corpus_fixtures import (
    ARTIFACTS,
    FIXED_TIME,
    PROJECT_CANDIDATE,
    REPO_PLANS,
    ROOT_ENGINE,
    ROOT_PLANS,
    corpus_payload,
    write_corpus,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def state(tmp_path_factory: pytest.TempPathFactory) -> TopologyState:
    root = tmp_path_factory.mktemp("corpus-compile")
    repositories, corpus = write_corpus(root)
    result = compile_topology(
        ROOT, repositories, corpus_bundle_paths=(corpus,), created_at=FIXED_TIME
    )
    assert result.validation_receipt.status == "passed"
    return result.materialized.state


def _edges(state: TopologyState, edge_type: EdgeType) -> tuple:
    return tuple(edge for edge in state.edge_records if edge.edge_type is edge_type)


def _claim(state: TopologyState, predicate: str, obj: str):
    matches = [
        claim
        for claim in state.semantic_claims
        if claim.predicate == predicate and claim.object == obj
    ]
    assert matches, f"no claim for {predicate}={obj}"
    return matches[0]


# ── document work signals become claims ─────────────────────────────────────


@pytest.mark.parametrize(
    ("predicate", "obj"),
    [
        ("work.kind", "plan"),
        ("work.status", "WIP"),
        ("work.status", "Complete"),
        ("work.milestone", "beta"),
        ("work.task.open", "wire the executor"),
        ("work.task.completed", "spike the parser"),
    ],
)
def test_a_document_work_signal_becomes_a_semantic_claim(
    state: TopologyState, predicate: str, obj: str
) -> None:
    """One case per document format the corpus carries.

    DOCX, PPTX, PDF, XLSX, and IPYNB signals all reach the claim domain, which is
    the point of giving them the same reconciliation engine as Markdown.
    """
    claim = _claim(state, predicate, obj)
    assert claim.evidence_refs, "a claim must cite the evidence that supports it"


def test_a_claim_from_a_binary_document_cites_a_structured_locator(
    state: TopologyState,
) -> None:
    claim = _claim(state, "work.status", "WIP")
    evidence = {record.evidence_id: record for record in state.evidence}
    locators = {
        evidence[ref].source_ref.locator.kind
        for ref in claim.evidence_refs
        if evidence[ref].source_ref.locator is not None
    }
    assert locators == {"docx"}
    assert all(evidence[ref].source_ref.line_number is None for ref in claim.evidence_refs)


def test_no_evidence_in_the_compile_carries_a_fake_line_number(
    state: TopologyState,
) -> None:
    """The invariant, asserted over the whole compile rather than one record."""
    for record in state.evidence:
        locator = record.source_ref.locator
        if locator is not None and locator.kind != "line":
            assert record.source_ref.line_number is None


def test_a_docx_and_a_pptx_disagreeing_is_one_conflict_not_two_facts(
    state: TopologyState,
) -> None:
    """The reason both producers share one reconciliation engine.

    Reconciled separately these would be two internally consistent facts in two
    collections, and the contradiction — the most useful thing a corpus can
    surface — would be reported by neither.
    """
    conflicts = [conflict for conflict in state.conflicts if conflict.field == "work.status"]
    assert len(conflicts) == 1
    assert conflicts[0].values == ("Complete", "WIP")
    # Both claims survive; neither is elected.
    for obj in ("Complete", "WIP"):
        claim = _claim(state, "work.status", obj)
        assert claim.conflict_status is ConflictStatus.confirmed
        assert claim.conflict_ids == (conflicts[0].conflict_id,)


def test_a_single_valued_work_predicate_conflicts_outside_status(
    state: TopologyState,
) -> None:
    kinds = [conflict for conflict in state.conflicts if conflict.field == "work.kind"]
    assert len(kinds) == 1
    assert kinds[0].values == ("plan", "roadmap")


def test_a_set_valued_work_predicate_never_conflicts(state: TopologyState) -> None:
    assert not [
        conflict
        for conflict in state.conflicts
        if conflict.field in {"work.task.open", "work.milestone", "document.heading"}
    ]


def test_an_unsupported_work_predicate_is_preserved_as_unknown(
    state: TopologyState,
) -> None:
    claim = _claim(state, "work.vibe", "optimistic")
    assert claim.support == "unsupported"
    assert claim.projected is False
    assert any(unknown.field == "work.vibe" for unknown in state.unknowns)


# ── exact duplicates ────────────────────────────────────────────────────────


def test_byte_identical_artifacts_become_duplicate_of_edges(
    state: TopologyState,
) -> None:
    duplicates = _edges(state, EdgeType.duplicate_of)
    assert len(duplicates) == 2, "one cross-root pair and one inside an archive"
    for edge in duplicates:
        assert edge.direction is Direction.bidirectional
        assert edge.properties["content_hash"]
        assert edge.properties["duplicate_cluster_id"]
        assert edge.evidence_refs, "byte identity must cite the hash behind it"


def test_a_duplicate_edge_spans_roots(state: TopologyState) -> None:
    endpoints = {
        frozenset({edge.source_id, edge.target_id}) for edge in _edges(state, EdgeType.duplicate_of)
    }
    cross_root = frozenset({ARTIFACTS["plan_md"].artifact_id, ARTIFACTS["engine_plan"].artifact_id})
    assert cross_root in endpoints


def test_a_duplicate_inside_an_archive_is_an_ordinary_duplicate(
    state: TopologyState,
) -> None:
    endpoints = {
        frozenset({edge.source_id, edge.target_id}) for edge in _edges(state, EdgeType.duplicate_of)
    }
    in_archive = frozenset(
        {ARTIFACTS["zipped_plan"].artifact_id, ARTIFACTS["readme_plans"].artifact_id}
    )
    assert in_archive in endpoints


def test_duplicate_edge_identity_ignores_endpoint_order() -> None:
    """Byte equality is symmetric, so one relation is one edge either way round."""
    from l9_constellation_topology.topology.duplicates import build_duplicate_edges

    def relation(first: str, second: str) -> ExactDuplicateRelation:
        return ExactDuplicateRelation(
            relation_id="duplicate:x",
            duplicate_cluster_id="cluster:x",
            artifact_a_id=first,
            artifact_b_id=second,
            content_hash="sha256:" + "c" * 64,
        )

    forward = build_duplicate_edges((relation("artifact:a", "artifact:b"),))
    backward = build_duplicate_edges((relation("artifact:b", "artifact:a"),))
    assert [edge.edge_id for edge in forward] == [edge.edge_id for edge in backward]


def test_a_duplicate_cluster_emits_a_star_not_a_clique() -> None:
    """A hundred copies of a licence file must not become 4,950 edges."""
    from l9_constellation_topology.topology.duplicates import build_duplicate_edges

    members = [f"artifact:{index:03d}" for index in range(10)]
    relations = tuple(
        ExactDuplicateRelation(
            relation_id=f"duplicate:{index}",
            duplicate_cluster_id="cluster:many",
            artifact_a_id=members[0],
            artifact_b_id=member,
            content_hash="sha256:" + "d" * 64,
        )
        for index, member in enumerate(members[1:])
    )
    edges = build_duplicate_edges(relations)
    assert len(edges) == len(members) - 1
    assert len(edges) < len(members) * (len(members) - 1) // 2


def test_a_near_duplicate_never_becomes_a_duplicate_edge(state: TopologyState) -> None:
    """The single most important negative in the corpus domain.

    ``engine_v1`` and ``engine_v2`` carry a 0.94 near-duplicate score. Nothing
    about that may reach ``DUPLICATE_OF``, which means byte identity and nothing
    weaker.
    """
    near = frozenset({ARTIFACTS["engine_v1"].artifact_id, ARTIFACTS["engine_v2"].artifact_id})
    for edge in _edges(state, EdgeType.duplicate_of):
        assert frozenset({edge.source_id, edge.target_id}) != near


def test_duplicate_edges_do_not_contribute_to_dependency_impact(
    state: TopologyState,
) -> None:
    """Byte identity is not a dependency.

    Following it would make every copy of a shared licence file a dependency hop
    and connect otherwise unrelated repositories through it.
    """
    assert EdgeType.duplicate_of not in TRAVERSABLE_EDGE_TYPES
    duplicate = _edges(state, EdgeType.duplicate_of)[0]
    impact = assess_impact(
        duplicate.source_id, state.edge_records, direction="both", maximum_depth=10
    )
    assert duplicate.target_id not in impact.affected_entity_ids


def test_duplicate_edges_are_reachable_when_explicitly_requested(
    state: TopologyState,
) -> None:
    """Excluded by default, never hidden: asking for them is a different question."""
    duplicate = _edges(state, EdgeType.duplicate_of)[0]
    impact = assess_impact(
        duplicate.source_id,
        state.edge_records,
        direction="both",
        maximum_depth=10,
        edge_types={EdgeType.duplicate_of},
    )
    assert duplicate.target_id in impact.affected_entity_ids


def test_duplicate_edges_generate_no_runtime_flows(state: TopologyState) -> None:
    duplicate_ids = {edge.edge_id for edge in _edges(state, EdgeType.duplicate_of)}
    for flow in state.flow_records:
        assert flow.flow_id not in duplicate_ids
        assert flow.flow_type == "repository-dependency"


# ── explicit work relations ─────────────────────────────────────────────────


def test_an_exactly_resolved_dependency_projects_to_depends_on(
    state: TopologyState,
) -> None:
    matches = [
        edge
        for edge in _edges(state, EdgeType.depends_on)
        if edge.properties.get("assertion_predicate") == "work.depends_on"
    ]
    assert len(matches) == 1
    assert matches[0].target_id == ARTIFACTS["engine_main"].artifact_id
    assert matches[0].properties["target_resolution"] == "exact-artifact"


def test_an_exactly_resolved_blocker_projects_to_blocked_by(
    state: TopologyState,
) -> None:
    matches = _edges(state, EdgeType.blocked_by)
    assert len(matches) == 1
    assert matches[0].target_id == ARTIFACTS["engine_v1"].artifact_id


def test_a_superseded_by_claim_projects_in_the_taxonomy_s_direction(
    state: TopologyState,
) -> None:
    """ "A superseded_by B" is the edge "B SUPERSEDES A".

    Keeping the subject on the left would state the opposite fact.
    """
    matches = [
        edge
        for edge in _edges(state, EdgeType.supersedes)
        if edge.properties.get("assertion_predicate") == "work.superseded_by"
    ]
    assert len(matches) == 1
    assert matches[0].source_id == ARTIFACTS["engine_v2"].artifact_id
    assert matches[0].target_id == REPO_PLANS


def test_an_ambiguous_reference_resolves_to_nothing_and_says_so(
    state: TopologyState,
) -> None:
    """Two artifacts sit at exactly ``README.md``, so the reference is ambiguous.

    An ambiguous reference is no evidence at all: it becomes an explicitly
    external endpoint plus an unknown naming both possibilities, never a guess.
    """
    ambiguous = [
        edge
        for edge in _edges(state, EdgeType.references)
        if edge.properties.get("target_resolution") == "ambiguous"
    ]
    assert len(ambiguous) == 1
    assert ambiguous[0].target_id.startswith(WORK_REFERENCE_PREFIX)
    # What the ambiguity was between is a fact about the *target*, so it lives on
    # the target node rather than on the relation that happened to reach it.
    node = next(
        record
        for record in state.graph_records
        if record.record_type == "node" and record.entity_id == ambiguous[0].target_id
    )
    assert len(node.properties["ambiguous_matches"]) == 2
    assert node.properties["observed_in_corpus"] is False
    assert any(unknown.field == "work.references" for unknown in state.unknowns), (
        "an ambiguous target must be recorded as unknown"
    )


def test_an_unresolvable_reference_still_records_the_declaration(
    state: TopologyState,
) -> None:
    """The document did say it. What is unknown is only what it pointed at."""
    unresolved = [
        edge
        for edge in _edges(state, EdgeType.references)
        if edge.properties.get("target_resolution") == "unresolved"
    ]
    assert len(unresolved) == 1
    assert unresolved[0].target_id.startswith(WORK_REFERENCE_PREFIX)


def test_an_external_work_reference_is_labelled_as_never_observed(
    state: TopologyState,
) -> None:
    nodes = {
        record.entity_id: record for record in state.graph_records if record.record_type == "node"
    }
    for edge in _edges(state, EdgeType.references):
        if edge.target_id.startswith(WORK_REFERENCE_PREFIX):
            assert nodes[edge.target_id].properties["observed_in_corpus"] is False


# ── corpus and root scope ───────────────────────────────────────────────────


def test_the_corpus_and_its_roots_are_first_class_records(
    state: TopologyState,
) -> None:
    assert len(state.corpus_records) == 1
    assert {root.root_id for root in state.root_records} == {ROOT_PLANS, ROOT_ENGINE}
    corpus = state.corpus_records[0]
    assert corpus.corpus_source_snapshot_id != corpus.corpus_analysis_id
    assert corpus.evidence_refs


def test_corpus_scope_is_joined_by_containment(state: TopologyState) -> None:
    contains = {(edge.source_id, edge.target_id) for edge in _edges(state, EdgeType.contains)}
    corpus_id = state.corpus_records[0].corpus_id
    assert (corpus_id, ROOT_PLANS) in contains
    assert (ROOT_PLANS, REPO_PLANS) in contains


def test_no_absolute_path_reaches_topology_identity(state: TopologyState) -> None:
    for record in state.root_records:
        assert not record.root_id.startswith("/")
        assert ":\\" not in record.root_id
    for record in state.artifact_records:
        assert not record.source_path.startswith("/")


# ── candidates stay candidates ──────────────────────────────────────────────


def test_candidate_relations_and_clusters_are_first_class(
    state: TopologyState,
) -> None:
    assert len(state.candidate_relations) == 2
    assert {record.candidate_type for record in state.candidate_clusters} == {
        "TOPIC_CANDIDATE",
        "PROJECT_CANDIDATE",
        "CONSOLIDATION_CANDIDATE",
    }


def test_every_candidate_carries_candidate_authority(state: TopologyState) -> None:
    """However strong the producer's class, the authority is where it came from."""
    for record in (*state.candidate_relations, *state.candidate_clusters):
        assert record.confidence.authority is Authority.candidate


def test_no_candidate_reaches_the_canonical_edge_domain(state: TopologyState) -> None:
    """The containment that matters, asserted structurally.

    Candidates live in their own state fields; every canonical consumer reads
    ``edge_records``. A candidate identity appearing there would mean the
    separation had been breached.
    """
    candidate_ids = {record.relation_id for record in state.candidate_relations} | {
        record.candidate_id for record in state.candidate_clusters
    }
    for edge in state.edge_records:
        assert edge.edge_id not in candidate_ids
        assert edge.source_id not in candidate_ids
        assert edge.target_id not in candidate_ids


def test_a_project_candidate_creates_no_member_of_edge(state: TopologyState) -> None:
    """ "These files are one project" is precisely what a candidate must not assert."""
    assert not _edges(state, EdgeType.member_of)


def test_candidate_graph_records_are_labelled_and_marked(state: TopologyState) -> None:
    projected = [record for record in state.graph_records if record.label.startswith("Candidate")]
    assert projected
    for record in projected:
        assert record.properties[CANDIDATE_MARKER] is False
        # Emitted as nodes, never edges: the graph's edge records are built from
        # `edge_records`, and an edge-shaped candidate would be one filter away
        # from being traversed as though it were canonical.
        assert record.record_type == "node"


def test_a_topic_candidate_cannot_affect_dependency_impact(
    state: TopologyState,
) -> None:
    topic = next(
        record for record in state.candidate_clusters if record.candidate_type == "TOPIC_CANDIDATE"
    )
    first, second = topic.member_entity_ids[0], topic.member_entity_ids[1]
    impact = assess_impact(first, state.edge_records, direction="both", maximum_depth=10)
    assert second not in impact.affected_entity_ids


def test_candidates_do_not_enter_maturity_or_risk(state: TopologyState) -> None:
    candidate_ids = {record.candidate_id for record in state.candidate_clusters}
    assert not {item.subject_id for item in state.maturity} & candidate_ids
    assert not {item.subject_id for item in state.risks} & candidate_ids


# ── structural enrichment ───────────────────────────────────────────────────


def test_a_candidate_is_enriched_with_structure_topology_measured(
    state: TopologyState,
) -> None:
    project = next(
        record
        for record in state.candidate_clusters
        if record.candidate_id == PROJECT_CANDIDATE.candidate_id
    )
    evidence = project.structural_evidence
    assert evidence.member_count == len(PROJECT_CANDIDATE.member_artifact_ids)
    assert evidence.root_count == 2, "the candidate spans both roots"
    assert evidence.work_status_distribution == {"Complete": 1, "WIP": 1}
    assert evidence.conflicting_status_count >= 1


def test_a_structural_contradiction_lowers_a_candidate_but_never_raises_it(
    state: TopologyState,
) -> None:
    """The asymmetry the enrichment pass is built around.

    The producer called this project candidate ``strong``. Its members declare
    incompatible statuses, so topology lowers it. Nothing anywhere raises a
    candidate: corroboration was already available to the profile that assigned
    the class.
    """
    project = next(
        record
        for record in state.candidate_clusters
        if record.candidate_id == PROJECT_CANDIDATE.candidate_id
    )
    assert PROJECT_CANDIDATE.confidence_class == "strong"
    assert project.confidence_class == "weak"
    assert AMBIGUITY_CONFLICTING_STATUS in project.ambiguity_flags


def test_a_candidate_with_no_internal_links_is_flagged_not_rejected(
    state: TopologyState,
) -> None:
    disconnected = [
        record
        for record in state.candidate_clusters
        if AMBIGUITY_STRUCTURALLY_DISCONNECTED in record.ambiguity_flags
    ]
    assert disconnected, "the corpus contains a candidate nothing structurally links"
    for record in disconnected:
        assert record.structural_evidence.structural_support_count == 0
        # Flagged, still carried. Nothing in the corpus may connect two documents
        # that are unmistakably about one project.
        assert record.member_entity_ids


# ── readiness ───────────────────────────────────────────────────────────────


def test_readiness_evidence_is_first_class_and_attached(state: TopologyState) -> None:
    assert len(state.readiness_evidence) == 1
    readiness = state.readiness_evidence[0]
    assert readiness.source_artifact_count == 9
    assert readiness.test_artifact_count == 4
    project = next(
        record
        for record in state.candidate_clusters
        if record.candidate_id == PROJECT_CANDIDATE.candidate_id
    )
    assert project.readiness_evidence_ref == readiness.readiness_id


def test_readiness_computes_no_score_priority_or_completion(
    state: TopologyState,
) -> None:
    """Asserted against the record's own field set, so adding one fails here."""
    fields = set(state.readiness_evidence[0].model_dump(mode="json"))
    assert not fields & FORBIDDEN_READINESS_FIELDS


def test_readiness_never_claims_source_authority(state: TopologyState) -> None:
    """Counting test files is deterministic; it is not a repository's own claim."""
    assert state.readiness_evidence[0].confidence.authority is not Authority.source


# ── reasoning handoff ───────────────────────────────────────────────────────


def test_every_candidate_is_routed_including_the_ones_going_nowhere(
    state: TopologyState,
) -> None:
    routed = {row.candidate_id for row in state.topology_reasoning_candidates}
    assert routed == {record.candidate_id for record in state.candidate_clusters}


def test_the_router_records_both_decisions(state: TopologyState) -> None:
    """A disagreement between producer and topology is the thing worth auditing."""
    project = next(
        row
        for row in state.topology_reasoning_candidates
        if row.candidate_id == PROJECT_CANDIDATE.candidate_id
    )
    assert project.upstream_recommended_reasoning_type == "PROJECT_IDENTITY_ADJUDICATION"
    assert project.topology_recommended_reasoning_type == "CONFLICT_RESOLUTION_ANALYSIS"
    assert project.reason


def test_the_router_escalates_on_structural_evidence(state: TopologyState) -> None:
    """The producer said ``NONE`` for the topic candidate; its members conflict."""
    topic = next(
        row for row in state.topology_reasoning_candidates if row.candidate_id == "candidate:topic"
    )
    assert topic.upstream_recommended_reasoning_type == "NONE"
    assert topic.topology_recommended_reasoning_type != "NONE"
    assert topic.escalated
    assert topic.structural_signals


def test_a_reasoning_candidate_carries_a_bounded_neighborhood(
    state: TopologyState,
) -> None:
    """One explicit hop. An unbounded neighbourhood is the corpus."""
    entity_ids = (
        {record.artifact_id for record in state.artifact_records}
        | {record.repository_id for record in state.repository_records}
        | {record.entity_id for record in state.graph_records}
    )
    for row in state.topology_reasoning_candidates:
        assert len(row.bounded_neighborhood_refs) < len(entity_ids)
        for reference in row.bounded_neighborhood_refs:
            assert reference in entity_ids


def test_the_router_de_escalates_a_wholly_duplicated_group() -> None:
    """A group whose members are byte-identical has nothing to adjudicate."""
    from l9_constellation_topology.domain.candidate import CandidateClusterRecord
    from l9_constellation_topology.packets.corpus_intelligence import (
        ReasoningCandidateRequest,
    )
    from l9_constellation_topology.topology.candidates import candidate_confidence
    from l9_constellation_topology.topology.duplicates import build_duplicate_edges
    from l9_constellation_topology.topology.reasoning_router import route_candidate

    edges = build_duplicate_edges(
        (
            ExactDuplicateRelation(
                relation_id="duplicate:only",
                duplicate_cluster_id="cluster:only",
                artifact_a_id="artifact:a",
                artifact_b_id="artifact:b",
                content_hash="sha256:" + "e" * 64,
            ),
        )
    )
    cluster = CandidateClusterRecord(
        candidate_id="candidate:copies",
        candidate_type="CONSOLIDATION_CANDIDATE",
        member_entity_ids=("artifact:a", "artifact:b"),
        confidence_class="strong",
        analysis_profile="fusion/1.0.0",
        confidence=candidate_confidence("strong"),
    )
    routed = route_candidate(
        cluster,
        upstream=ReasoningCandidateRequest(
            reasoning_candidate_id="upstream:copies",
            candidate_id=cluster.candidate_id,
            recommended_reasoning_type="CONSOLIDATION_ANALYSIS",
        ),
        edges=edges,
        conflicts=(),
        unknowns=(),
    )
    assert routed.topology_recommended_reasoning_type == "NONE"
    assert routed.deescalated


def test_routing_is_deterministic(tmp_path: Path) -> None:
    """Same inputs, same queue — including the identities of its rows."""
    repositories, corpus = write_corpus(tmp_path / "run")
    first = compile_topology(
        ROOT, repositories, corpus_bundle_paths=(corpus,), created_at=FIXED_TIME
    ).materialized.state
    second = compile_topology(
        ROOT, repositories, corpus_bundle_paths=(corpus,), created_at=FIXED_TIME
    ).materialized.state
    assert first.topology_reasoning_candidates == second.topology_reasoning_candidates


# ── backward compatibility ──────────────────────────────────────────────────


def test_a_compile_with_no_corpus_input_leaves_every_corpus_domain_empty(
    tmp_path: Path,
) -> None:
    """The 1.0.0 behaviour, unchanged."""
    repositories, _ = write_corpus(tmp_path / "rmp-only")
    result = compile_topology(ROOT, repositories, created_at=FIXED_TIME)
    state = result.materialized.state
    assert result.validation_receipt.status == "passed"
    assert state.corpus_records == ()
    assert state.root_records == ()
    assert state.candidate_relations == ()
    assert state.candidate_clusters == ()
    assert state.readiness_evidence == ()
    assert state.topology_reasoning_candidates == ()
    assert not [edge for edge in state.edge_records if edge.edge_type is EdgeType.duplicate_of]


def test_a_corpus_packet_analysing_an_uncompiled_root_is_refused(
    tmp_path: Path,
) -> None:
    """A corpus may cover a subset of the compile; it may not exceed it."""
    repositories, corpus = write_corpus(tmp_path / "mismatch")
    with pytest.raises(ValueError, match="absent from this compile"):
        compile_topology(
            ROOT,
            repositories[:1],
            corpus_bundle_paths=(corpus,),
            created_at=FIXED_TIME,
        )


def test_a_corrupt_corpus_packet_fails_the_compile_closed(tmp_path: Path) -> None:
    """No partial topology. Compiling the resolvable subset would hide the defect."""
    from l9_constellation_topology.packets.corpus_validator import (
        CorpusIntelligenceValidationError,
    )

    stray = ExactDuplicateRelation(
        relation_id="duplicate:stray",
        duplicate_cluster_id="cluster:stray",
        artifact_a_id=ARTIFACTS["plan_md"].artifact_id,
        artifact_b_id="artifact:never-observed",
        content_hash="sha256:" + "f" * 64,
    )
    repositories, corpus = write_corpus(
        tmp_path / "corrupt",
        payload=corpus_payload(exact_duplicate_relations=(stray,)),
    )
    with pytest.raises(CorpusIntelligenceValidationError):
        compile_topology(ROOT, repositories, corpus_bundle_paths=(corpus,), created_at=FIXED_TIME)
