"""Schema validation for TopologyReport and GraphRecords against JSON Schema."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from l9_constellation_topology.models import (
    Confidence,
    RecordType,
    TopologyReport,
    ValidationIssue,
    ValidationResult,
)

_REQUIRED_REPORT_FIELDS = [
    "constellation_name",
    "generated_at",
    "repo_inventory",
    "dependency_graph",
    "risk_register",
    "maturity_scorecard",
]

_REQUIRED_GRAPH_RECORD_FIELDS = ["record_type", "label", "id", "properties", "confidence"]

_VALID_CONFIDENCE = {c.value for c in Confidence}
_VALID_RECORD_TYPES = {r.value for r in RecordType}


def _issue(
    issue_id: str,
    severity: Literal["error", "warning", "info"],
    rule: str,
    message: str,
    path: str = "",
) -> ValidationIssue:
    return ValidationIssue(
        issue_id=issue_id, severity=severity, rule=rule, message=message, path=path
    )


def validate_topology_report(report: TopologyReport) -> ValidationResult:
    issues: list[ValidationIssue] = []
    data = report.model_dump(mode="json")

    for field in _REQUIRED_REPORT_FIELDS:
        if field not in data or data[field] is None:
            issues.append(
                _issue(
                    f"report:{field}:missing",
                    "error",
                    "required_field_present",
                    f"Missing required field: {field}",
                    f"report.{field}",
                )
            )

    if not report.constellation_name:
        issues.append(
            _issue(
                "report:name:empty",
                "error",
                "constellation_name_nonempty",
                "constellation_name must not be empty",
                "report.constellation_name",
            )
        )

    for i, card in enumerate(report.repo_inventory):
        if not card.repo_id:
            issues.append(
                _issue(
                    f"card:{i}:repo_id:empty",
                    "error",
                    "repo_id_nonempty",
                    f"RepoCard[{i}] repo_id is empty",
                    f"repo_inventory[{i}].repo_id",
                )
            )
        if card.confidence.value not in _VALID_CONFIDENCE:
            issues.append(
                _issue(
                    f"card:{i}:confidence:invalid",
                    "error",
                    "confidence_valid",
                    f"Invalid confidence: {card.confidence}",
                    f"repo_inventory[{i}].confidence",
                )
            )

    for i, rec in enumerate(report.graph_records):
        if rec.record_type.value not in _VALID_RECORD_TYPES:
            issues.append(
                _issue(
                    f"graph:{i}:type:invalid",
                    "error",
                    "record_type_valid",
                    f"Invalid record_type: {rec.record_type}",
                    f"graph_records[{i}].record_type",
                )
            )
        if not rec.id:
            issues.append(
                _issue(
                    f"graph:{i}:id:empty",
                    "error",
                    "graph_record_id_nonempty",
                    f"GraphRecord[{i}] id is empty",
                    f"graph_records[{i}].id",
                )
            )

    return ValidationResult(
        valid=not any(i.severity == "error" for i in issues),
        issues=issues,
        checked_at=datetime.now(UTC).isoformat(),
    )


def validate_from_file(path: Path) -> ValidationResult:
    """Load a topology_report.json and validate it."""
    data = json.loads(path.read_text(encoding="utf-8"))
    report = TopologyReport.model_validate(data)
    return validate_topology_report(report)
