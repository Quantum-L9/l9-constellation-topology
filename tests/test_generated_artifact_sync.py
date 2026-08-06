from pathlib import Path

import pytest
from scripts.generated_artifact_sync import GeneratedArtifact, find_drift, synchronize


def test_update_then_check_generated_artifacts(tmp_path: Path) -> None:
    first = tmp_path / "contracts" / "first.json"
    second = tmp_path / "fixtures" / "second.json"
    artifacts = (
        GeneratedArtifact(first, b'{"value":1}\n'),
        GeneratedArtifact(second, b'{"value":2}\n'),
    )

    updated = synchronize(artifacts, check=False)

    assert [(item.kind, item.path) for item in updated] == [
        ("missing", first),
        ("missing", second),
    ]
    assert first.read_bytes() == b'{"value":1}\n'
    assert second.read_bytes() == b'{"value":2}\n'
    assert synchronize(artifacts, check=True) == ()


def test_check_reports_drift_without_mutating_files(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    stale = tmp_path / "stale.json"
    stale.write_bytes(b"old\n")
    artifacts = (
        GeneratedArtifact(missing, b"new\n"),
        GeneratedArtifact(stale, b"new\n"),
    )

    findings = synchronize(artifacts, check=True)

    assert [(item.kind, item.path) for item in findings] == [
        ("missing", missing),
        ("stale", stale),
    ]
    assert not missing.exists()
    assert stale.read_bytes() == b"old\n"


def test_duplicate_generated_paths_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    artifacts = (
        GeneratedArtifact(path, b"first"),
        GeneratedArtifact(path, b"second"),
    )

    with pytest.raises(ValueError, match="duplicate generated artifact path"):
        find_drift(artifacts)
