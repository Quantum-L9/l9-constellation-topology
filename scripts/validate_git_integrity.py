#!/usr/bin/env python3
"""Bind validation to the exact commit, inventory, modes, and Git blob identities."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

try:
    from scripts.git_tree_manifest import (
        MANIFEST_PATH,
        collect_tree_entries,
        entries_sha256,
        load_manifest,
    )
except ModuleNotFoundError:  # Direct script execution places scripts/ on sys.path.
    from git_tree_manifest import (
        MANIFEST_PATH,
        collect_tree_entries,
        entries_sha256,
        load_manifest,
    )

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ENTRY_RE = re.compile(r"^- `([^`]+)`\s+—\s+.+$")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def _markdown_manifest_paths(root: Path) -> tuple[str, ...]:
    paths = []
    for line in (root / "MANIFEST.md").read_text(encoding="utf-8").splitlines():
        match = MANIFEST_ENTRY_RE.match(line)
        if match:
            paths.append(match.group(1))
    return tuple(sorted(paths))


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_commit(root: Path = ROOT) -> dict[str, object]:
    root = root.resolve()
    commit_sha = _git(root, "rev-parse", "HEAD")
    tree_sha = _git(root, "rev-parse", "HEAD^{tree}")
    committed_paths = tuple(
        sorted(
            line
            for line in _git(root, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
            if line
        )
    )
    inventory_paths = _markdown_manifest_paths(root)
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")

    missing_from_inventory = tuple(sorted(set(committed_paths) - set(inventory_paths)))
    absent_from_commit = tuple(sorted(set(inventory_paths) - set(committed_paths)))

    committed_entries = collect_tree_entries(root, "HEAD")
    try:
        recorded_entries = load_manifest(root)
        manifest_error = None
    except ValueError as exc:
        recorded_entries = ()
        manifest_error = str(exc)

    committed_by_path = {entry["path"]: entry for entry in committed_entries}
    recorded_by_path = {entry["path"]: entry for entry in recorded_entries}
    missing_from_git_tree_manifest = tuple(
        sorted(set(committed_by_path) - set(recorded_by_path))
    )
    absent_from_git_tree = tuple(sorted(set(recorded_by_path) - set(committed_by_path)))
    content_identity_mismatches = tuple(
        sorted(
            path
            for path in set(committed_by_path) & set(recorded_by_path)
            if committed_by_path[path] != recorded_by_path[path]
        )
    )

    passed = not any(
        (
            missing_from_inventory,
            absent_from_commit,
            manifest_error,
            missing_from_git_tree_manifest,
            absent_from_git_tree,
            content_identity_mismatches,
            status,
        )
    )
    return {
        "status": "passed" if passed else "failed",
        "validated_commit_sha": commit_sha,
        "validated_tree_sha": tree_sha,
        "working_tree_clean": not bool(status),
        "committed_file_count": len(committed_paths),
        "inventory_manifest_file_count": len(inventory_paths),
        "git_tree_manifest_entry_count": len(recorded_entries),
        "inventory_manifest_sha256": _sha256(root / "MANIFEST.md"),
        "git_tree_manifest_sha256": _sha256(root / MANIFEST_PATH),
        "git_tree_entries_sha256": entries_sha256(committed_entries),
        "missing_from_inventory_manifest": missing_from_inventory,
        "absent_from_commit": absent_from_commit,
        "git_tree_manifest_error": manifest_error,
        "missing_from_git_tree_manifest": missing_from_git_tree_manifest,
        "absent_from_git_tree": absent_from_git_tree,
        "content_identity_mismatches": content_identity_mismatches,
        "working_tree_status": tuple(status.splitlines()),
        "validation_tool": "scripts/validate_git_integrity.py",
        "validation_tool_version": "2.0.0",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out")
    args = parser.parse_args()
    result = inspect_commit(args.root)
    content = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    print(content, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
