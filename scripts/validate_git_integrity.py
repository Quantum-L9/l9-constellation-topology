#!/usr/bin/env python3
"""Bind release-readiness evidence to the exact committed Git tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ENTRY_RE = re.compile(r"^- `([^`]+)`\s+—\s+.+$")


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def _manifest_paths() -> tuple[str, ...]:
    paths = []
    for line in (ROOT / "MANIFEST.md").read_text(encoding="utf-8").splitlines():
        match = MANIFEST_ENTRY_RE.match(line)
        if match:
            paths.append(match.group(1))
    return tuple(sorted(paths))


def _manifest_digest() -> str:
    content = (ROOT / "MANIFEST.md").read_bytes()
    return "sha256:" + hashlib.sha256(content).hexdigest()


def inspect_commit() -> dict[str, object]:
    commit_sha = _git("rev-parse", "HEAD")
    tree_sha = _git("rev-parse", "HEAD^{tree}")
    committed = tuple(
        sorted(line for line in _git("ls-tree", "-r", "--name-only", "HEAD").splitlines() if line)
    )
    manifest = _manifest_paths()
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    missing_from_manifest = tuple(sorted(set(committed) - set(manifest)))
    absent_from_commit = tuple(sorted(set(manifest) - set(committed)))
    result_status = "passed" if not missing_from_manifest and not absent_from_commit and not status else "failed"
    return {
        "status": result_status,
        "validated_commit_sha": commit_sha,
        "validated_tree_sha": tree_sha,
        "manifest_sha256": _manifest_digest(),
        "working_tree_clean": not bool(status),
        "committed_file_count": len(committed),
        "manifest_file_count": len(manifest),
        "missing_from_manifest": missing_from_manifest,
        "absent_from_commit": absent_from_commit,
        "working_tree_status": tuple(status.splitlines()),
        "validation_tool": "scripts/validate_git_integrity.py",
        "validation_tool_version": "1.0.0",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    args = parser.parse_args()
    result = inspect_commit()
    content = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    print(content, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
