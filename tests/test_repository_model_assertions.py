"""Repository-model 1.1.0 carries semantic assertions; 1.0.0 still loads.

The assertion domain exists so semantic claims survive the packet boundary as
typed, evidence-linked data rather than as prose smuggled through diagnostics.
These tests pin both halves of that contract: the new domain round-trips intact,
and packets emitted before it existed are unaffected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_constellation_topology.packets.adapters.repository_model_v1 import (
    RepositoryModelV1Adapter,
)
from l9_constellation_topology.packets.loader import load_repository_model_bundle
from l9_constellation_topology.packets.repository_model import (
    AssertionSourceRange,
    RepositoryModelAssertion,
    RepositoryModelPacket,
    RepositoryModelPayload,
)
from l9_constellation_topology.packets.validator import (
    SUPPORTED_REPOSITORY_MODEL_VERSIONS,
    PacketValidationError,
    repository_model_semantic_view,
    validate_repository_model_packet,
)
from l9_constellation_topology.run.evidence import semantic_hash

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk"


def _assertion(
    predicate: str = "package.framework", obj: str = "fastapi"
) -> RepositoryModelAssertion:
    return RepositoryModelAssertion(
        assertion_id=f"assertion:{predicate}:{obj}",
        subject_id="repo:sample",
        predicate=predicate,
        object=obj,
        source_path="pyproject.toml",
        source_range=AssertionSourceRange(start_line=12, end_line=12),
        evidence_excerpt='fastapi = ">=0.135.1,<0.137.0"',
        source_content_hash="sha256:" + "a" * 64,
        extractor_id="manifest/v1",
        evidence_class="declared",
        authority="source",
        confidence="high",
    )


def _packet(version: str, payload: RepositoryModelPayload) -> RepositoryModelPacket:
    packet = RepositoryModelPacket(
        packet_version=version,
        packet_id="packet:pending",
        subject={"repository_id": "repo:sample"},
        source_snapshot={"revision": "git:" + "0" * 40, "semantic_hash": "sha256:" + "b" * 64},
        validation={"status": "passed"},
        producer={"name": "test", "version": "1.0.0"},
        profile={"id": "p", "version": "1.0.0", "hash": "sha256:" + "c" * 64},
        schema_hash="sha256:" + "d" * 64,
        semantic_hash="sha256:pending",
        payload=payload,
    )
    digest = semantic_hash(repository_model_semantic_view(packet))
    return packet.model_copy(update={"semantic_hash": digest, "packet_id": f"packet:{digest[7:]}"})


def test_both_contract_versions_are_supported() -> None:
    assert frozenset({"1.0.0", "1.1.0"}) == SUPPORTED_REPOSITORY_MODEL_VERSIONS
    assert "1.1.0" in RepositoryModelV1Adapter.supported_versions
    assert "1.0.0" in RepositoryModelV1Adapter.supported_versions


def test_assertions_survive_the_packet_boundary_intact() -> None:
    payload = RepositoryModelPayload(assertions=(_assertion(),))
    packet = _packet("1.1.0", payload)
    validate_repository_model_packet(packet)

    normalized = RepositoryModelV1Adapter().adapt(packet)
    assert len(normalized.assertions) == 1
    carried = normalized.assertions[0]
    original = _assertion()
    # Evidence and its exact span must survive; a lossy carry defeats the point.
    assert carried.source_path == original.source_path
    assert carried.source_range.start_line == 12
    assert carried.source_range.end_line == 12
    assert carried.source_content_hash == original.source_content_hash
    assert carried.evidence_excerpt == original.evidence_excerpt
    assert carried.extractor_id == "manifest/v1"
    assert carried.evidence_class == "declared"


def test_a_packet_without_the_domain_still_loads() -> None:
    """1.0.0 predates assertions entirely and must be unaffected."""
    packet = _packet("1.0.0", RepositoryModelPayload())
    validate_repository_model_packet(packet)
    normalized = RepositoryModelV1Adapter().adapt(packet)
    assert normalized.assertions == ()


def test_absent_and_empty_assertion_domains_are_distinct() -> None:
    """An absent domain must not be hashed as an empty one.

    A 1.0.0 packet carries no `assertions` key. Serializing that absence as `[]`
    would silently change the identity of every previously emitted packet.
    """
    absent = _packet("1.0.0", RepositoryModelPayload())
    empty = _packet("1.1.0", RepositoryModelPayload(assertions=()))
    assert absent.payload is not None and absent.payload.assertions is None
    assert empty.payload is not None and empty.payload.assertions == ()
    assert absent.semantic_hash != empty.semantic_hash


def test_changing_an_assertion_changes_packet_identity() -> None:
    baseline = _packet("1.1.0", RepositoryModelPayload(assertions=(_assertion(),)))
    changed = _packet(
        "1.1.0",
        RepositoryModelPayload(assertions=(_assertion(obj="django"),)),
    )
    assert baseline.semantic_hash != changed.semantic_hash


def test_an_unsupported_version_is_still_rejected() -> None:
    packet = _packet("2.0.0", RepositoryModelPayload())
    with pytest.raises(PacketValidationError, match="unsupported-contract-version"):
        validate_repository_model_packet(packet)


def test_committed_fixture_bundle_still_loads_unchanged() -> None:
    """The checked-in 1.0.0 bundle must load without a translation shim."""
    bundle = load_repository_model_bundle(FIXTURE)
    assert bundle.packet.packet_version in SUPPORTED_REPOSITORY_MODEL_VERSIONS
    normalized = RepositoryModelV1Adapter().adapt(bundle.packet)
    assert normalized.repositories
