"""Every edge type the policy admits must have been lowered at least once.

Six of the seventeen edge types in ``eligible_edge_types`` were exercised by a
fixture. The other eleven — ``DUPLICATE_OF``, ``BLOCKED_BY``, ``REFERENCES``,
``SUPERSEDES``, ``MEMBER_OF``, ``DERIVED_FROM``, ``EXPOSES``, ``PRODUCES``,
``CONSUMES``, ``ROUTES_TO`` and ``PUBLISHES_TO`` — were admitted by policy,
lowered by code, and published by nothing any test had ever looked at. An edge
type in that state is not covered by the compiler being correct in general; it is
covered by nobody having tried it.

The last test here is the one that matters over time. It compares the policy's
own list against the set these tests actually lower, so adding a type to
``eligible_edge_types`` without a case fails immediately rather than quietly
re-opening the same gap. Adding a case is a line in ``EDGE_CASES``.

Structured metadata is asserted throughout, never the human ``content`` string:
a test that parsed the sentence would pass while the data was missing, which is
the defect ``test_publication_edge_fidelity`` was written for.
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
from l9_constellation_topology.publication.lowering import lower_relationship

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)
FIXED_TIME = datetime(2026, 3, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def policy() -> PublicationPolicy:
    return load_publication_policy(ROOT)


@pytest.fixture(scope="module")
def packet():
    return compile_topology(ROOT, INPUTS, created_at=FIXED_TIME).materialized.packet


@pytest.fixture(scope="module")
def index() -> TopologyIndex:
    return TopologyIndex.build(TopologyState())


def _edge(
    edge_type: EdgeType,
    *,
    source: str,
    target: str,
    direction: Direction = Direction.outbound,
    properties: dict | None = None,
    confidence=None,
) -> EdgeRecord:
    record = EdgeRecord(
        edge_id=f"edge:{edge_type.value.lower()}:{source}-{target}",
        source_id=source,
        target_id=target,
        edge_type=edge_type,
        direction=direction,
        properties=properties or {},
    )
    if confidence is not None:
        record = record.model_copy(update={"confidence": confidence})
    return record


#: One case per policy-eligible edge type, with the properties that type carries.
#:
#: The properties are not decoration. ``DUPLICATE_OF`` means nothing without its
#: cluster and hash; ``BLOCKED_BY`` and ``REFERENCES`` are declared work
#: relations whose whole content is which declaration they came from. A case
#: lowering a bare triple would prove the type reaches the plan and nothing about
#: whether it arrives meaning anything.
EDGE_CASES: dict[EdgeType, dict] = {
    EdgeType.depends_on: {
        "source": "repo:alpha",
        "target": "package:beta",
        "properties": {"declared_in": "pyproject.toml", "version_constraint": ">=2.0"},
    },
    EdgeType.implements: {"source": "capability:auth", "target": "spec:oauth2"},
    EdgeType.exposes: {
        "source": "repo:alpha",
        "target": "capability:http-api",
        "properties": {"surface": "rest"},
    },
    EdgeType.validated_by: {"source": "capability:auth", "target": "artifact:alpha/tests/auth.py"},
    EdgeType.governed_by: {"source": "repo:alpha", "target": "artifact:alpha/CODEOWNERS"},
    EdgeType.owned_by: {"source": "repo:alpha", "target": "team:platform"},
    EdgeType.documented_by: {"source": "capability:auth", "target": "artifact:alpha/docs/auth.md"},
    EdgeType.produces: {
        "source": "repo:alpha",
        "target": "artifact:alpha/dist/alpha.whl",
        "properties": {"build_definition": "pyproject.toml"},
    },
    EdgeType.consumes: {"source": "repo:alpha", "target": "capability:queue"},
    EdgeType.derived_from: {
        "source": "artifact:alpha/schema.json",
        "target": "artifact:alpha/schema.yaml",
        "properties": {"generator": "scripts/generate_schemas.py"},
    },
    EdgeType.supersedes: {
        "source": "artifact:alpha/docs/adr/0027.md",
        "target": "artifact:alpha/docs/adr/0021.md",
        "properties": {"declared_in": "docs/adr/0027.md"},
    },
    EdgeType.routes_to: {"source": "capability:gateway", "target": "capability:auth"},
    EdgeType.publishes_to: {
        "source": "repo:alpha",
        "target": "registry:npm",
        "properties": {"declared_in": "package.json"},
    },
    EdgeType.member_of: {"source": "repo:alpha", "target": "constellation:l9"},
    EdgeType.duplicate_of: {
        "source": "artifact:alpha/LICENSE",
        "target": "artifact:beta/LICENSE",
        "direction": Direction.bidirectional,
        "properties": {
            "duplicate_cluster_id": "duplicate-cluster:9f2",
            "content_hash": "sha256:" + "c" * 64,
            "method": EXACT_DUPLICATE_METHOD,
            "cluster_member_count": 4,
            "representative_artifact_id": "artifact:alpha/LICENSE",
            "representative_is_arbitrary": True,
        },
        "confidence": duplicate_confidence(),
    },
    EdgeType.blocked_by: {
        "source": "artifact:alpha/PLAN.md",
        "target": "artifact:alpha/docs/procurement.md",
        "properties": {
            "declared_in": "PLAN.md",
            "declaration": "Blocked by: procurement",
            "target_resolution": "exact",
        },
    },
    EdgeType.references: {
        "source": "artifact:alpha/PLAN.md",
        "target": "artifact:alpha/docs/routing.md",
        "properties": {
            "declared_in": "PLAN.md",
            "declaration": "See routing.md",
            "target_resolution": "exact",
        },
    },
}


def _lower(edge_type: EdgeType, policy, packet, index):
    return lower_relationship(
        _edge(edge_type, **EDGE_CASES[edge_type]),
        policy=policy,
        packet=packet,
        index=index,
        published_at=FIXED_TIME,
    )


@pytest.mark.parametrize("edge_type", sorted(EDGE_CASES, key=lambda item: item.value))
def test_each_eligible_edge_type_lowers_to_a_structured_assertion(
    edge_type: EdgeType, policy, packet, index
) -> None:
    """The triple, the relation block, and the properties, as data."""
    lowered = _lower(edge_type, policy, packet, index)
    case = EDGE_CASES[edge_type]

    assertion = lowered.intent.request.assertion
    assert assertion is not None, edge_type
    assert assertion.subject == case["source"]
    assert assertion.predicate == edge_type.value
    assert assertion.object == case["target"]

    relation = lowered.intent.request.metadata["topology_relation"]
    assert relation["edge_type"] == edge_type.value
    assert relation["source_id"] == case["source"]
    assert relation["target_id"] == case["target"]
    assert relation["direction"] == case.get("direction", Direction.outbound).value
    assert relation["properties"] == case.get("properties", {})


@pytest.mark.parametrize("edge_type", sorted(EDGE_CASES, key=lambda item: item.value))
def test_each_eligible_edge_type_keys_a_distinct_durable_write(
    edge_type: EdgeType, policy, packet, index
) -> None:
    """Two different relations must not collide onto one durable write."""
    lowered = _lower(edge_type, policy, packet, index)
    # The key is namespaced rather than a bare digest, so a hash from another
    # producer cannot land in this one's key space by coincidence.
    namespace, _, digest = lowered.idempotency_key.partition(":")
    assert namespace == "l9-topology-publication/v3"
    assert len(digest) == 64
    assert lowered.candidate_kind == "relationship"
    assert lowered.identity["candidate_kind"] == "relationship"


def test_no_two_edge_types_share_an_idempotency_key(policy, packet, index) -> None:
    """Distinctness across the whole set, not pairwise by inspection.

    A key that did not include the predicate would look right in every
    single-type test above and merge the entire taxonomy into one write.
    """
    keys = {
        edge_type: _lower(edge_type, policy, packet, index).idempotency_key
        for edge_type in EDGE_CASES
    }
    assert len(set(keys.values())) == len(keys)


def test_the_work_relations_carry_which_declaration_they_came_from(policy, packet, index) -> None:
    """BLOCKED_BY and REFERENCES are declarations, and say so.

    Both are published only when their target resolved to exactly one observed
    artifact. A published one whose properties did not record the declaration it
    was read from would be indistinguishable from an inferred relation, which is
    what the taxonomy separates them from.
    """
    for edge_type in (EdgeType.blocked_by, EdgeType.references):
        relation = _lower(edge_type, policy, packet, index).intent.request.metadata[
            "topology_relation"
        ]
        assert relation["properties"]["declared_in"], edge_type
        assert relation["properties"]["declaration"], edge_type
        assert relation["properties"]["target_resolution"] == "exact", edge_type


def test_every_policy_eligible_edge_type_has_a_case(policy) -> None:
    """The test that keeps this file honest as the taxonomy grows.

    Compared against the policy rather than against a list written here, so a
    type admitted for publication with no case fails at once. The reverse
    direction is checked too: a case for a type the policy no longer admits is
    dead weight that would otherwise sit here looking like coverage.
    """
    eligible = {str(edge_type) for edge_type in policy.eligible_edge_types}
    covered = {edge_type.value for edge_type in EDGE_CASES}
    assert eligible - covered == set(), "policy admits an edge type no case lowers"
    assert covered - eligible == set(), "a case lowers an edge type policy does not admit"


def test_the_taxonomy_beyond_the_policy_is_deliberate(policy) -> None:
    """CONTAINS is excluded, and its exclusion is the reason to state it.

    Every other taxonomy member is eligible. If a new one is added and left out
    of the policy, this fails and someone has to say which it is and why.
    """
    eligible = {str(edge_type) for edge_type in policy.eligible_edge_types}
    everything = {edge_type.value for edge_type in EdgeType}
    assert everything - eligible == {"CONTAINS"}
