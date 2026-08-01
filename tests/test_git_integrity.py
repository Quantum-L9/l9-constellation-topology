from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.git_tree_manifest import write_manifest
from scripts.validate_git_integrity import inspect_commit


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
