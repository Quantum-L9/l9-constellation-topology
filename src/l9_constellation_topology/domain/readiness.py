"""Readiness evidence: counts of things observed, and nothing derived from them.

Every field here is a count of artifacts or declarations that were actually
seen. None is combined with another, weighted, normalized, or projected forward.

That restraint is the whole design. The obvious next step — divide test files by
source files, call it a coverage proxy, call the result readiness — produces a
number that looks like a measurement and is not one: a repository with one
thorough test file and one with forty trivial ones score identically, and a body
of work whose documents are mostly undecodable scores as though it had nothing
in it. The counts are honest; a score computed from them would not be, and once
a score exists downstream will rank on it.

So the forbidden metrics are named and refused at the type level rather than
merely discouraged. ``percent_complete``, ``priority_score``,
``strategic_value``, ``ROI``, ``production_ready``, and
``recommended_build_order`` are not fields this record has, and
``FORBIDDEN_READINESS_FIELDS`` exists so a test can assert their continued
absence rather than a reviewer having to notice one being added.

``coverage_gap_count`` sits beside the counts for the same reason: a body of
work whose documents could not be read produces thin evidence, and a reader who
cannot see that will mistake thin evidence for a thin project.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from .base import FrozenModel
from .confidence import Authority, ConfidenceAssessment

#: Field names this record must never gain. Each requires a judgement about
#: worth, completion, or intent that no count of files supports. Named so the
#: refusal is testable rather than merely stated.
FORBIDDEN_READINESS_FIELDS: frozenset[str] = frozenset(
    {
        "percent_complete",
        "priority_score",
        "strategic_value",
        "roi",
        "ROI",
        "production_ready",
        "recommended_build_order",
        "readiness_score",
        "completion_ratio",
    }
)


class ReadinessEvidenceRecord(FrozenModel):
    """Readiness measurements for one subject."""

    readiness_id: str = Field(min_length=1)
    #: The candidate cluster or topology entity these counts are about.
    subject_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)

    # What exists, by kind.
    source_artifact_count: int = Field(default=0, ge=0)
    #: Files a test convention claims. Structural evidence only: files named or
    #: placed like tests exist. Never that a test was run, and never that one
    #: passed.
    test_artifact_count: int = Field(default=0, ge=0)
    build_manifest_count: int = Field(default=0, ge=0)
    ci_definition_count: int = Field(default=0, ge=0)
    deployment_definition_count: int = Field(default=0, ge=0)
    specification_count: int = Field(default=0, ge=0)
    documentation_count: int = Field(default=0, ge=0)

    # What the documents declare about their own state. Declarations, not
    # verdicts: a document saying "complete" is evidence that it says so.
    plan_count: int = Field(default=0, ge=0)
    roadmap_count: int = Field(default=0, ge=0)
    wip_count: int = Field(default=0, ge=0)
    draft_count: int = Field(default=0, ge=0)
    blocked_count: int = Field(default=0, ge=0)

    open_task_count: int = Field(default=0, ge=0)
    completed_task_count: int = Field(default=0, ge=0)
    milestone_count: int = Field(default=0, ge=0)

    # Duplication and consolidation pressure.
    exact_duplicate_count: int = Field(default=0, ge=0)
    near_duplicate_count: int = Field(default=0, ge=0)
    consolidation_candidate_count: int = Field(default=0, ge=0)

    #: Members whose bytes were never read or never decoded. The denominator's
    #: honesty check.
    coverage_gap_count: int = Field(default=0, ge=0)
    evidence_refs: tuple[str, ...] = ()
    #: Readiness is a measurement over derived corpus analysis, so it is never
    #: source-authoritative however exact its inputs were.
    confidence: ConfidenceAssessment

    @model_validator(mode="after")
    def authority_is_never_source(self) -> ReadinessEvidenceRecord:
        if self.confidence.authority is Authority.source:
            raise ValueError(
                "readiness evidence is a derived measurement and may not claim source authority"
            )
        return self
