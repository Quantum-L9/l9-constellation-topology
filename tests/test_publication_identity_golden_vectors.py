"""The producer's identity algorithm is pinned by vectors the consumer also asserts.

``l9-graphiti-memory`` reimplements this repository's publication identity
algorithm, because a consumer that verified a producer's claim using the
producer's own code would prove only that the code is self-consistent. Two
implementations of one algorithm drift silently unless something holds them
together; this file is that thing.

The same ``golden-vectors.json`` lives in both repositories and is asserted by
both. A change here that moves a digest — the volatile-field set, canonical JSON
formatting, the evidence sort, the effect-identity domain string — fails this
suite in the producer before it can fail a real plan in the consumer.

Regenerating the vectors is a deliberate act: it means the effect-identity
algorithm changed, which re-keys every durable write the pipeline requests. Bump
``IDEMPOTENCY_ALGORITHM_VERSION``, regenerate in both repositories, and say so in
the change that does it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from l9_constellation_topology.publication.contracts import LOWERING_CONTRACT_VERSION
from l9_constellation_topology.publication.identity import (
    IDEMPOTENCY_ALGORITHM_VERSION,
    candidate_id,
    candidate_identity,
    confidence_semantics,
    evidence_semantics,
    idempotency_key,
)

VECTOR_FILE = (
    Path(__file__).resolve().parent / "fixtures" / "publication_identity" / "golden-vectors.json"
)


def _document() -> dict[str, Any]:
    return json.loads(VECTOR_FILE.read_text(encoding="utf-8"))


def _vectors() -> list[dict[str, Any]]:
    return _document()["vectors"]


def _identity(vector: dict[str, Any]) -> dict[str, Any]:
    spec = vector["identity"]
    return candidate_identity(
        operation=spec["operation"],
        candidate_kind=spec["candidate_kind"],
        namespace=spec["namespace"],
        memory_class=spec["memory_class"],
        content=spec["content"],
        assertion=spec["assertion"],
        source_topology_entity_ids=tuple(spec["source_topology_entity_ids"]),
    )


def test_vector_file_pins_the_versions_this_build_implements() -> None:
    document = _document()
    assert document["effect_identity_algorithm_version"] == IDEMPOTENCY_ALGORITHM_VERSION
    assert document["lowering_contract_version"] == LOWERING_CONTRACT_VERSION
    assert document["generated_from"]["producer_repository"] == (
        "Quantum-L9/l9-constellation-topology"
    )


@pytest.mark.parametrize("vector", _vectors(), ids=lambda item: item["label"])
def test_candidate_id_is_unchanged(vector: dict[str, Any]) -> None:
    assert candidate_id(_identity(vector)) == vector["expected_candidate_id"]


@pytest.mark.parametrize("vector", _vectors(), ids=lambda item: item["label"])
def test_idempotency_key_is_unchanged(vector: dict[str, Any]) -> None:
    document = _document()
    recomputed = idempotency_key(
        _identity(vector),
        lowering_contract_version=document["lowering_contract_version"],
        local_evidence=tuple(
            evidence_semantics(
                evidence_kind=item["evidence_kind"],
                source_content_digest=item["source_content_digest"],
                stable_source_locator=item["stable_source_locator"],
            )
            for item in vector["local_evidence"]
        ),
        confidence=confidence_semantics(**vector["confidence"]),
        derivation_kind=vector["derivation_kind"],
    )
    assert recomputed == vector["expected_idempotency_key"]
