"""An edge must publish as more than a triple and a sentence.

Lowering used to read only ``source_id``, ``edge_type``, ``target_id`` and
``direction`` off an ``EdgeRecord``, and only the first three reached the
downstream intent as data — direction survived inside the human ``content``
string and ``properties`` did not survive at all.

``DUPLICATE_OF`` is where that hurt most. Its whole meaning is in its
properties: which exact cluster the two files belong to, the content hash both
endpoints carry, the method that decided the relation, how large the cluster is,
and an explicit statement that the star's centre is arbitrary. Published without
them it read as a directional relation between two files, with no cluster,
nothing to re-check, and no sign that picking that centre meant nothing — which
is the opposite of what the taxonomy says the relation is.

These tests assert the structured data, never the prose. A test that parsed
``content`` would pass while the defect stood.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.domain.edge import (
    EXACT_DUPLICATE_METHOD,
    Direction,
    EdgeRecord,
    EdgeType,
    duplicate_confidence,
)
from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.publication import (
    PublicationPolicy,
    TopologyIndex,
    load_publication_policy,
)
from l9_constellation_topology.publication.contracts import LOWERING_CONTRACT_VERSION
from l9_constellation_topology.publication.lowering import lower_relationship, relation_metadata

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)
FIXED_TIME = datetime(2026, 3, 1, tzinfo=UTC)

DUPLICATE_PROPERTIES = {
    "duplicate_cluster_id": "duplicate-cluster:9f2",
    "content_hash": "sha256:" + "c" * 64,
    "method": EXACT_DUPLICATE_METHOD,
    "cluster_member_count": 4,
    "representative_artifact_id": "artifact:alpha/LICENSE",
    "representative_is_arbitrary": True,
}


@pytest.fixture(scope="module")
def policy() -> PublicationPolicy:
    return load_publication_policy(ROOT)


@pytest.fixture(scope="module")
def packet():
    return compile_topology(ROOT, INPUTS, created_at=FIXED_TIME).materialized.packet


@pytest.fixture(scope="module")
def index() -> TopologyIndex:
    return TopologyIndex.build(TopologyState())


def _duplicate_edge() -> EdgeRecord:
    return EdgeRecord(
        edge_id="edge:duplicate:alpha-beta",
        source_id="artifact:alpha/LICENSE",
        target_id="artifact:beta/LICENSE",
        edge_type=EdgeType.duplicate_of,
        direction=Direction.bidirectional,
        properties=dict(DUPLICATE_PROPERTIES),
        confidence=duplicate_confidence(),
    )


def _lower(record: EdgeRecord, policy: PublicationPolicy, packet, index: TopologyIndex):
    return lower_relationship(
        record, policy=policy, packet=packet, index=index, published_at=FIXED_TIME
    )


def test_duplicate_of_properties_reach_the_intent_as_data(policy, packet, index) -> None:
    lowered = _lower(_duplicate_edge(), policy, packet, index)
    relation = lowered.intent.request.metadata["topology_relation"]
    assert relation["properties"] == DUPLICATE_PROPERTIES


def test_bidirectional_direction_is_structured_not_prose(policy, packet, index) -> None:
    """A symmetric relation must not read as a directional one.

    The assertion triple has to put one endpoint first; nothing about that order
    was observed. Direction is what tells a reader so, and it has to be a field
    rather than a phrase inside a sentence.
    """
    lowered = _lower(_duplicate_edge(), policy, packet, index)
    relation = lowered.intent.request.metadata["topology_relation"]
    assert relation["direction"] == "bidirectional"
    assert relation["properties"]["representative_is_arbitrary"] is True


def test_outbound_direction_survives_for_an_ordinary_edge(policy, packet, index) -> None:
    record = EdgeRecord(
        edge_id="edge:dep:alpha-beta",
        source_id="repo:alpha",
        target_id="package:beta",
        edge_type=EdgeType.depends_on,
        direction=Direction.outbound,
    )
    relation = _lower(record, policy, packet, index).intent.request.metadata["topology_relation"]
    assert relation["direction"] == "outbound"
    assert relation["edge_type"] == "DEPENDS_ON"
    assert relation["source_id"] == "repo:alpha"
    assert relation["target_id"] == "package:beta"


def test_the_assertion_triple_is_unchanged(policy, packet, index) -> None:
    """Structured metadata is additive: the triple is still the fact."""
    lowered = _lower(_duplicate_edge(), policy, packet, index)
    assertion = lowered.intent.request.assertion
    assert assertion is not None
    assert assertion.subject == "artifact:alpha/LICENSE"
    assert assertion.predicate == "DUPLICATE_OF"
    assert assertion.object == "artifact:beta/LICENSE"


def test_only_relationships_carry_a_relation_block(policy, packet, index) -> None:
    """An entity or claim has no edge, so it must not claim to have one."""
    from l9_constellation_topology.domain.repository import RepositoryRecord
    from l9_constellation_topology.publication.lowering import lower_repository

    record = RepositoryRecord(
        repository_id="repo:alpha", name="alpha", source_revision="abc", packet_ref="p"
    )
    lowered = lower_repository(
        record, policy=policy, packet=packet, index=index, published_at=FIXED_TIME
    )
    assert "topology_relation" not in lowered.intent.request.metadata


def test_relation_metadata_carries_no_unserializable_value(policy, packet, index) -> None:
    """Properties are canonicalized, so a plan stays JSON round-trippable."""
    import json

    relation = relation_metadata(_duplicate_edge())
    assert json.loads(json.dumps(relation)) == relation


def test_richer_lowering_requests_a_different_durable_write(policy, packet, index) -> None:
    """The contract version moved, so the effect key moved with it.

    A fact lowered under v2 states more than the same fact under v1. Keying the
    richer write as a retry of the poorer one is what would make the downstream
    answer DUPLICATE and drop the added structure, so this is the version field
    doing its job rather than a regression to paper over.
    """
    from l9_constellation_topology.publication.identity import idempotency_key

    lowered = _lower(_duplicate_edge(), policy, packet, index)
    assert LOWERING_CONTRACT_VERSION == "lowering/v2"
    assert lowered.intent.request.metadata["lowering_contract_version"] == "lowering/v2"
    under_v1 = idempotency_key(lowered.identity, lowering_contract_version="lowering/v1")
    assert lowered.idempotency_key != under_v1
