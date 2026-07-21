from pathlib import Path

import pytest

from l9_constellation_topology.run.evidence import (
    canonical_json,
    normalize_source_path,
    semantic_hash,
)


def test_canonical_json_is_order_independent() -> None:
    assert canonical_json({"b": 2, "a": 1}) == canonical_json({"a": 1, "b": 2})


def test_semantic_hash_excludes_volatile_fields() -> None:
    left = {"name": "x", "created_at": "one", "run_id": "r1"}
    right = {"name": "x", "created_at": "two", "run_id": "r2"}
    assert semantic_hash(left) == semantic_hash(right)


def test_normalize_source_path_rejects_absolute() -> None:
    with pytest.raises(ValueError):
        normalize_source_path("/tmp/repo/file.py")


def test_normalize_source_path_relativizes_to_root(tmp_path: Path) -> None:
    child = tmp_path / "src" / "file.py"
    child.parent.mkdir()
    child.write_text("x")
    assert normalize_source_path(str(child), repository_root=tmp_path) == "src/file.py"
