from pathlib import Path

import pytest

from l9_constellation_topology.scanners.dependency_scanner import scan_dependencies
from scripts.validate_release_readiness import collect_findings


def test_release_readiness_has_no_blocking_findings() -> None:
    findings = collect_findings()
    blocking = [finding for finding in findings if finding.severity in {"critical", "major"}]
    assert blocking == []


def test_dependency_scanner_rejects_malformed_package_json(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="repo:test: invalid package.json"):
        scan_dependencies(tmp_path, "repo:test")


def test_dependency_scanner_rejects_non_object_dependency_section(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies": ["not-a-map"]}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="dependencies must be an object"):
        scan_dependencies(tmp_path, "repo:test")
