#!/usr/bin/env python3
"""Capture the bound l9-graphiti-memory write contract as a descriptor.

The descriptor under ``tests/fixtures/downstream_contracts/`` is what lets this
repository's mirror be checked offline, in CI, without depending on the
downstream package. It was previously hand-authored, which made it a second
thing that could drift: a mirror and a descriptor can agree with each other
while both disagree with the real contract, and nothing would say so.

This script derives it from the downstream models instead, so the only way the
descriptor moves is that the contract moved.

    L9_GRAPHITI_MEMORY_SRC=/path/to/l9-graphiti-memory/src \\
        python3 scripts/capture_downstream_contract.py

It captures, per model: the field set, requiredness, the JSON type, and the
validation constraints a mirror must not be looser than. It also captures the
``SourceLocator`` union variant by variant — the union the mirror carries
structured document coordinates through, and the place a silently added
downstream field would otherwise turn into a rejected plan the first time a
binary-format claim was published.

The downstream checkout is only read. Nothing is written outside this
repository's fixture directory.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, get_args, get_origin

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "downstream_contracts"
    / "l9-graphiti-memory-contract.json"
)

#: Constraint attributes a mirror must reproduce. A downstream bound the mirror
#: does not carry is a value the mirror would emit and the boundary would refuse.
_CONSTRAINT_ATTRS = ("ge", "gt", "le", "lt", "min_length", "max_length")


def _json_type(annotation: Any) -> str:
    """Name the JSON shape of a field, ignoring optionality and containers."""
    args = [item for item in get_args(annotation) if item is not type(None)]
    if get_origin(annotation) is not None and args:
        if get_origin(annotation) in (tuple, list, set, frozenset):
            return "array"
        if len(args) == 1:
            return _json_type(args[0])
        return "union"
    if annotation is bool:
        return "boolean"
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is str:
        return "string"
    if annotation is dict or get_origin(annotation) is dict:
        return "object"
    return "object"


def _field_spec(field: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {"required": field.is_required()}
    spec["type"] = _json_type(field.annotation)
    constraints: dict[str, Any] = {}
    for meta in field.metadata:
        for attr in _CONSTRAINT_ATTRS:
            value = getattr(meta, attr, None)
            if value is not None:
                constraints[attr] = value
    if constraints:
        spec["constraints"] = constraints
    return spec


def _model_spec(model: Any) -> dict[str, Any]:
    return {
        "extra": model.model_config.get("extra", "ignore"),
        "fields": {name: _field_spec(field) for name, field in model.model_fields.items()},
    }


def main() -> int:
    source = os.environ.get("L9_GRAPHITI_MEMORY_SRC")
    if not source:
        sys.stderr.write(
            "set L9_GRAPHITI_MEMORY_SRC to a read-only l9-graphiti-memory src/ checkout\n"
        )
        return 2
    source_path = Path(source).resolve()
    sys.path.insert(0, str(source_path))

    from l9_graphite_memory.contracts import evidence, memory, requests
    from l9_graphite_memory.contracts.enums import ConfidenceMethod, EvidenceKind, MemoryClass
    from l9_graphite_memory.integrations.constellation import IngestMemoryIntent

    repo_root = source_path.parent
    revision = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    models = {
        "IngestMemoryIntent": IngestMemoryIntent,
        "MemoryWriteRequest": requests.MemoryWriteRequest,
        "Provenance": evidence.Provenance,
        "EvidenceRef": evidence.EvidenceRef,
        "Confidence": evidence.Confidence,
        "MemoryAssertion": memory.MemoryAssertion,
        "SourceRange": evidence.SourceRange,
    }
    locators = {
        "line": evidence.LineSourceLocator,
        "pdf": evidence.PdfSourceLocator,
        "docx": evidence.DocxSourceLocator,
        "pptx": evidence.PptxSourceLocator,
        "spreadsheet": evidence.SpreadsheetSourceLocator,
        "notebook": evidence.NotebookSourceLocator,
        "csv": evidence.CsvSourceLocator,
        "html": evidence.HtmlSourceLocator,
    }

    document = {
        "downstream_repository": "Quantum-L9/l9-graphiti-memory",
        "downstream_revision": revision,
        "captured_by": "scripts/capture_downstream_contract.py",
        "enums": {
            "MemoryClass": [member.value for member in MemoryClass],
            "EvidenceKind": [member.value for member in EvidenceKind],
            "ConfidenceMethod": [member.value for member in ConfidenceMethod],
        },
        "evidence_requiring_confidence_methods": [
            ConfidenceMethod.INFERRED.value,
            ConfidenceMethod.AGGREGATED.value,
        ],
        "derivation_evidence_kinds": [
            EvidenceKind.INFERENCE.value,
            EvidenceKind.AGGREGATION.value,
            EvidenceKind.SOURCE_EXCERPT.value,
        ],
        "models": {name: _model_spec(model) for name, model in sorted(models.items())},
        "source_locator_variants": {
            kind: _model_spec(model) for kind, model in sorted(locators.items())
        },
    }
    FIXTURE.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(
        f"captured {len(models)} models and {len(locators)} locator variants "
        f"from {revision[:12]} -> {FIXTURE}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
