#!/usr/bin/env python3
"""Generate and validate a Git-native tracked-content manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

MANIFEST_PATH = "GIT_TREE_MANIFEST.json"
SCHEMA_VERSION = "l9.git-tree-manifest/1.0.0"
EXCLUDED_PATHS = (MANIFEST_PATH,)


def _git_bytes(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", "replace").strip()
        if not message:
            message = completed.stdout.decode("utf-8", "replace").strip()
        raise RuntimeError(message)
    return completed.stdout


def _git_text(root: Path, *args: str) -> str:
    return _git_bytes(root, *args).decode("utf-8", "strict").strip()


def collect_tree_entries(root: Path, treeish: str) -> tuple[dict[str, str], ...]:
    """Return path, mode, object type, and Git object ID for one tree."""

    output = _git_bytes(root, "ls-tree", "-r", "--full-tree", "-z", treeish)
    entries: list[dict[str, str]] = []
    for raw_record in output.split(b"\0"):
        if not raw_record:
            continue
        metadata, separator, raw_path = raw_record.partition(b"\t")
        if not separator:
            raise RuntimeError("git ls-tree emitted a malformed record")
        metadata_parts = metadata.decode("ascii").split()
        if len(metadata_parts) != 3:
            raise RuntimeError("git ls-tree emitted malformed object metadata")
        mode, object_type, object_id = metadata_parts
        path = raw_path.decode("utf-8", "surrogateescape")
        if path in EXCLUDED_PATHS:
            continue
        entries.append(
            {
                "path": path,
                "mode": mode,
                "object_type": object_type,
                "git_object_id": object_id,
            }
        )
    return tuple(sorted(entries, key=lambda item: item["path"]))


def entries_sha256(entries: tuple[dict[str, str], ...]) -> str:
    canonical = json.dumps(
        entries,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def build_manifest(root: Path, treeish: str) -> dict[str, Any]:
    entries = collect_tree_entries(root, treeish)
    return {
        "schema_version": SCHEMA_VERSION,
        "content_scope": "all tracked Git entries except the manifest itself",
        "excluded_paths": list(EXCLUDED_PATHS),
        "entry_count": len(entries),
        "entries_sha256": entries_sha256(entries),
        "entries": list(entries),
    }


def validate_manifest_shape(manifest: object) -> tuple[dict[str, str], ...]:
    if not isinstance(manifest, dict):
        raise ValueError("Git tree manifest must be a JSON object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Git tree manifest schema_version is unsupported")
    if manifest.get("excluded_paths") != list(EXCLUDED_PATHS):
        raise ValueError("Git tree manifest excluded_paths is invalid")
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("Git tree manifest entries must be a list")
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise ValueError("Git tree manifest entry must be an object")
        if set(raw) != {"path", "mode", "object_type", "git_object_id"}:
            raise ValueError("Git tree manifest entry has unexpected fields")
        entry = {key: raw[key] for key in ("path", "mode", "object_type", "git_object_id")}
        if not all(isinstance(value, str) and value for value in entry.values()):
            raise ValueError("Git tree manifest entry fields must be non-empty strings")
        path = entry["path"]
        if path in EXCLUDED_PATHS or path in seen:
            raise ValueError(f"Git tree manifest path is excluded or duplicated: {path}")
        seen.add(path)
        entries.append(entry)
    normalized = tuple(sorted(entries, key=lambda item: item["path"]))
    if tuple(entries) != normalized:
        raise ValueError("Git tree manifest entries must be sorted by path")
    if manifest.get("entry_count") != len(normalized):
        raise ValueError("Git tree manifest entry_count does not match entries")
    if manifest.get("entries_sha256") != entries_sha256(normalized):
        raise ValueError("Git tree manifest entries_sha256 does not match entries")
    return normalized


def load_manifest(root: Path) -> tuple[dict[str, str], ...]:
    path = root / MANIFEST_PATH
    if not path.is_file():
        raise ValueError(f"Git tree manifest is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Git tree manifest is invalid JSON: {exc}") from exc
    return validate_manifest_shape(payload)


def write_manifest(root: Path, treeish: str) -> Path:
    destination = root / MANIFEST_PATH
    payload = build_manifest(root, treeish)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--treeish",
        help="Git treeish to inventory. Defaults to the current staged index via git write-tree.",
    )
    parser.add_argument("--check", action="store_true", help="Validate the committed manifest")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.check:
        expected = collect_tree_entries(root, args.treeish or "HEAD")
        actual = load_manifest(root)
        if actual != expected:
            return 1
        print(json.dumps({"status": "passed", "entry_count": len(actual)}, sort_keys=True))
        return 0
    treeish = args.treeish or _git_text(root, "write-tree")
    destination = write_manifest(root, treeish)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
