from pathlib import Path

import pytest
from scripts.validate_release_readiness import ROOT, _is_excluded, collect_findings

from l9_constellation_topology.scanners.dependency_scanner import scan_dependencies


def test_release_readiness_has_no_blocking_findings() -> None:
    findings = collect_findings()
    blocking = [finding for finding in findings if finding.severity in {"critical", "major"}]
    assert blocking == []


@pytest.mark.parametrize(
    "relative",
    [
        ".l9/session/secrets-plane.json",
        ".l9/uv-environment.lock",
        ".cursor/governance/CANONICAL_LAW.md",
        ".cursor-commands",
        ".l9/autonomy/l4-release-receipt.json",
        ".l9/pr/pr-summary.json",
        ".claude/settings.json",
        ".mcp.json",
    ],
)
def test_governance_session_state_is_not_delivery_inventory(relative: str) -> None:
    assert _is_excluded(ROOT / relative)


@pytest.mark.parametrize(
    "relative",
    [
        ".l9/pipeline.yaml",
        ".l9/topology-profile.yaml",
        ".l9/sessions.yaml",
        ".cursor-commands.md",
        "docs/cursor/notes.md",
    ],
)
def test_delivered_paths_near_session_state_remain_scanned(relative: str) -> None:
    assert not _is_excluded(ROOT / relative)


def test_dependency_scanner_rejects_malformed_package_json(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match=r"repo:test: invalid package\.json"):
        scan_dependencies(tmp_path, "repo:test")


def test_dependency_scanner_rejects_non_object_dependency_section(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"dependencies": ["not-a-map"]}', encoding="utf-8")
    with pytest.raises(ValueError, match="dependencies must be an object"):
        scan_dependencies(tmp_path, "repo:test")
