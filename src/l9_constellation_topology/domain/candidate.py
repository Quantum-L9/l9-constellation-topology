"""Candidate topology: valuable analysis that is explicitly not canonical truth.

A topic candidate, a project candidate, a similarity relation — these are worth
carrying. They are the only signal a corpus has about which of forty thousand
loose documents belong together, and discarding them because they are not
certain would throw away the entire point of analysing a corpus.

What they must never do is become canonical. The failure this domain is built to
prevent is specific and quiet: a strong project candidate gets promoted to a
``MEMBER_OF`` edge, that edge enters impact analysis, impact feeds maturity and
risk, and three layers later a similarity score is indistinguishable from a
declared dependency. Nothing in the output says which is which, and by then
nothing can reconstruct it.

The separation is therefore structural rather than a convention:

* candidates live in their own ``TopologyState`` fields, never in
  ``edge_records``;
* their graph projection is labelled ``Candidate…`` and carries
  ``canonical: False``, so a reader of the graph alone cannot mistake one;
* impact, flow, maturity, and risk read ``edge_records`` and so cannot see them;
* publication holds them by default.

Topology may *lower* a candidate's confidence when its own structural evidence
contradicts the upstream analysis, and it may add structural support counts. It
may never raise a candidate's authority above ``candidate``: no amount of
structural corroboration turns "these look related" into "these are related",
because the underlying observation never said so.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .base import FrozenModel
from .confidence import Authority, ConfidenceAssessment

#: Candidate cluster kinds, matching the producer's vocabulary exactly so a
#: topology record and the upstream record it came from are directly comparable.
CandidateType = Literal["TOPIC_CANDIDATE", "PROJECT_CANDIDATE", "CONSOLIDATION_CANDIDATE"]

#: Confidence class as the producer's fusion profile assigned it.
ConfidenceClass = Literal["weak", "moderate", "strong"]

#: Ordered weakest-first, so "lower but never raise" is a comparison rather than
#: a convention every call site has to remember.
CONFIDENCE_CLASS_ORDER: tuple[ConfidenceClass, ...] = ("weak", "moderate", "strong")

#: Ambiguity flag raised when a candidate's members declare incompatible work
#: statuses. Topology raises this from its own reconciled claims, so it can fire
#: on a contradiction the producer's own pass did not see.
AMBIGUITY_CONFLICTING_STATUS = "conflicting_status"

#: Raised when a candidate's members have no explicit structural relation at all
#: — no shared duplicate, no reference, no dependency, no supersession. The
#: grouping may still be right; nothing in the observed structure supports it.
AMBIGUITY_STRUCTURALLY_DISCONNECTED = "structurally_disconnected_members"

#: Raised when a candidate spans roots. Not a defect: cross-root candidates are
#: the point of a corpus. Flagged because adjudicating one needs more care.
AMBIGUITY_CROSS_ROOT = "spans_multiple_roots"


class CandidateMethodScore(FrozenModel):
    """One scored similarity method behind a candidate relation."""

    method: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)


class CandidateRelationRecord(FrozenModel):
    """A proposed relation between two artifacts. Never an ``EdgeRecord``.

    Deliberately not an ``EdgeRecord`` subclass and deliberately not carrying an
    ``EdgeType``. Sharing the canonical edge shape is exactly how a candidate
    ends up in a canonical traversal by accident, and a type that cannot be
    passed to the graph builder cannot be passed to it by mistake.
    """

    relation_id: str = Field(min_length=1)
    source_artifact_id: str = Field(min_length=1)
    target_artifact_id: str = Field(min_length=1)
    #: The similarity methods that fired, e.g. ``keyphrase-weighted-overlap/v1``.
    methods: tuple[str, ...] = ()
    method_scores: tuple[CandidateMethodScore, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    confidence_class: ConfidenceClass
    #: Identity of the producer profile this relation was computed under.
    analysis_profile: str = Field(min_length=1)
    #: The producer's own identity for this relation.
    upstream_candidate_id: str | None = None
    #: Always ``Authority.candidate``. Held as a field so the invariant is
    #: visible on the record and checkable by the validator, rather than being a
    #: property of the code that happened to build it.
    confidence: ConfidenceAssessment

    @model_validator(mode="after")
    def authority_is_candidate(self) -> CandidateRelationRecord:
        if self.confidence.authority is not Authority.candidate:
            raise ValueError(
                "a candidate relation must carry candidate authority, got "
                f"{self.confidence.authority!r}"
            )
        return self

    @model_validator(mode="after")
    def endpoints_are_distinct(self) -> CandidateRelationRecord:
        if self.source_artifact_id == self.target_artifact_id:
            raise ValueError(f"a candidate relation needs two artifacts: {self.relation_id}")
        return self


class CandidateStructuralEvidence(FrozenModel):
    """What topology can measure about a candidate group, deterministically.

    Every field is a count over records topology already holds: exact duplicate
    edges, resolved work relations, reconciled claims. None of them decides
    whether the candidate is a real project — a group with high counts is a
    well-connected candidate, not a confirmed one.

    The distributions are here because a total hides the thing worth seeing. Four
    members all declaring ``WIP`` and four members split two-and-two between
    ``WIP`` and ``Complete`` have the same member count and are completely
    different situations, and only the second needs a human.
    """

    member_count: int = Field(default=0, ge=0)
    repository_count: int = Field(default=0, ge=0)
    root_count: int = Field(default=0, ge=0)
    archive_member_count: int = Field(default=0, ge=0)

    internal_exact_duplicate_count: int = Field(default=0, ge=0)
    internal_explicit_reference_count: int = Field(default=0, ge=0)
    internal_dependency_count: int = Field(default=0, ge=0)
    internal_supersession_count: int = Field(default=0, ge=0)
    blocker_count: int = Field(default=0, ge=0)

    #: ``work.status`` value to number of members declaring it.
    work_status_distribution: dict[str, int] = Field(default_factory=dict)
    #: ``work.kind`` value to number of members declaring it.
    work_kind_distribution: dict[str, int] = Field(default_factory=dict)
    #: Members declaring more than one incompatible status.
    conflicting_status_count: int = Field(default=0, ge=0)

    capability_count: int = Field(default=0, ge=0)
    external_dependency_count: int = Field(default=0, ge=0)

    @property
    def structural_support_count(self) -> int:
        """Explicit structural links observed *inside* this group.

        A measurement, not a verdict. Zero means nothing in the observed
        structure connects these members, which is worth saying out loud; it does
        not mean the candidate is wrong.
        """
        return (
            self.internal_exact_duplicate_count
            + self.internal_explicit_reference_count
            + self.internal_dependency_count
            + self.internal_supersession_count
        )


class CandidateClusterRecord(FrozenModel):
    """A candidate body of work, topic, or consolidation group."""

    candidate_id: str = Field(min_length=1)
    candidate_type: CandidateType
    member_entity_ids: tuple[str, ...]
    supporting_relation_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    confidence_class: ConfidenceClass
    #: Contradictions inside the group, from the producer and from topology's own
    #: structural pass. Carried rather than resolved.
    ambiguity_flags: tuple[str, ...] = ()
    cross_root: bool = False
    cross_archive: bool = False
    analysis_profile: str = Field(min_length=1)
    upstream_candidate_id: str | None = None
    #: Topology's deterministic structural measurement of this group.
    structural_evidence: CandidateStructuralEvidence = Field(
        default_factory=CandidateStructuralEvidence
    )
    #: Readiness measurement for this candidate, when one exists.
    readiness_evidence_ref: str | None = None
    confidence: ConfidenceAssessment

    @model_validator(mode="after")
    def authority_is_candidate(self) -> CandidateClusterRecord:
        if self.confidence.authority is not Authority.candidate:
            raise ValueError(
                "a candidate cluster must carry candidate authority, got "
                f"{self.confidence.authority!r}"
            )
        return self

    @model_validator(mode="after")
    def names_at_least_one_member(self) -> CandidateClusterRecord:
        if not self.member_entity_ids:
            raise ValueError(f"candidate {self.candidate_id} names no members")
        return self


def weaken_to(current: ConfidenceClass, proposed: ConfidenceClass) -> ConfidenceClass:
    """Return the weaker of two confidence classes.

    The only permitted movement. Topology finding structural contradictions may
    lower a candidate; topology finding structural corroboration may not raise
    one, because the corroboration was already available to the profile that
    assigned the class and raising it here would silently override a decision
    made under rules this compiler does not own.
    """
    return min((current, proposed), key=CONFIDENCE_CLASS_ORDER.index)
