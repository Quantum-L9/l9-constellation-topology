"""Check structural invariants of the topology graph."""

from __future__ import annotations

from datetime import UTC, datetime

from l9_constellation_topology.models import TopologyReport, ValidationIssue, ValidationResult


def check_invariants(report: TopologyReport) -> ValidationResult:
    issues: list[ValidationIssue] = []

    repo_ids = {card.repo_id for card in report.repo_inventory}

    for i, edge in enumerate(report.dependency_graph):
        if edge.source not in repo_ids:
            issues.append(
                ValidationIssue(
                    issue_id=f"edge:{i}:source:unknown",
                    severity="warning",
                    rule="edge_source_in_inventory",
                    message=f"Edge source '{edge.source}' not in repo inventory",
                    path=f"dependency_graph[{i}].source",
                )
            )
        if edge.target not in repo_ids:
            issues.append(
                ValidationIssue(
                    issue_id=f"edge:{i}:target:unknown",
                    severity="warning",
                    rule="edge_target_in_inventory",
                    message=f"Edge target '{edge.target}' not in repo inventory",
                    path=f"dependency_graph[{i}].target",
                )
            )

    for i, risk in enumerate(report.risk_register):
        if risk.repo_id not in repo_ids and risk.repo_id != "global":
            issues.append(
                ValidationIssue(
                    issue_id=f"risk:{i}:repo:unknown",
                    severity="warning",
                    rule="risk_repo_in_inventory",
                    message=f"Risk '{risk.risk_id}' references unknown repo '{risk.repo_id}'",
                    path=f"risk_register[{i}].repo_id",
                )
            )

    scored_ids = {ms.repo_id for ms in report.maturity_scorecard}
    for card in report.repo_inventory:
        if card.repo_id not in scored_ids:
            issues.append(
                ValidationIssue(
                    issue_id=f"maturity:{card.repo_id}:missing",
                    severity="warning",
                    rule="all_repos_scored",
                    message=f"Repo '{card.repo_id}' has no maturity score",
                    path="maturity_scorecard",
                )
            )

    return ValidationResult(
        valid=not any(i.severity == "error" for i in issues),
        issues=issues,
        checked_at=datetime.now(UTC).isoformat(),
    )
