"""Profile-driven maturity projection plus v4 compatibility scoring."""

from __future__ import annotations

from typing import Any

from l9_constellation_topology.compatibility.v4_models import Confidence, MaturityScore, RepoCard
from l9_constellation_topology.domain import ConfidenceLevel, MaturityAssessment, RepositoryRecord
from l9_constellation_topology.run import EvidenceRecord


def _band(score: int, bands: dict[str, int]) -> str:
    ordered = sorted(((threshold, label) for label, threshold in bands.items()), reverse=True)
    return next(label for threshold, label in ordered if score >= threshold)


def assess_maturity(
    repositories: tuple[RepositoryRecord, ...],
    evidence: tuple[EvidenceRecord, ...],
    profile: dict[str, Any],
) -> tuple[MaturityAssessment, ...]:
    evidence_by_subject: dict[str, tuple[EvidenceRecord, ...]] = {
        repository.repository_id: tuple(
            item for item in evidence if item.subject_id == repository.repository_id
        )
        for repository in repositories
    }
    dimensions_config = profile.get("dimensions", {})
    maximum = int(profile.get("maximum_score", 100))
    bands = {
        str(label): int(value) for label, value in profile.get("bands", {"nascent": 0}).items()
    }
    assessments: list[MaturityAssessment] = []
    for repository in repositories:
        dimensions: dict[str, int] = {}
        subject_evidence = evidence_by_subject[repository.repository_id]
        for dimension, rule in dimensions_config.items():
            weight = int(rule.get("weight", 0))
            awarded = 0
            if "field" in rule:
                value = getattr(repository, str(rule["field"]), ())
                if value:
                    awarded = weight
            if "evidence_contains" in rule:
                needle = str(rule["evidence_contains"]).lower()
                if any(
                    item.source_ref.source_path and needle in item.source_ref.source_path.lower()
                    for item in subject_evidence
                ):
                    awarded = weight
            if "minimum_confidence" in rule:
                threshold = ConfidenceLevel(str(rule["minimum_confidence"]))
                order = {ConfidenceLevel.low: 0, ConfidenceLevel.medium: 1, ConfidenceLevel.high: 2}
                if order[repository.confidence.level] >= order[threshold]:
                    awarded = weight
            dimensions[str(dimension)] = awarded
        score = min(maximum, sum(dimensions.values()))
        assessments.append(
            MaturityAssessment(
                subject_id=repository.repository_id,
                profile_id=str(profile["id"]),
                profile_version=str(profile["version"]),
                score=score,
                maximum_score=maximum,
                band=_band(score, bands),
                dimensions=dimensions,
                evidence_refs=repository.evidence_refs,
            )
        )
    return tuple(assessments)


_LEGACY_BANDS = [(90, "exemplary"), (70, "mature"), (40, "emerging"), (0, "nascent")]


def score_repo(card: RepoCard) -> MaturityScore:
    breakdown: dict[str, int] = {
        "has_package_manifest": 15
        if any(
            manager in card.package_managers
            for manager in ("pip", "uv", "uv/pip", "npm", "yarn", "cargo", "go")
        )
        else 0,
        "has_ci_workflow": 20 if card.ci_workflows else 0,
        "has_adr": 15 if card.adr_files else 0,
        "has_governance": 15 if card.governance_files else 0,
        "has_readme": 10
        if any("readme" in item.source_file.lower() for item in card.evidence)
        else 0,
        "has_dependencies": 10 if card.upstream_dependencies or card.downstream_dependents else 0,
        "high_confidence": 15 if card.confidence == Confidence.high else 0,
    }
    total = min(100, sum(breakdown.values()))
    band = next(label for threshold, label in _LEGACY_BANDS if total >= threshold)
    return MaturityScore(repo_id=card.repo_id, score=total, band=band, breakdown=breakdown)
