"""The reasoning router's decision table, exercised branch by branch.

`test_corpus_topology_compilation` covers routing as it emerges from a real
compile. This module drives the router directly, because several signals need a
topology shape the fixture corpus does not happen to produce, and constructing a
whole corpus per branch would obscure what each case is actually about.

Nothing here calls a model. That is the property under test as much as the
routing itself: the router is a pure function of recorded structure.
"""

from __future__ import annotations

import pytest

from l9_constellation_topology.domain.assessment import ConflictRecord, UnknownRecord
from l9_constellation_topology.domain.candidate import (
    AMBIGUITY_CONFLICTING_STATUS,
    AMBIGUITY_STRUCTURALLY_DISCONNECTED,
    CandidateClusterRecord,
    CandidateStructuralEvidence,
)
from l9_constellation_topology.domain.edge import Direction, EdgeRecord, EdgeType
from l9_constellation_topology.domain.reasoning import (
    SIGNAL_AMBIGUOUS_SUPERSESSION,
    SIGNAL_CONFIRMED_CLAIM_CONFLICT,
    SIGNAL_EXACT_DUPLICATE_ONLY,
    SIGNAL_EXPLAINED_BY_EXACT_RELATION,
    SIGNAL_SPANS_ROOTS_AND_VERSIONS,
    SIGNAL_STRUCTURALLY_DISCONNECTED,
    SIGNAL_UNRESOLVED_EXACT_REFERENCE,
)
from l9_constellation_topology.packets.corpus_intelligence import (
    ExactDuplicateRelation,
    ReasoningCandidateRequest,
)
from l9_constellation_topology.topology.candidates import candidate_confidence
from l9_constellation_topology.topology.duplicates import build_duplicate_edges
from l9_constellation_topology.topology.reasoning_router import route_candidate
from l9_constellation_topology.topology.work_projection import AMBIGUOUS_TARGET_REASON

MEMBERS = ("artifact:a", "artifact:b")


def cluster(
    candidate_type: str = "PROJECT_CANDIDATE",
    *,
    flags: tuple[str, ...] = (),
    cross_root: bool = False,
    supersessions: int = 0,
    members: tuple[str, ...] = MEMBERS,
) -> CandidateClusterRecord:
    return CandidateClusterRecord(
        candidate_id=f"candidate:{candidate_type.lower()}",
        candidate_type=candidate_type,  # type: ignore[arg-type]
        member_entity_ids=members,
        confidence_class="moderate",
        ambiguity_flags=flags,
        cross_root=cross_root,
        analysis_profile="fusion/1.0.0",
        structural_evidence=CandidateStructuralEvidence(
            member_count=len(members),
            internal_supersession_count=supersessions,
        ),
        confidence=candidate_confidence("moderate"),
    )


def supersession(resolution: str, *, inside: bool = True) -> EdgeRecord:
    target = MEMBERS[1] if inside else "artifact:elsewhere"
    return EdgeRecord(
        edge_id=f"edge:supersedes:{resolution}:{target}",
        source_id=MEMBERS[0],
        target_id=target,
        edge_type=EdgeType.supersedes,
        direction=Direction.outbound,
        properties={"target_resolution": resolution},
    )


def request(reasoning_type: str) -> ReasoningCandidateRequest:
    return ReasoningCandidateRequest(
        reasoning_candidate_id="upstream:x",
        candidate_id="candidate:project_candidate",
        recommended_reasoning_type=reasoning_type,  # type: ignore[arg-type]
    )


def duplicates_over(members: tuple[str, ...]) -> tuple[EdgeRecord, ...]:
    return build_duplicate_edges(
        tuple(
            ExactDuplicateRelation(
                relation_id=f"duplicate:{index}",
                duplicate_cluster_id="cluster:one",
                artifact_a_id=members[0],
                artifact_b_id=member,
                content_hash="sha256:" + "a" * 64,
            )
            for index, member in enumerate(members[1:])
        )
    )


# ── escalation ──────────────────────────────────────────────────────────────


def test_a_confirmed_conflict_routes_to_conflict_resolution() -> None:
    """A conflict beats every other signal: it is the question to answer."""
    routed = route_candidate(
        cluster(),
        upstream=request("PROJECT_IDENTITY_ADJUDICATION"),
        edges=(),
        conflicts=(
            ConflictRecord(
                conflict_id="conflict:1",
                subject_id=MEMBERS[0],
                field="work.status",
                values=("Complete", "WIP"),
            ),
        ),
        unknowns=(),
    )
    assert routed.topology_recommended_reasoning_type == "CONFLICT_RESOLUTION_ANALYSIS"
    assert SIGNAL_CONFIRMED_CLAIM_CONFLICT in routed.structural_signals
    assert routed.conflict_refs == ("conflict:1",)


def test_an_ambiguous_reference_escalates() -> None:
    """A reference that matched several artifacts is a question a reasoner can take."""
    routed = route_candidate(
        cluster(),
        upstream=None,
        edges=(),
        conflicts=(),
        unknowns=(
            UnknownRecord(
                unknown_id="unknown:1",
                subject_id=MEMBERS[0],
                field="work.references",
                reason=AMBIGUOUS_TARGET_REASON,
            ),
        ),
    )
    assert SIGNAL_UNRESOLVED_EXACT_REFERENCE in routed.structural_signals
    assert routed.topology_recommended_reasoning_type != "NONE"
    assert routed.escalated


def test_an_unrelated_unknown_does_not_escalate() -> None:
    """Only an *ambiguous target* escalates, not any unknown on a member.

    An unsupported predicate is an unknown too, and it says nothing about
    whether the grouping needs adjudicating.
    """
    routed = route_candidate(
        cluster(),
        upstream=request("NONE"),
        edges=(),
        conflicts=(),
        unknowns=(
            UnknownRecord(
                unknown_id="unknown:2",
                subject_id=MEMBERS[0],
                field="work.vibe",
                reason="predicate has no declared rule",
            ),
        ),
    )
    assert SIGNAL_UNRESOLVED_EXACT_REFERENCE not in routed.structural_signals
    assert routed.topology_recommended_reasoning_type == "NONE"


@pytest.mark.parametrize("resolution", ["ambiguous", "unresolved"])
def test_a_supersession_that_did_not_resolve_escalates(resolution: str) -> None:
    routed = route_candidate(
        cluster(),
        upstream=None,
        edges=(supersession(resolution, inside=False),),
        conflicts=(),
        unknowns=(),
    )
    assert SIGNAL_AMBIGUOUS_SUPERSESSION in routed.structural_signals
    assert routed.escalated


def test_a_structurally_disconnected_project_candidate_escalates() -> None:
    routed = route_candidate(
        cluster(flags=(AMBIGUITY_STRUCTURALLY_DISCONNECTED,)),
        upstream=None,
        edges=(),
        conflicts=(),
        unknowns=(),
    )
    assert SIGNAL_STRUCTURALLY_DISCONNECTED in routed.structural_signals


def test_a_disconnected_topic_candidate_does_not_escalate_on_that_alone() -> None:
    """Topic candidates are *supposed* to be loosely connected.

    "These documents share vocabulary" is not a question with a wrong answer, and
    escalating every one is how a queue becomes a corpus dump.
    """
    routed = route_candidate(
        cluster("TOPIC_CANDIDATE", flags=(AMBIGUITY_STRUCTURALLY_DISCONNECTED,)),
        upstream=None,
        edges=(),
        conflicts=(),
        unknowns=(),
    )
    assert SIGNAL_STRUCTURALLY_DISCONNECTED not in routed.structural_signals
    assert routed.topology_recommended_reasoning_type == "NONE"


def test_a_candidate_spanning_roots_and_versions_escalates() -> None:
    routed = route_candidate(
        cluster(cross_root=True, supersessions=1),
        upstream=None,
        edges=(),
        conflicts=(),
        unknowns=(),
    )
    assert SIGNAL_SPANS_ROOTS_AND_VERSIONS in routed.structural_signals


def test_an_escalated_topic_candidate_gets_a_question_it_can_answer() -> None:
    """A topic candidate's default is ``NONE``, so escalation needs a fallback."""
    routed = route_candidate(
        cluster("TOPIC_CANDIDATE", cross_root=True, supersessions=1),
        upstream=None,
        edges=(),
        conflicts=(),
        unknowns=(),
    )
    assert routed.topology_recommended_reasoning_type == "SAME_BODY_OF_WORK_ADJUDICATION"


def test_escalation_preserves_a_more_specific_upstream_recommendation() -> None:
    """Topology escalated; the producer already named the better question."""
    routed = route_candidate(
        cluster(cross_root=True, supersessions=1),
        upstream=request("VERSION_EVOLUTION_ANALYSIS"),
        edges=(),
        conflicts=(),
        unknowns=(),
    )
    assert routed.topology_recommended_reasoning_type == "VERSION_EVOLUTION_ANALYSIS"


# ── de-escalation ───────────────────────────────────────────────────────────


def test_a_wholly_duplicated_group_de_escalates() -> None:
    routed = route_candidate(
        cluster("CONSOLIDATION_CANDIDATE"),
        upstream=request("CONSOLIDATION_ANALYSIS"),
        edges=duplicates_over(MEMBERS),
        conflicts=(),
        unknowns=(),
    )
    assert routed.topology_recommended_reasoning_type == "NONE"
    assert SIGNAL_EXACT_DUPLICATE_ONLY in routed.structural_signals
    assert routed.deescalated


def test_a_partially_duplicated_group_does_not_de_escalate() -> None:
    """Two of three members being identical leaves a real question about the third."""
    members = ("artifact:a", "artifact:b", "artifact:c")
    routed = route_candidate(
        cluster("CONSOLIDATION_CANDIDATE", members=members),
        upstream=request("CONSOLIDATION_ANALYSIS"),
        edges=duplicates_over(("artifact:a", "artifact:b")),
        conflicts=(),
        unknowns=(),
    )
    assert routed.topology_recommended_reasoning_type == "CONSOLIDATION_ANALYSIS"
    assert SIGNAL_EXACT_DUPLICATE_ONLY not in routed.structural_signals


def test_an_exactly_resolved_supersession_de_escalates() -> None:
    """Version B replaced version A. A reasoner would re-derive a declaration."""
    routed = route_candidate(
        cluster("CONSOLIDATION_CANDIDATE"),
        upstream=request("CONSOLIDATION_ANALYSIS"),
        edges=(supersession("exact-artifact"),),
        conflicts=(),
        unknowns=(),
    )
    assert routed.topology_recommended_reasoning_type == "NONE"
    assert SIGNAL_EXPLAINED_BY_EXACT_RELATION in routed.structural_signals


def test_a_conflict_beats_de_escalation() -> None:
    """Byte identity does not answer a status contradiction.

    The members hold the same bytes *and* their subjects declare incompatible
    statuses. The hashes settled one question and not the other, so the candidate
    still goes to a reasoner.
    """
    routed = route_candidate(
        cluster("CONSOLIDATION_CANDIDATE", flags=(AMBIGUITY_CONFLICTING_STATUS,)),
        upstream=request("CONSOLIDATION_ANALYSIS"),
        edges=duplicates_over(MEMBERS),
        conflicts=(),
        unknowns=(),
    )
    assert routed.topology_recommended_reasoning_type == "CONFLICT_RESOLUTION_ANALYSIS"
    assert SIGNAL_EXACT_DUPLICATE_ONLY not in routed.structural_signals


def test_a_single_member_group_is_never_wholly_duplicated() -> None:
    """Byte identity needs two files. One member cannot de-escalate on it."""
    routed = route_candidate(
        cluster("CONSOLIDATION_CANDIDATE", members=("artifact:a",)),
        upstream=request("CONSOLIDATION_ANALYSIS"),
        edges=duplicates_over(MEMBERS),
        conflicts=(),
        unknowns=(),
    )
    assert SIGNAL_EXACT_DUPLICATE_ONLY not in routed.structural_signals


# ── neither ─────────────────────────────────────────────────────────────────


def test_with_no_signal_the_producer_s_routing_stands() -> None:
    routed = route_candidate(
        cluster(),
        upstream=request("PROJECT_IDENTITY_ADJUDICATION"),
        edges=(),
        conflicts=(),
        unknowns=(),
    )
    assert routed.topology_recommended_reasoning_type == "PROJECT_IDENTITY_ADJUDICATION"
    assert not routed.escalated
    assert not routed.deescalated
    assert "no structural evidence" in routed.reason


def test_with_no_upstream_recommendation_the_candidate_type_decides() -> None:
    routed = route_candidate(
        cluster(),
        upstream=None,
        edges=(),
        conflicts=(),
        unknowns=(),
    )
    assert routed.upstream_recommended_reasoning_type is None
    assert routed.topology_recommended_reasoning_type == "SAME_BODY_OF_WORK_ADJUDICATION"
    assert "no upstream recommendation" in routed.reason


def test_a_producer_none_and_a_topology_none_is_not_a_movement() -> None:
    routed = route_candidate(
        cluster("TOPIC_CANDIDATE"),
        upstream=request("NONE"),
        edges=(),
        conflicts=(),
        unknowns=(),
    )
    assert routed.topology_recommended_reasoning_type == "NONE"
    assert not routed.escalated
    assert not routed.deescalated


def test_every_routing_decision_carries_a_reason() -> None:
    """Including ``NONE``. A queue row with no stated reason cannot be audited."""
    for candidate_type in ("TOPIC_CANDIDATE", "PROJECT_CANDIDATE", "CONSOLIDATION_CANDIDATE"):
        routed = route_candidate(
            cluster(candidate_type),
            upstream=None,
            edges=(),
            conflicts=(),
            unknowns=(),
        )
        assert routed.reason


def test_the_bounded_neighborhood_is_one_hop() -> None:
    edges = (
        EdgeRecord(
            edge_id="edge:out",
            source_id=MEMBERS[0],
            target_id="artifact:neighbour",
            edge_type=EdgeType.depends_on,
        ),
        EdgeRecord(
            edge_id="edge:far",
            source_id="artifact:neighbour",
            target_id="artifact:distant",
            edge_type=EdgeType.depends_on,
        ),
    )
    routed = route_candidate(cluster(), upstream=None, edges=edges, conflicts=(), unknowns=())
    assert routed.bounded_neighborhood_refs == ("artifact:neighbour",)
    assert "artifact:distant" not in routed.bounded_neighborhood_refs
