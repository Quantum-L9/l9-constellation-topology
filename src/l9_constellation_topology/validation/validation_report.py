"""Legacy v4 validation report formatting behind the canonical sink boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from l9_constellation_topology.models import TopologyReport
from l9_constellation_topology.renderers.common import (
    make_rendered_artifact,
    write_compatibility_artifact,
)
from l9_constellation_topology.validation.invariant_validator import check_invariants
from l9_constellation_topology.validation.schema_validator import validate_topology_report


def run_full_validation(report: TopologyReport) -> dict[str, Any]:
    schema_result = validate_topology_report(report)
    invariant_result = check_invariants(report)
    all_issues = schema_result.issues + invariant_result.issues
    return {
        "valid": schema_result.valid and invariant_result.valid,
        "error_count": sum(1 for issue in all_issues if issue.severity == "error"),
        "warning_count": sum(1 for issue in all_issues if issue.severity == "warning"),
        "issues": [issue.model_dump() for issue in all_issues],
        "schema_valid": schema_result.valid,
        "invariants_valid": invariant_result.valid,
        "checked_at": datetime.now(UTC).isoformat(),
    }


def render_validation_report(result: dict[str, Any]) -> str:
    lines = [
        "# 07_VALIDATION_REPORT",
        f"\n**Checked at:** {result['checked_at']}",
        f"**Valid:** {result['valid']}",
        f"**Errors:** {result['error_count']}",
        f"**Warnings:** {result['warning_count']}",
        "\n## Issues\n",
    ]
    if not result["issues"]:
        lines.append("_No issues found._")
    else:
        lines.extend(
            (
                "| Issue ID | Severity | Rule | Message | Path |",
                "|---|---|---|---|---|",
            )
        )
        for issue in result["issues"]:
            lines.append(
                f"| {issue['issue_id']} | {issue['severity']} | {issue['rule']} | "
                f"{issue['message']} | {issue['path']} |"
            )
    return "\n".join(lines) + "\n"


def write_validation_report(result: dict[str, Any], output_path: Path) -> None:
    content = render_validation_report(result).encode("utf-8")
    write_compatibility_artifact(
        output_path,
        make_rendered_artifact(
            logical_id="legacy-validation-report",
            destination_path=output_path.name,
            artifact_kind="human-report",
            media_type="text/markdown",
            content=content,
        ),
    )
