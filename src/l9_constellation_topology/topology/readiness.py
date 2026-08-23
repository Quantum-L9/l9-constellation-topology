"""Lower corpus readiness evidence into topology, as counts and nothing else.

This module is almost entirely a copy: the producer counted, and topology
carries the counts across. That is the intent. The one thing worth doing here
would be the one thing that must not be done — combining the counts into
something that ranks.

What the module does add is confidence, and it adds it downward. Readiness is a
measurement over derived corpus analysis, so it never carries source authority
however exact its inputs were: counting test files is deterministic, and "there
are four files named like tests" is still not a claim any repository made about
itself. A body of work with a large ``coverage_gap_count`` gets a lower level
again, because counts drawn from documents that could not be read are thin
evidence, and thin evidence presented at full confidence reads as a thin project.
"""

from __future__ import annotations

from l9_constellation_topology.domain.confidence import (
    Authority,
    Completeness,
    ConfidenceAssessment,
    ConfidenceLevel,
    DerivationMethod,
    EvidenceStrength,
)
from l9_constellation_topology.domain.readiness import ReadinessEvidenceRecord
from l9_constellation_topology.packets.corpus_intelligence import (
    CorpusIntelligencePacket,
    ReadinessEvidence,
)

#: Share of a subject's members that may be unreadable before the measurement is
#: reported at reduced confidence. A tenth is a judgement call, and it is stated
#: as a named constant rather than buried so it can be argued with.
COVERAGE_GAP_CONFIDENCE_THRESHOLD = 0.1


def _measured_total(evidence: ReadinessEvidence) -> int:
    """Artifacts this measurement had something to say about.

    The denominator for the coverage-gap ratio. Deliberately the *kind* counts
    rather than every count on the record: adding open tasks and milestones into
    a denominator of artifacts would compare two different things.
    """
    return (
        evidence.source_artifact_count
        + evidence.test_artifact_count
        + evidence.build_manifest_count
        + evidence.ci_definition_count
        + evidence.deployment_definition_count
        + evidence.specification_count
        + evidence.documentation_count
        + evidence.coverage_gap_count
    )


def readiness_confidence(evidence: ReadinessEvidence) -> ConfidenceAssessment:
    """Return the confidence of one readiness measurement."""
    total = _measured_total(evidence)
    gap_ratio = (evidence.coverage_gap_count / total) if total else 0.0
    thin = gap_ratio > COVERAGE_GAP_CONFIDENCE_THRESHOLD
    return ConfidenceAssessment(
        level=ConfidenceLevel.low if thin else ConfidenceLevel.medium,
        evidence_strength=EvidenceStrength.weak if thin else EvidenceStrength.corroborated,
        # Counting is deterministic even when what was counted is incomplete.
        derivation_method=DerivationMethod.deterministic,
        # Never `source`: a count of files is not a statement any repository made.
        authority=Authority.derived,
        completeness=Completeness.partial if thin else Completeness.sufficient,
    )


def compile_readiness_evidence(
    packet: CorpusIntelligencePacket,
) -> tuple[ReadinessEvidenceRecord, ...]:
    """Lower every readiness measurement the packet carries."""
    if packet.payload is None:
        return ()
    return tuple(
        sorted(
            (
                ReadinessEvidenceRecord(
                    readiness_id=evidence.readiness_id,
                    subject_id=evidence.subject_id,
                    profile_id=evidence.profile_id,
                    profile_version=evidence.profile_version,
                    source_artifact_count=evidence.source_artifact_count,
                    test_artifact_count=evidence.test_artifact_count,
                    build_manifest_count=evidence.build_manifest_count,
                    ci_definition_count=evidence.ci_definition_count,
                    deployment_definition_count=evidence.deployment_definition_count,
                    specification_count=evidence.specification_count,
                    documentation_count=evidence.documentation_count,
                    plan_count=evidence.plan_count,
                    roadmap_count=evidence.roadmap_count,
                    wip_count=evidence.wip_count,
                    draft_count=evidence.draft_count,
                    blocked_count=evidence.blocked_count,
                    open_task_count=evidence.open_task_count,
                    completed_task_count=evidence.completed_task_count,
                    milestone_count=evidence.milestone_count,
                    exact_duplicate_count=evidence.exact_duplicate_count,
                    near_duplicate_count=evidence.near_duplicate_count,
                    consolidation_candidate_count=evidence.consolidation_candidate_count,
                    coverage_gap_count=evidence.coverage_gap_count,
                    evidence_refs=tuple(sorted(set(evidence.evidence_refs))),
                    confidence=readiness_confidence(evidence),
                )
                for evidence in packet.payload.readiness_evidence
            ),
            key=lambda item: item.readiness_id,
        )
    )


def readiness_by_subject(
    records: tuple[ReadinessEvidenceRecord, ...],
) -> dict[str, str]:
    """Return ``subject_id`` -> ``readiness_id``, for attaching to candidates.

    First wins on a duplicated subject, deterministically, because records are
    already sorted by identity. Two readiness records for one subject is a
    producer defect the packet validator does not currently refuse; picking
    arbitrarily here would make the choice depend on iteration order.
    """
    index: dict[str, str] = {}
    for record in records:
        index.setdefault(record.subject_id, record.readiness_id)
    return index
