"""Route candidates for future reasoning, deterministically and with no model call.

The producer routes from what a corpus scan can see. Topology holds the compiled
graph, so it can see things the producer could not: whether a candidate's members
have a confirmed claim conflict between them, whether one of their references
failed to resolve, whether a supersession is ambiguous, whether the group has any
explicit structural link at all. Those change the answer to "would a reasoner
help here", so topology owns the final routing decision and records both.

Escalation and de-escalation are both real and are not symmetric in kind.

*Escalation* is for genuine ambiguity a reasoner could resolve: two members
declaring incompatible statuses, a reference that matched several artifacts, a
project candidate whose members nothing connects, a candidate spanning roots and
versions. Each is a question with more than one defensible answer, which is
exactly what adjudication is for.

*De-escalation* is for questions that turn out to already be answered. A
consolidation candidate whose members are all byte-identical has nothing to
adjudicate — every copy is the same file, and a reasoner reading them would spend
its attention confirming equality that a hash already decided. Likewise a
candidate whose grouping is fully explained by an exact source relation the
compiler resolved.

Everything here is a table lookup over recorded structure. No model is called,
no text is read, and the router is a pure function of the topology it is handed.
Rows routed to ``NONE`` are emitted rather than dropped: a queue that silently
omitted them could not be checked for the property that matters most, which is
that exact duplicates and similarity-only candidates never reach a reasoner.
"""

from __future__ import annotations

from dataclasses import dataclass

from l9_constellation_topology.domain.assessment import ConflictRecord, UnknownRecord
from l9_constellation_topology.domain.candidate import (
    AMBIGUITY_CONFLICTING_STATUS,
    AMBIGUITY_STRUCTURALLY_DISCONNECTED,
    CandidateClusterRecord,
)
from l9_constellation_topology.domain.edge import EdgeRecord, EdgeType
from l9_constellation_topology.domain.reasoning import (
    SIGNAL_AMBIGUOUS_SUPERSESSION,
    SIGNAL_CONFIRMED_CLAIM_CONFLICT,
    SIGNAL_EXACT_DUPLICATE_ONLY,
    SIGNAL_EXPLAINED_BY_EXACT_RELATION,
    SIGNAL_SPANS_ROOTS_AND_VERSIONS,
    SIGNAL_STRUCTURALLY_DISCONNECTED,
    SIGNAL_UNRESOLVED_EXACT_REFERENCE,
    ReasoningType,
    TopologyReasoningCandidate,
)
from l9_constellation_topology.packets.corpus_intelligence import (
    CorpusIntelligencePacket,
    ReasoningCandidateRequest,
)
from l9_constellation_topology.run.evidence import stable_id
from l9_constellation_topology.topology.work_projection import AMBIGUOUS_TARGET_REASON

#: Default routing for each candidate type when nothing escalates or de-escalates.
#:
#: A topic candidate routes to ``NONE`` by default: "these documents share
#: vocabulary" is not a question with a wrong answer, and sending every one to a
#: reasoner is how a queue becomes a corpus dump.
_DEFAULT_BY_TYPE: dict[str, ReasoningType] = {
    "TOPIC_CANDIDATE": "NONE",
    "PROJECT_CANDIDATE": "SAME_BODY_OF_WORK_ADJUDICATION",
    "CONSOLIDATION_CANDIDATE": "CONSOLIDATION_ANALYSIS",
}


def _bounded_neighborhood(
    members: frozenset[str], edges: tuple[EdgeRecord, ...]
) -> tuple[str, ...]:
    """Entities one explicit canonical hop from this candidate's members.

    One hop, not a traversal. An unbounded neighbourhood is the corpus, and
    handing a reasoner the corpus is not a handoff — the whole point of a bounded
    pack is that the attention it asks for is proportional to the question.
    """
    neighbours: set[str] = set()
    for edge in edges:
        if edge.source_id in members and edge.target_id not in members:
            neighbours.add(edge.target_id)
        elif edge.target_id in members and edge.source_id not in members:
            neighbours.add(edge.source_id)
    return tuple(sorted(neighbours))


def _members_wholly_duplicated(members: frozenset[str], edges: tuple[EdgeRecord, ...]) -> bool:
    """Whether every member is in one byte-identical cluster.

    Star edges mean a cluster of ``n`` members carries ``n-1`` edges, all naming
    one ``duplicate_cluster_id``. So "wholly duplicated" is: exactly one cluster
    id among the group's duplicate edges, and every member touched by one.
    """
    if len(members) < 2:
        return False
    touched: set[str] = set()
    clusters: set[str] = set()
    for edge in edges:
        if edge.edge_type is not EdgeType.duplicate_of:
            continue
        endpoints = {edge.source_id, edge.target_id}
        if not endpoints <= members:
            continue
        touched |= endpoints
        cluster = edge.properties.get("duplicate_cluster_id")
        if isinstance(cluster, str):
            clusters.add(cluster)
    return len(clusters) == 1 and touched == members


def _explained_by_exact_relation(members: frozenset[str], edges: tuple[EdgeRecord, ...]) -> bool:
    """Whether an exact resolved supersession already explains this grouping.

    A candidate whose members are joined by a supersession the compiler resolved
    exactly has its story told: version B replaced version A, and a reasoner
    would be re-deriving what a declaration already stated.
    """
    return any(
        edge.edge_type is EdgeType.supersedes
        and {edge.source_id, edge.target_id} <= members
        and edge.properties.get("target_resolution") == "exact-artifact"
        for edge in edges
    )


def _ambiguous_supersession(members: frozenset[str], edges: tuple[EdgeRecord, ...]) -> bool:
    """Whether a supersession touching this group failed to resolve exactly."""
    return any(
        edge.edge_type is EdgeType.supersedes
        and ({edge.source_id, edge.target_id} & members)
        and edge.properties.get("target_resolution") in {"ambiguous", "unresolved"}
        for edge in edges
    )


@dataclass(frozen=True)
class _Signals:
    """What topology's own structure says about one candidate.

    Collected before anything is decided, so gathering evidence and acting on it
    stay separable: a new signal is one branch here, and the decision table below
    does not grow with it.
    """

    structural: tuple[str, ...]
    conflict_refs: tuple[str, ...]
    unknown_refs: tuple[str, ...]
    escalate: bool
    deescalate: bool


def _collect_signals(
    cluster: CandidateClusterRecord,
    *,
    edges: tuple[EdgeRecord, ...],
    conflicts: tuple[ConflictRecord, ...],
    unknowns: tuple[UnknownRecord, ...],
) -> _Signals:
    """Return every signal recorded structure raises about this candidate."""
    members = frozenset(cluster.member_entity_ids)
    structural: list[str] = []

    conflict_refs = tuple(
        sorted(conflict.conflict_id for conflict in conflicts if conflict.subject_id in members)
    )
    unknown_refs = tuple(
        sorted(unknown.unknown_id for unknown in unknowns if unknown.subject_id in members)
    )

    if conflict_refs or AMBIGUITY_CONFLICTING_STATUS in cluster.ambiguity_flags:
        structural.append(SIGNAL_CONFIRMED_CLAIM_CONFLICT)
    if any(
        unknown.reason == AMBIGUOUS_TARGET_REASON and unknown.subject_id in members
        for unknown in unknowns
    ):
        structural.append(SIGNAL_UNRESOLVED_EXACT_REFERENCE)
    if _ambiguous_supersession(members, edges):
        structural.append(SIGNAL_AMBIGUOUS_SUPERSESSION)
    if (
        cluster.candidate_type == "PROJECT_CANDIDATE"
        and AMBIGUITY_STRUCTURALLY_DISCONNECTED in cluster.ambiguity_flags
    ):
        structural.append(SIGNAL_STRUCTURALLY_DISCONNECTED)
    if cluster.cross_root and cluster.structural_evidence.internal_supersession_count:
        structural.append(SIGNAL_SPANS_ROOTS_AND_VERSIONS)

    escalate = bool(structural)
    deescalate = False
    # Checked only when nothing escalated, and so it beats nothing: a group that
    # is wholly byte-identical *and* carries a confirmed conflict still goes to a
    # reasoner, because the conflict is a real question the hashes did not answer.
    if not escalate:
        if _members_wholly_duplicated(members, edges):
            structural.append(SIGNAL_EXACT_DUPLICATE_ONLY)
            deescalate = True
        elif _explained_by_exact_relation(members, edges):
            structural.append(SIGNAL_EXPLAINED_BY_EXACT_RELATION)
            deescalate = True

    return _Signals(
        structural=tuple(sorted(set(structural))),
        conflict_refs=conflict_refs,
        unknown_refs=unknown_refs,
        escalate=escalate,
        deescalate=deescalate,
    )


def _escalated_type(
    signals: _Signals, upstream_type: ReasoningType | None, default: ReasoningType
) -> ReasoningType:
    """Return what an escalated candidate should be adjudicated for."""
    if SIGNAL_CONFIRMED_CLAIM_CONFLICT in signals.structural:
        return "CONFLICT_RESOLUTION_ANALYSIS"
    if upstream_type is not None and upstream_type != "NONE":
        return upstream_type
    if default != "NONE":
        return default
    # A topic candidate's default is ``NONE``, so an escalated one still needs a
    # question. "Are these one body of work" is the weakest adjudication that
    # fits every escalation signal here.
    return "SAME_BODY_OF_WORK_ADJUDICATION"


def _decide(
    signals: _Signals, upstream_type: ReasoningType | None, default: ReasoningType
) -> tuple[ReasoningType, str]:
    """Return the routing decision and the reason recorded beside it."""
    if signals.deescalate:
        return "NONE", (
            "topology de-escalated: the grouping is already explained by an exact "
            + "relation this compile resolved, so there is nothing left to adjudicate"
        )
    if signals.escalate:
        return _escalated_type(signals, upstream_type, default), (
            "topology escalated on structural evidence the corpus pass did not hold: "
            + ", ".join(signals.structural)
        )
    if upstream_type is not None:
        return upstream_type, (
            "topology found no structural evidence to change the producer's routing"
        )
    return default, (
        "no upstream recommendation; routed by candidate type with no structural signal either way"
    )


def route_candidate(
    cluster: CandidateClusterRecord,
    *,
    upstream: ReasoningCandidateRequest | None,
    edges: tuple[EdgeRecord, ...],
    conflicts: tuple[ConflictRecord, ...],
    unknowns: tuple[UnknownRecord, ...],
) -> TopologyReasoningCandidate:
    """Return the topology reasoning decision for one candidate."""
    signals = _collect_signals(cluster, edges=edges, conflicts=conflicts, unknowns=unknowns)
    upstream_type = upstream.recommended_reasoning_type if upstream is not None else None
    default = _DEFAULT_BY_TYPE.get(cluster.candidate_type, "NONE")
    decided, reason = _decide(signals, upstream_type, default)

    return TopologyReasoningCandidate(
        reasoning_candidate_id=stable_id(
            "reasoning-candidate",
            {"candidate_id": cluster.candidate_id, "reasoning_type": decided},
        ),
        candidate_id=cluster.candidate_id,
        upstream_recommended_reasoning_type=upstream_type,
        topology_recommended_reasoning_type=decided,
        reason=reason,
        trigger_signals=tuple(sorted(set(cluster.ambiguity_flags))),
        structural_signals=signals.structural,
        conflict_refs=signals.conflict_refs,
        unknown_refs=signals.unknown_refs,
        readiness_ref=cluster.readiness_evidence_ref,
        evidence_refs=cluster.evidence_refs,
        bounded_neighborhood_refs=_bounded_neighborhood(
            frozenset(cluster.member_entity_ids), edges
        ),
    )


def route_reasoning_candidates(
    clusters: tuple[CandidateClusterRecord, ...],
    packets: tuple[CorpusIntelligencePacket, ...],
    *,
    edges: tuple[EdgeRecord, ...],
    conflicts: tuple[ConflictRecord, ...],
    unknowns: tuple[UnknownRecord, ...],
) -> tuple[TopologyReasoningCandidate, ...]:
    """Route every candidate, including the ones that go nowhere."""
    upstream_by_candidate: dict[str, ReasoningCandidateRequest] = {}
    for packet in packets:
        if packet.payload is None:
            continue
        for request in packet.payload.reasoning_candidates:
            upstream_by_candidate.setdefault(request.candidate_id, request)
    return tuple(
        sorted(
            (
                route_candidate(
                    cluster,
                    upstream=upstream_by_candidate.get(cluster.candidate_id),
                    edges=edges,
                    conflicts=conflicts,
                    unknowns=unknowns,
                )
                for cluster in clusters
            ),
            key=lambda item: item.reasoning_candidate_id,
        )
    )
