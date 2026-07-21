"""Deterministic read-only source snapshot identity."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import NamedTuple

from l9_constellation_topology.run.evidence import artifact_hash, semantic_hash


class SourceSnapshotResult(NamedTuple):
    revision: str
    semantic_hash: str


def _git_revision(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    value = completed.stdout.strip()
    return f"git:{value}" if value else None


def compute_source_snapshot(root: Path) -> SourceSnapshotResult:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"source root does not exist: {root}")
    ignored = {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "outputs",
    }
    members: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in ignored for part in relative.parts):
            continue
        members.append(
            {"path": relative.as_posix(), "content_hash": artifact_hash(path.read_bytes())}
        )
    tree_hash = semantic_hash(members)
    revision = _git_revision(root) or f"tree:{tree_hash.removeprefix('sha256:')}"
    return SourceSnapshotResult(revision, tree_hash)
