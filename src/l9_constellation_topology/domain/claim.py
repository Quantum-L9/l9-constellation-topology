"""Canonical semantic claim reconciled from repository-model assertions.

A repository-model assertion is a semantic claim a repository makes about itself:
a subject, a predicate, an object, and the exact hashed source span that says so.
None of the pre-existing canonical records can carry that losslessly.
``RepositoryRecord`` has a closed field set and no room for an arbitrary
predicate; ``CapabilityRecord`` describes a capability rather than an arbitrary
claim; ``EdgeRecord`` requires two resolvable topology entities, which most
claims do not have; ``ConflictRecord`` and ``UnknownRecord`` describe what went
*wrong* with a claim rather than the claim itself. Forcing a claim into any of
them would either drop the predicate or assert a relationship that was never
observed, so the claim gets a record of its own.

Identity is the logical claim — subject, predicate, object — and nothing else.
The packet that carried it, the topology snapshot that compiled it, the wall
clock, and the checkout it was read from are all excluded: the same repository
asserting the same thing twice is one claim, and it stays one claim when an
unrelated repository changes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .base import FrozenModel
from .confidence import Authority, ConfidenceAssessment, ConflictStatus

#: Reconciliation arity actually applied to this claim's predicate.
ClaimCardinality = Literal["single", "set", "unknown"]

#: How the predicate registry classified this claim's predicate. ``unsupported``
#: is preserved rather than dropped, and never projects.
ClaimSupport = Literal["set", "single", "auxiliary", "unsupported"]


class SemanticClaimRecord(FrozenModel):
    """One reconciled semantic claim, with the evidence that supports it."""

    claim_id: str
    subject_id: str
    predicate: str
    object: str
    #: Every producer assertion that asserted this exact claim. More than one
    #: means independent corroboration, never a contradiction.
    source_assertion_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    confidence: ConfidenceAssessment
    #: The claim-level authority. Held identically in ``confidence.authority``;
    #: the validator below makes the two impossible to diverge.
    authority: Authority
    cardinality: ClaimCardinality
    support: ClaimSupport
    conflict_status: ConflictStatus = ConflictStatus.none
    #: Set when this claim competes with another claim on the same single-valued
    #: subject and predicate. Every competing claim keeps its own record and
    #: names the shared conflict; none of them is elected the winner.
    conflict_ids: tuple[str, ...] = ()
    #: Whether a topology projection was applied. ``False`` is the normal case
    #: and never means the claim was discarded.
    projected: bool = False
    projected_entity_ids: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def authority_agrees_with_confidence(self) -> SemanticClaimRecord:
        if self.authority != self.confidence.authority:
            raise ValueError(
                "claim authority and confidence.authority must name the same authority: "
                f"{self.authority!r} != {self.confidence.authority!r}"
            )
        return self

    @model_validator(mode="after")
    def conflict_status_matches_conflicts(self) -> SemanticClaimRecord:
        if bool(self.conflict_ids) != (self.conflict_status is ConflictStatus.confirmed):
            raise ValueError(
                "a claim names conflicts exactly when its conflict status is confirmed"
            )
        return self
