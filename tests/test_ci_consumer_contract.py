"""Organization CI consumer contract (`.l9/ci.json`) and the Biome scope.

`.l9/ci.json` is read by Quantum-L9/l9-ci-core (`l9.ci-consumer/v1`). Its
`product_kind` is descriptive: a repository that declares `node` (the
Quantum-L9/.github ProductKind for a runtime behind Constellation.Gate) is held
to the Gate routing rules as blocking. This repository has not been promoted to
a Constellation node, so it declares no ProductKind; Core reads an absent kind
as not declared, which is not a node. The promotion change is the one that
adds `"product_kind": "node"` and updates this test.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSUMER = ROOT / ".l9" / "ci.json"
BIOME = ROOT / "biome.json"

# Fields `l9.ci-consumer/v1` admits; anything else fails closed in Core.
CONSUMER_FIELDS = {"schema", "owner", "repo_class", "waiver_refs", "product_kind"}


def _load(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_consumer_contract_uses_only_admitted_fields() -> None:
    data = _load(CONSUMER)
    assert data["schema"] == "l9.ci-consumer/v1"
    assert set(data) <= CONSUMER_FIELDS, sorted(set(data) - CONSUMER_FIELDS)
    assert data["repo_class"] == "python"
    assert data["waiver_refs"] == []


def test_consumer_contract_declares_no_product_kind_before_promotion() -> None:
    data = _load(CONSUMER)
    assert "product_kind" not in data, (
        "l9-constellation-topology is not a promoted Constellation node; "
        "declare product_kind only in the promotion change"
    )


def test_biome_leaves_byte_exact_records_unformatted() -> None:
    includes = _load(BIOME)["files"]["includes"]  # type: ignore[index]
    assert isinstance(includes, list)
    for excluded in ("!evidence", "!tests/fixtures", "!HASH_LOCALITY_EVALUATION.json"):
        assert excluded in includes, excluded
