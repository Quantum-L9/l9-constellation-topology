"""Configuration-driven risk projection plus v4 compatibility rules."""

from __future__ import annotations

from typing import Any, Literal, cast

from l9_constellation_topology.compatibility.v4_models import (
    Confidence,
    EvidenceItem,
    RepoCard,
    RiskItem,
    SourceType,
)
from l9_constellation_topology.domain import ConfidenceLevel, RepositoryRecord, RiskRecord
from l9_constellation_topology.run import stable_id


def assess_topology_risks(
    repositories: tuple[RepositoryRecord, ...],
    profile: dict[str, Any],
) -> tuple[RiskRecord, ...]:
    risks: list[RiskRecord] = []
    order = {ConfidenceLevel.low: 0, ConfidenceLevel.medium: 1, ConfidenceLevel.high: 2}
    for repository in repositories:
        for rule in profile.get("rules", []):
            kind = str(rule.get("kind"))
            triggered = False
            if kind == "empty":
                triggered = not bool(getattr(repository, str(rule["field"]), ()))
            elif kind == "confidence_below":
                threshold = ConfidenceLevel(str(rule.get("threshold", "medium")))
                triggered = order[repository.confidence.level] < order[threshold]
            if not triggered:
                continue
            risks.append(
                RiskRecord(
                    risk_id=stable_id(
                        "risk",
                        {
                            "subject": repository.repository_id,
                            "rule": rule["id"],
                            "version": rule["version"],
                        },
                    ),
                    subject_id=repository.repository_id,
                    severity=cast(
                        Literal["low", "medium", "high", "critical"],
                        str(rule["severity"]),
                    ),
                    category=str(rule["category"]),
                    description=str(rule["description"]),
                    rule_id=str(rule["id"]),
                    rule_version=str(rule["version"]),
                    evidence_refs=repository.evidence_refs,
                    remediation=str(rule.get("remediation")) if rule.get("remediation") else None,
                )
            )
        for dependency in repository.unresolved_dependencies:
            risks.append(
                RiskRecord(
                    risk_id=stable_id(
                        "risk",
                        {"subject": repository.repository_id, "dependency": dependency},
                    ),
                    subject_id=repository.repository_id,
                    severity="medium",
                    category="unresolved_dependency",
                    description=f"Dependency {dependency!r} does not resolve to an input repository.",
                    rule_id="unresolved-dependency",
                    rule_version="1.0.0",
                    evidence_refs=repository.evidence_refs,
                    remediation="Provide the missing Repository Model Packet or mark the dependency external.",
                )
            )
    return tuple(sorted(risks, key=lambda item: item.risk_id))


def assess_risks(card: RepoCard) -> list[RiskItem]:
    """Legacy v4 compatibility rules."""
    risks: list[RiskItem] = []
    if not card.ci_workflows:
        risks.append(
            RiskItem(
                risk_id=f"{card.repo_id}:ci_gap",
                repo_id=card.repo_id,
                severity="high",
                category="ci_gap",
                description=f"No CI workflow detected in {card.name}.",
                evidence=[
                    EvidenceItem(
                        source_file=card.path,
                        source_type=SourceType.inference,
                        excerpt="ci_workflows list is empty",
                    )
                ],
            )
        )
    if not card.governance_files:
        risks.append(
            RiskItem(
                risk_id=f"{card.repo_id}:governance_gap",
                repo_id=card.repo_id,
                severity="medium",
                category="governance_gap",
                description=f"No governance file (CODEOWNERS, OWNERS) found in {card.name}.",
                evidence=[
                    EvidenceItem(
                        source_file=card.path,
                        source_type=SourceType.inference,
                        excerpt="governance_files list is empty",
                    )
                ],
            )
        )
    if not card.adr_files:
        risks.append(
            RiskItem(
                risk_id=f"{card.repo_id}:adr_gap",
                repo_id=card.repo_id,
                severity="low",
                category="adr_gap",
                description=f"No ADR files detected in {card.name}.",
                evidence=[
                    EvidenceItem(
                        source_file=card.path,
                        source_type=SourceType.inference,
                        excerpt="adr_files list is empty",
                    )
                ],
            )
        )
    if card.confidence == Confidence.low:
        risks.append(
            RiskItem(
                risk_id=f"{card.repo_id}:evidence_quality",
                repo_id=card.repo_id,
                severity="medium",
                category="evidence_quality",
                description=f"Repo {card.name} has low confidence evidence — claims may be incomplete.",
                evidence=card.evidence[:3],
            )
        )
    if (
        not card.upstream_dependencies
        and not card.downstream_dependents
        and card.primary_role not in ("documentation", "infrastructure", "UNKNOWN")
    ):
        risks.append(
            RiskItem(
                risk_id=f"{card.repo_id}:isolation",
                repo_id=card.repo_id,
                severity="low",
                category="isolation",
                description=f"Repo {card.name} has no detected dependencies — possible isolation.",
                evidence=[
                    EvidenceItem(
                        source_file=card.path,
                        source_type=SourceType.inference,
                        excerpt="upstream_dependencies and downstream_dependents are empty",
                    )
                ],
            )
        )
    return risks
