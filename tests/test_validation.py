"""Tests for schema and invariant validators."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

from l9_constellation_topology.models import (
    Confidence,
    MaturityScore,
    RepoCard,
    TopologyReport,
)
from l9_constellation_topology.validation.invariant_validator import check_invariants
from l9_constellation_topology.validation.schema_validator import validate_topology_report
from l9_constellation_topology.validation.validation_report import run_full_validation


def _valid_report() -> TopologyReport:
    card = RepoCard(
        repo_id="r1",
        name="r1",
        path="/fake/r1",
        primary_role="service",
        confidence=Confidence.medium,
    )
    return TopologyReport(
        constellation_name="test",
        generated_at="2026-07-05T00:00:00Z",
        repo_inventory=[card],
        maturity_scorecard=[MaturityScore(repo_id="r1", score=50, band="emerging")],
    )


def test_valid_report_passes_schema():
    result = validate_topology_report(_valid_report())
    assert result.valid is True
    assert len([i for i in result.issues if i.severity == "error"]) == 0


def test_empty_constellation_name_fails():
    report = _valid_report()
    report.constellation_name = ""
    result = validate_topology_report(report)
    assert result.valid is False


def test_invariants_pass_for_valid_report():
    result = check_invariants(_valid_report())
    assert result.valid is True


def test_invariants_warn_on_unscored_repo():
    report = _valid_report()
    report.maturity_scorecard = []
    result = check_invariants(report)
    warnings = [i for i in result.issues if i.severity == "warning"]
    assert any("maturity" in i.issue_id for i in warnings)


def test_run_full_validation_returns_dict():
    result = run_full_validation(_valid_report())
    assert "valid" in result
    assert "error_count" in result
    assert "issues" in result
