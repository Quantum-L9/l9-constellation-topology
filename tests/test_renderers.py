"""Tests for renderers: markdown, json, csv, mermaid."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

from l9_constellation_topology.models import (
    Confidence,
    Direction,
    EdgeCard,
    EdgeType,
    MaturityScore,
    RepoCard,
    TopologyReport,
)
from l9_constellation_topology.renderers.csv_export import (
    export_maturity_csv,
    export_repo_inventory_yaml,
)
from l9_constellation_topology.renderers.json_export import export_json
from l9_constellation_topology.renderers.markdown_report import render_markdown
from l9_constellation_topology.renderers.mermaid_export import export_mermaid


def _sample_report(tmp_path: Path) -> TopologyReport:
    card = RepoCard(
        repo_id="test-repo",
        name="test-repo",
        path=str(tmp_path),
        primary_role="service",
        languages=["Python"],
        package_managers=["pip"],
        confidence=Confidence.medium,
    )
    edge = EdgeCard(
        source="test-repo",
        target="other-repo",
        edge_type=EdgeType.dependency,
        direction=Direction.outbound,
        confidence=Confidence.medium,
    )
    return TopologyReport(
        constellation_name="test-constellation",
        generated_at="2026-07-05T21:00:00Z",
        repo_inventory=[card],
        dependency_graph=[edge],
        maturity_scorecard=[MaturityScore(repo_id="test-repo", score=55, band="emerging")],
    )


def test_render_markdown_contains_repo(tmp_path):
    report = _sample_report(tmp_path)
    md = render_markdown(report)
    assert "test-repo" in md
    assert "# L9 Constellation Topology Report" in md


def test_export_json_is_valid(tmp_path):
    report = _sample_report(tmp_path)
    out = tmp_path / "report.json"
    export_json(report, out)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["constellation_name"] == "test-constellation"


def test_export_maturity_csv_has_header(tmp_path):
    report = _sample_report(tmp_path)
    out = tmp_path / "maturity.csv"
    export_maturity_csv(report, out)
    assert out.exists()
    lines = out.read_text().splitlines()
    assert lines[0].startswith("repo_id")


def test_export_mermaid_has_graph(tmp_path):
    report = _sample_report(tmp_path)
    out = tmp_path / "diagram.mmd"
    export_mermaid(report, out)
    assert out.exists()
    content = out.read_text()
    assert "graph TD" in content
    assert "test-repo" in content


def test_export_repo_inventory_yaml(tmp_path):
    report = _sample_report(tmp_path)
    out = tmp_path / "inventory.yaml"
    export_repo_inventory_yaml(report, out)
    assert out.exists()
    content = out.read_text()
    assert "repo_inventory:" in content
    assert "test-repo" in content
