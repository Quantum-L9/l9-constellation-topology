"""Tests for dependency_scanner against fixture repos."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample_constellation"
MCP_SERVER = FIXTURE / "l9-mcp-server"
GATE_SDK = FIXTURE / "l9-gate-sdk"


from l9_constellation_topology.scanners.dependency_scanner import scan_dependencies


def test_mcp_server_has_l9_gate_sdk_dep():
    deps, _evidence = scan_dependencies(MCP_SERVER, "l9-mcp-server")
    dep_names = [d.lower() for d in deps]
    assert any("l9" in d or "gate" in d for d in dep_names)


def test_mcp_server_deps_have_evidence():
    _deps, evidence = scan_dependencies(MCP_SERVER, "l9-mcp-server")
    assert len(evidence) > 0


def test_gate_sdk_deps_are_external():
    deps, _evidence = scan_dependencies(GATE_SDK, "l9-gate-sdk")
    assert len(deps) > 0
    assert all(isinstance(d, str) for d in deps)


def test_dependency_evidence_has_source_file():
    _deps, evidence = scan_dependencies(MCP_SERVER, "l9-mcp-server")
    for ev in evidence:
        assert ev.source_file != ""
