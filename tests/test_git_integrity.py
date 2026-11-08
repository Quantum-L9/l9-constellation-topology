from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from scripts.git_tree_manifest import (
    collect_tree_entries,
    load_manifest,
    write_manifest,
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


def _committed_repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "Test Architect")
    _git(root, "config", "user.email", "architect@example.invalid")
    (root / "payload.txt").write_text("first\n", encoding="utf-8")
    (root / "MANIFEST.md").write_text(
        "\n".join(
            (
                "# Manifest",
                "",
                "- `GIT_TREE_MANIFEST.json` — Git blob identity manifest",
                "- `MANIFEST.md` — tracked path inventory",
                "- `payload.txt` — fixture payload",
                "",
            )
        ),
        encoding="utf-8",
    )
    _git(root, "add", "MANIFEST.md", "payload.txt")
    treeish = _git(root, "write-tree")
    write_manifest(root, treeish)
    _git(root, "add", "GIT_TREE_MANIFEST.json")
    _git(root, "commit", "-m", "initial")
    return root


def test_git_integrity_binds_paths_modes_and_blob_ids(tmp_path: Path) -> None:
    root = _committed_repository(tmp_path)
    result = inspect_commit(root)
    assert result["status"] == "passed"
    assert result["content_identity_mismatches"] == ()
    assert result["git_tree_manifest_entry_count"] == 2


def test_git_integrity_rejects_same_paths_with_changed_blob(tmp_path: Path) -> None:
    root = _committed_repository(tmp_path)
    (root / "payload.txt").write_text("second\n", encoding="utf-8")
    _git(root, "add", "payload.txt")
    _git(root, "commit", "-m", "change payload without regenerating manifest")

    result = inspect_commit(root)
    assert result["status"] == "failed"
    assert result["content_identity_mismatches"] == ("payload.txt",)


def test_tree_manifest_refuses_a_treeish_git_would_read_as_an_option(tmp_path: Path) -> None:
    root = _committed_repository(tmp_path)
    for treeish in ("--output=/tmp/x", "-p", ""):
        with pytest.raises(ValueError, match="treeish must name a revision or tree"):
            collect_tree_entries(root, treeish)
    assert collect_tree_entries(root, "HEAD") == load_manifest(root)


def test_tree_manifest_cli_rejects_an_option_treeish(tmp_path: Path) -> None:
    root = _committed_repository(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "git_tree_manifest.py"),
            "--root",
            str(root),
            "--check",
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
    assert (root / "validation" / "result.json").is_file()
