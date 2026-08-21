"""Conformance of lowered intents to the bound l9-graphiti-memory contract.

Two layers guard the seam:

* An offline structural check against a contract descriptor captured from the
  bound downstream revision. It runs everywhere, including CI, and fails when
  this repository's mirror drifts from the recorded downstream shape.
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
from typing import Any

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
        assert assertion["subject"] and assertion["predicate"] and assertion["object"]
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
