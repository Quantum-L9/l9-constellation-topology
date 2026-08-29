"""Conformance of lowered intents to the bound l9-graphiti-memory contract.

Two layers guard the seam:

* An offline structural check against a contract descriptor captured from the
  bound downstream revision by ``scripts/capture_downstream_contract.py``. It
  runs everywhere, including CI, and fails when this repository's mirror drifts
  from the recorded downstream shape. The descriptor is derived from the
  downstream models rather than hand-authored, because a hand-authored
  descriptor is a second thing that can drift: a mirror and a descriptor can
  agree with each other while both disagree with the real contract.
* A live check against the real downstream types. It runs only when
  ``L9_GRAPHITI_MEMORY_SRC`` points at a read-only checkout of
  ``Quantum-L9/l9-graphiti-memory``, and it validates intents without
  dispatching them.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args
from uuid import UUID

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.publication import (
    MemoryAssertion,
    MemoryConfidence,
    MemoryEvidenceRef,
    MemoryIngestIntent,
    MemoryProvenance,
    MemorySourceRange,
    MemoryWriteRequest,
    build_publication_plan,
    eligible_intent_document,
    load_publication_policy,
)
from l9_constellation_topology.publication.contracts import (
    DERIVATION_EVIDENCE_KINDS,
    EVIDENCE_REQUIRING_METHODS,
    ConfidenceMethodName,
    EvidenceKindName,
    MemoryClassName,
    MemoryCsvSourceLocator,
    MemoryDocxSourceLocator,
    MemoryHtmlSourceLocator,
    MemoryLineSourceLocator,
    MemoryNotebookSourceLocator,
    MemoryPdfSourceLocator,
    MemoryPptxSourceLocator,
    MemorySpreadsheetSourceLocator,
)

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
    # Included so semantic-claim intents — the kind that carries a structured
    # subject/predicate/object assertion — are validated against the downstream
    # boundary too. Without it this seam would only ever see entity and
    # relationship intents, and the newest lowering would go unchecked.
    ROOT / "tests/fixtures/repository_model_packets/l9-assertion-sample",
)
CONTRACT_FIXTURE = ROOT / "tests/fixtures/downstream_contracts/l9-graphiti-memory-contract.json"
FIXED_TIME = datetime(2026, 3, 1, tzinfo=UTC)

MIRRORS = {
    "IngestMemoryIntent": MemoryIngestIntent,
    "MemoryWriteRequest": MemoryWriteRequest,
    "Provenance": MemoryProvenance,
    "EvidenceRef": MemoryEvidenceRef,
    "Confidence": MemoryConfidence,
    "MemoryAssertion": MemoryAssertion,
    "SourceRange": MemorySourceRange,
}

#: Mirrors of the downstream ``SourceLocator`` union, variant by variant. Until
#: these existed the mirror carried no locator at all and lowering degraded
#: structured coordinates into prose, so a downstream field added here was
#: invisible until the first binary-format claim was published and the whole
#: plan was refused for an extra field.
LOCATOR_MIRRORS = {
    "line": MemoryLineSourceLocator,
    "pdf": MemoryPdfSourceLocator,
    "docx": MemoryDocxSourceLocator,
    "pptx": MemoryPptxSourceLocator,
    "spreadsheet": MemorySpreadsheetSourceLocator,
    "notebook": MemoryNotebookSourceLocator,
    "csv": MemoryCsvSourceLocator,
    "html": MemoryHtmlSourceLocator,
}


def _constraints(field: Any) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for meta in field.metadata:
        for attr in ("ge", "gt", "le", "lt", "min_length", "max_length"):
            value = getattr(meta, attr, None)
            if value is not None:
                found[attr] = value
    return found


def _literal_values(annotation: Any) -> set[str]:
    return set(annotation.__args__)


@pytest.fixture(scope="module")
def contract() -> dict[str, Any]:
    return json.loads(CONTRACT_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def intents() -> list[dict[str, Any]]:
    materialized = compile_topology(ROOT, INPUTS, created_at=FIXED_TIME).materialized
    plan = build_publication_plan(
        materialized, load_publication_policy(ROOT), published_at=FIXED_TIME
    )
    document = eligible_intent_document(plan)
    assert document["intents"], "fixture topology produced no eligible intents"
    return list(document["intents"])


@pytest.fixture(scope="module")
def claim_intents(intents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        intent
        for intent in intents
        if intent["request"]["metadata"].get("candidate_kind") == "claim"
    ]
    assert selected, "fixture topology produced no eligible semantic-claim intents"
    return selected


def test_contract_fixture_records_the_bound_downstream_revision(
    contract: dict[str, Any],
) -> None:
    assert contract["downstream_repository"] == "Quantum-L9/l9-graphiti-memory"
    assert len(contract["downstream_revision"]) == 40


def test_mirror_field_names_match_the_downstream_contract(contract: dict[str, Any]) -> None:
    for name, mirror in MIRRORS.items():
        expected = set(contract["models"][name]["fields"])
        actual = set(mirror.model_fields)
        assert actual == expected, f"{name} mirror drifted: {actual ^ expected}"


def test_mirror_required_fields_are_never_weaker_than_downstream(
    contract: dict[str, Any],
) -> None:
    for name, mirror in MIRRORS.items():
        downstream = contract["models"][name]["fields"]
        for field, spec in downstream.items():
            if spec["required"]:
                assert mirror.model_fields[field].is_required(), (
                    f"{name}.{field} must stay required"
                )


def test_downstream_models_forbid_unknown_fields(contract: dict[str, Any]) -> None:
    for name in MIRRORS:
        assert contract["models"][name]["extra"] == "forbid"


def test_mirror_enumerations_match_downstream_enums(contract: dict[str, Any]) -> None:
    assert _literal_values(MemoryClassName) == set(contract["enums"]["MemoryClass"])
    assert _literal_values(EvidenceKindName) == set(contract["enums"]["EvidenceKind"])
    assert _literal_values(ConfidenceMethodName) == set(contract["enums"]["ConfidenceMethod"])


def test_admission_rule_constants_match_downstream(contract: dict[str, Any]) -> None:
    assert (
        frozenset(contract["evidence_requiring_confidence_methods"]) == EVIDENCE_REQUIRING_METHODS
    )
    assert frozenset(contract["derivation_evidence_kinds"]) == DERIVATION_EVIDENCE_KINDS


def test_intents_satisfy_the_downstream_shape_offline(
    intents: list[dict[str, Any]], contract: dict[str, Any]
) -> None:
    intent_fields = set(contract["models"]["IngestMemoryIntent"]["fields"])
    request_fields = set(contract["models"]["MemoryWriteRequest"]["fields"])
    memory_classes = set(contract["enums"]["MemoryClass"])

    for intent in intents:
        assert set(intent) <= intent_fields
        assert intent["operation"] == "memory.ingest"
        request = intent["request"]
        assert set(request) <= request_fields
        assert request["memory_class"] in memory_classes
        assert 1 <= len(request["namespace"]) <= 300
        assert 1 <= len(request["content"]) <= 64_000
        assert 1 <= len(request["idempotency_key"]) <= 300
        assert request["dry_run"] is False
        assert len(request["provenance"]["source_digest"]) == 64
        if request["confidence"]["method"] in contract["evidence_requiring_confidence_methods"]:
            kinds = {item["kind"] for item in request["evidence"]}
            assert kinds & set(contract["derivation_evidence_kinds"])


def test_claim_intents_carry_a_structured_assertion(
    claim_intents: list[dict[str, Any]], contract: dict[str, Any]
) -> None:
    """A claim publishes as the triple it is, within downstream field bounds."""
    assertion_fields = set(contract["models"]["MemoryAssertion"]["fields"])
    for intent in claim_intents:
        request = intent["request"]
        assertion = request["assertion"]
        assert assertion is not None
        assert set(assertion) <= assertion_fields
        assert assertion["subject"]
        assert assertion["predicate"]
        assert assertion["object"]
        assert len(assertion["subject"]) <= 500
        assert len(assertion["predicate"]) <= 200
        assert len(assertion["object"]) <= 2_000
        assert request["metadata"]["assertion_predicate"] == assertion["predicate"]
        assert request["metadata"]["source_assertion_ids"]
        # Topology never fabricates a downstream record identity.
        assert request["supersedes"] == []


@pytest.mark.skipif(
    not os.environ.get("L9_GRAPHITI_MEMORY_SRC"),
    reason="set L9_GRAPHITI_MEMORY_SRC to a read-only l9-graphiti-memory checkout",
)
def test_intents_validate_against_the_real_downstream_boundary(
    intents: list[dict[str, Any]],
) -> None:
    source = Path(os.environ["L9_GRAPHITI_MEMORY_SRC"]).resolve()
    sys.path.insert(0, str(source))
    try:
        from l9_graphite_memory.integrations.constellation import (
            GateMemoryBridge,
            IngestMemoryIntent,
        )

        for intent in intents:
            validated = GateMemoryBridge.validate_intent(intent)
            assert isinstance(validated, IngestMemoryIntent)
    finally:
        sys.path.remove(str(source))


def test_locator_mirror_covers_every_downstream_variant(contract: dict[str, Any]) -> None:
    """A variant this repository cannot express is a coordinate it cannot carry."""
    assert set(LOCATOR_MIRRORS) == set(contract["source_locator_variants"])


def test_locator_mirror_fields_match_the_downstream_contract(contract: dict[str, Any]) -> None:
    for kind, mirror in LOCATOR_MIRRORS.items():
        expected = set(contract["source_locator_variants"][kind]["fields"])
        actual = set(mirror.model_fields)
        assert actual == expected, f"{kind} locator mirror drifted: {actual ^ expected}"


def test_locator_mirror_constraints_are_never_looser_than_downstream(
    contract: dict[str, Any],
) -> None:
    """A looser mirror emits values the downstream boundary refuses.

    This is the check that would have caught five topology-only locator fields
    and a ``csv.row`` bound that named a different row on each side — drift that
    was invisible while the mirror carried no locator at all, and would have
    failed an entire publication plan the first time one was emitted.
    """
    for kind, mirror in LOCATOR_MIRRORS.items():
        downstream = contract["source_locator_variants"][kind]["fields"]
        for field, spec in downstream.items():
            expected = spec.get("constraints", {})
            actual = _constraints(mirror.model_fields[field])
            for attr, value in expected.items():
                assert actual.get(attr) == value, (
                    f"{kind}.{field} constraint {attr} is {actual.get(attr)!r}, "
                    f"downstream requires {value!r}"
                )


def test_mirror_field_constraints_are_never_looser_than_downstream(
    contract: dict[str, Any],
) -> None:
    for name, mirror in MIRRORS.items():
        downstream = contract["models"][name]["fields"]
        for field, spec in downstream.items():
            expected = spec.get("constraints", {})
            actual = _constraints(mirror.model_fields[field])
            for attr, value in expected.items():
                assert actual.get(attr) == value, (
                    f"{name}.{field} constraint {attr} is {actual.get(attr)!r}, "
                    f"downstream requires {value!r}"
                )


def test_mirror_field_types_match_the_downstream_contract(contract: dict[str, Any]) -> None:
    """Same field name is not the same field.

    ``supersedes`` and ``references`` were mirrored as tuples of topology
    strings while the downstream contract holds tuples of memory record UUIDs.
    Both are empty today, so the drift was invisible; the first use would have
    emitted a topology entity id where a record id was required.
    """
    for name, mirror in MIRRORS.items():
        downstream = contract["models"][name]["fields"]
        for field, spec in downstream.items():
            mirrored = mirror.model_fields[field].annotation
            if spec["type"] == "array":
                args = [item for item in get_args(mirrored) if item is not type(None)]
                assert args, f"{name}.{field} must stay a sequence"
            if field in {"supersedes", "references"}:
                assert UUID in get_args(mirrored), (
                    f"{name}.{field} must carry downstream record UUIDs, not topology ids"
                )
