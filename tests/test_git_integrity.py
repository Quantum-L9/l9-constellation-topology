from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.git_tree_manifest import (
    FORBIDDEN_TRACKED_PATH,
    build_manifest,
    collect_tree_entries,
    entries_sha256,
)
from scripts.validate_git_integrity import inspect_commit

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write_inventory(root: Path, *paths: str) -> None:
    lines = ["# Manifest", ""]
    lines.extend(f"- `{path}` — fixture entry" for path in sorted(paths))
    (root / "MANIFEST.md").write_text("\n".join((*lines, "")), encoding="utf-8")


def _committed_repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "Test Architect")
    _git(root, "config", "user.email", "architect@example.invalid")
    (root / "payload.txt").write_text("first\n", encoding="utf-8")
    _write_inventory(root, "MANIFEST.md", "payload.txt")
    _git(root, "add", "MANIFEST.md", "payload.txt")
    _git(root, "commit", "-m", "initial")
    return root


def test_git_integrity_passes_without_a_committed_tree_manifest(tmp_path: Path) -> None:
    root = _committed_repository(tmp_path)
    result = inspect_commit(root)
    assert result["status"] == "passed"
    assert result["committed_tree_manifest"] is False
    assert result["git_tree_entry_count"] == 2
    assert result["validated_tree_sha"] == _git(root, "rev-parse", "HEAD^{tree}")


def test_git_integrity_digest_follows_committed_content(tmp_path: Path) -> None:
    root = _committed_repository(tmp_path)
    before = inspect_commit(root)
    (root / "payload.txt").write_text("second\n", encoding="utf-8")
    _git(root, "add", "payload.txt")
    _git(root, "commit", "-m", "change payload")

    after = inspect_commit(root)
    assert after["status"] == "passed"
    assert after["git_tree_entries_sha256"] != before["git_tree_entries_sha256"]
    assert after["git_tree_entries_sha256"] == entries_sha256(collect_tree_entries(root, "HEAD"))


def test_git_integrity_refuses_a_committed_tree_manifest(tmp_path: Path) -> None:
    root = _committed_repository(tmp_path)
    (root / FORBIDDEN_TRACKED_PATH).write_text("{}\n", encoding="utf-8")
    _write_inventory(root, "MANIFEST.md", "payload.txt", FORBIDDEN_TRACKED_PATH)
    _git(root, "add", "MANIFEST.md", FORBIDDEN_TRACKED_PATH)
    _git(root, "commit", "-m", "commit the retired manifest")

    result = inspect_commit(root)
    assert result["status"] == "failed"
    assert result["committed_tree_manifest"] is True


def test_git_integrity_rejects_an_inventory_that_omits_a_tracked_path(tmp_path: Path) -> None:
    root = _committed_repository(tmp_path)
    (root / "extra.txt").write_text("extra\n", encoding="utf-8")
    _git(root, "add", "extra.txt")
    _git(root, "commit", "-m", "add a file without inventory")

    result = inspect_commit(root)
    assert result["status"] == "failed"
    assert result["missing_from_inventory_manifest"] == ("extra.txt",)


def test_tree_manifest_refuses_a_treeish_git_would_read_as_an_option(tmp_path: Path) -> None:
    root = _committed_repository(tmp_path)
    for treeish in ("--output=/tmp/x", "-p", ""):
        with pytest.raises(ValueError, match="treeish must name a revision or tree"):
            collect_tree_entries(root, treeish)
    paths = [entry["path"] for entry in collect_tree_entries(root, "HEAD")]
    assert paths == ["MANIFEST.md", "payload.txt"]


def test_tree_manifest_cli_prints_and_writes_nothing(tmp_path: Path) -> None:
    root = _committed_repository(tmp_path)
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS / "git_tree_manifest.py"), "--root", str(root)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == build_manifest(root, "HEAD")
    assert not (root / FORBIDDEN_TRACKED_PATH).exists()
    assert _git(root, "status", "--porcelain=v1", "--untracked-files=all") == ""


def test_tree_manifest_cli_rejects_an_option_treeish(tmp_path: Path) -> None:
    root = _committed_repository(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "git_tree_manifest.py"),
            "--root",
            str(root),
            "--treeish=--all",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "treeish must name a revision or tree" in completed.stderr


def test_git_integrity_out_must_stay_inside_the_repository(tmp_path: Path) -> None:
    root = _committed_repository(tmp_path)
    script = str(SCRIPTS / "validate_git_integrity.py")
    outside = subprocess.run(
        [sys.executable, script, "--root", str(root), "--out", "../escaped.json"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert outside.returncode != 0
    assert "--out must stay inside the repository root" in outside.stderr
    assert not (tmp_path / "escaped.json").exists()

    inside = subprocess.run(
        [sys.executable, script, "--root", str(root), "--out", "validation/result.json"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert inside.returncode == 0, inside.stdout + inside.stderr
    evidence = json.loads((root / "validation" / "result.json").read_text(encoding="utf-8"))
    assert evidence["validated_commit_sha"] == _git(root, "rev-parse", "HEAD")
    assert evidence["git_tree_entries_sha256"].startswith("sha256:")
