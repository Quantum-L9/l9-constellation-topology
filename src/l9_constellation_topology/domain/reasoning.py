"""The reasoning handoff: what a later reasoner should look at, and why.

The producer routes candidates for reasoning from what a corpus scan can see:
similarity scores, duplicate clusters, declared identifiers. By the time a
candidate reaches topology, more is known about it — whether its members have
resolved dependencies between them, whether a reference failed to resolve,
whether two of them declare contradictory statuses, how much readiness evidence
the group carries. That is genuinely new information about whether reasoning
would help, so topology owns the final routing decision.

Both decisions are recorded. ``upstream_recommended_reasoning_type`` is what the
producer asked for and ``topology_recommended_reasoning_type`` is what topology
decided; keeping only the second would make a disagreement between the two
invisible, and a disagreement is exactly the thing worth auditing.

Routing is deterministic and performs no reasoning of its own. Nothing in this
module or its router calls a model, and the record carries *references* — to
evidence, conflicts, unknowns, readiness, and a bounded neighbourhood — rather
than copies, so the handoff never becomes a second version of corpus truth that
can drift from the first.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import FrozenModel

#: What kind of adjudication a candidate needs, if any.
#:
#: ``NONE`` rows are emitted rather than dropped. A queue that silently omitted
#: them could not be checked for the property that matters most: that exact
#: duplicates and similarity-only candidates never reach a reasoner.
ReasoningType = Literal[
    "NONE",
    "SAME_BODY_OF_WORK_ADJUDICATION",
    "PROJECT_IDENTITY_ADJUDICATION",
    "VERSION_EVOLUTION_ANALYSIS",
    "CONSOLIDATION_ANALYSIS",
    "SUPERSESSION_ANALYSIS",
    "CONFLICT_RESOLUTION_ANALYSIS",
]

#: Every reasoning type, exposed so a consumer can assert it handles them all.
REASONING_TYPES: tuple[ReasoningType, ...] = (
    "NONE",
    "SAME_BODY_OF_WORK_ADJUDICATION",
    "PROJECT_IDENTITY_ADJUDICATION",
    "VERSION_EVOLUTION_ANALYSIS",
    "CONSOLIDATION_ANALYSIS",
    "SUPERSESSION_ANALYSIS",
    "CONFLICT_RESOLUTION_ANALYSIS",
)

#: Signals that may raise a candidate's routing. Named constants rather than
#: free strings so the router and its tests cannot disagree about spelling.
SIGNAL_CONFIRMED_CLAIM_CONFLICT = "confirmed_claim_conflict"
SIGNAL_UNRESOLVED_EXACT_REFERENCE = "unresolved_exact_reference"
SIGNAL_AMBIGUOUS_SUPERSESSION = "ambiguous_supersession"
SIGNAL_STRUCTURALLY_DISCONNECTED = "structurally_disconnected_project_candidate"
SIGNAL_SPANS_ROOTS_AND_VERSIONS = "spans_multiple_roots_and_versions"

#: Signals that may lower it.
SIGNAL_EXACT_DUPLICATE_ONLY = "exact_duplicate_only"
SIGNAL_EXPLAINED_BY_EXACT_RELATION = "already_explained_by_exact_source_relation"


class TopologyReasoningCandidate(FrozenModel):
    """One bounded, deterministic reasoning request."""

    reasoning_candidate_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    #: What the producer asked for. ``None`` when the producer said nothing about
    #: this candidate, which is different from the producer saying ``NONE``.
    upstream_recommended_reasoning_type: ReasoningType | None = None
    topology_recommended_reasoning_type: ReasoningType
    #: Why this routing was chosen. Present for every row, ``NONE`` included.
    reason: str = ""
    #: Signals the producer's own routing rested on, preserved verbatim.
    trigger_signals: tuple[str, ...] = ()
    #: Signals topology contributed from its own structural evidence.
    structural_signals: tuple[str, ...] = ()
    conflict_refs: tuple[str, ...] = ()
    unknown_refs: tuple[str, ...] = ()
    readiness_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()
    #: Entities one explicit hop from the candidate's members along canonical
    #: edges. Bounded on purpose: an unbounded neighbourhood is the corpus, and
    #: handing a reasoner the corpus is not a handoff.
    bounded_neighborhood_refs: tuple[str, ...] = ()

    @property
    def escalated(self) -> bool:
        """Whether topology routed this higher than the producer did.

        ``NONE`` and "the producer said nothing" both count as the floor, so a
        candidate topology routes for adjudication that the producer did not is
        an escalation either way.
        """
        upstream = self.upstream_recommended_reasoning_type
        return self.topology_recommended_reasoning_type != "NONE" and upstream in {None, "NONE"}

    @property
    def deescalated(self) -> bool:
        """Whether topology routed this lower than the producer did."""
        upstream = self.upstream_recommended_reasoning_type
        return (
            self.topology_recommended_reasoning_type == "NONE"
            and upstream is not None
            and upstream != "NONE"
        )
