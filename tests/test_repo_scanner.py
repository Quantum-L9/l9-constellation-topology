"""Tests for repo_scanner and sub-scanners using the sample_constellation fixture."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample_constellation"
GATE_SDK = FIXTURE / "l9-gate-sdk"
MCP_SERVER = FIXTURE / "l9-mcp-server"


from l9_constellation_topology.models import Confidence, RepoSource
from l9_constellation_topology.scanners.repo_scanner import scan_repo


def test_scan_gate_sdk_returns_repo_card():
    source = RepoSource(
        repo_id="l9-gate-sdk",
        name="l9-gate-sdk",
        local_path=str(GATE_SDK),
        expected_role="library",
    )
    card = scan_repo(source)
    assert card.repo_id == "l9-gate-sdk"
    assert card.name == "l9-gate-sdk"
    assert card.path == str(GATE_SDK)


def test_scan_gate_sdk_detects_python():
    source = RepoSource(
        repo_id="l9-gate-sdk",
        name="l9-gate-sdk",
        local_path=str(GATE_SDK),
    )
    card = scan_repo(source)
    assert "Python" in card.languages


def test_scan_gate_sdk_detects_ci():
    source = RepoSource(
        repo_id="l9-gate-sdk",
        name="l9-gate-sdk",
        local_path=str(GATE_SDK),
    )
    card = scan_repo(source)
    assert len(card.ci_workflows) > 0


def test_scan_gate_sdk_detects_adr():
    source = RepoSource(
        repo_id="l9-gate-sdk",
        name="l9-gate-sdk",
        local_path=str(GATE_SDK),
    )
    card = scan_repo(source)
    assert len(card.adr_files) > 0


def test_scan_gate_sdk_detects_governance():
    source = RepoSource(
        repo_id="l9-gate-sdk",
        name="l9-gate-sdk",
        local_path=str(GATE_SDK),
    )
    card = scan_repo(source)
    assert len(card.governance_files) > 0
    assert card.owner != "UNKNOWN"


def test_scan_missing_path_returns_low_confidence():
    source = RepoSource(
        repo_id="nonexistent",
        name="nonexistent",
        local_path="/tmp/does_not_exist_l9_test",
    )
    card = scan_repo(source)
    assert card.confidence == Confidence.low


def test_scan_gate_sdk_evidence_not_empty():
    source = RepoSource(
        repo_id="l9-gate-sdk",
        name="l9-gate-sdk",
        local_path=str(GATE_SDK),
    )
    card = scan_repo(source)
    assert len(card.evidence) > 0


def test_scan_mcp_server_detects_dependencies():
    source = RepoSource(
        repo_id="l9-mcp-server",
        name="l9-mcp-server",
        local_path=str(MCP_SERVER),
    )
    card = scan_repo(source)
    assert len(card.upstream_dependencies) > 0
