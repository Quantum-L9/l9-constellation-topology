"""Compatibility wrapper for v5 deterministic evidence utilities."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from l9_constellation_topology.run.evidence import (
    artifact_hash,
    canonical_bytes,
    canonical_data,
    canonical_json,
    normalize_source_path,
    semantic_hash,
    sha256_bytes,
    sha256_text,
    stable_id,
)


def sha256_hash(value: str) -> str:
    """Legacy unprefixed SHA-256 helper."""
    return sha256_text(value).removeprefix("sha256:")


def deep_freeze(obj: Any) -> Any:
    if isinstance(obj, dict):
        return frozenset((key, deep_freeze(value)) for key, value in sorted(obj.items()))
    if isinstance(obj, (list, tuple)):
        return tuple(deep_freeze(value) for value in obj)
    return obj


def hash_artifact(path: Path) -> dict[str, Any]:
    content = path.read_bytes()
    return {
        "path": path.name,
        "sha256": artifact_hash(content),
        "size_bytes": len(content),
    }


def hash_all_artifacts(paths: list[Path]) -> dict[str, Any]:
    artifacts = [
        hash_artifact(path) for path in sorted(paths, key=lambda item: item.name) if path.exists()
    ]
    return {
        "artifacts": artifacts,
        "manifest_sha256": semantic_hash(artifacts),
        "generated_at": datetime.now(UTC).isoformat(),
    }


__all__ = [
    "artifact_hash",
    "canonical_bytes",
    "canonical_data",
    "canonical_json",
    "deep_freeze",
    "hash_all_artifacts",
    "hash_artifact",
    "normalize_source_path",
    "semantic_hash",
    "sha256_bytes",
    "sha256_hash",
    "sha256_text",
    "stable_id",
]
