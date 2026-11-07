import json
from pathlib import Path

from l9_constellation_topology.domain.edge import EdgeRecord, EdgeType
from l9_constellation_topology.stages.aggregate_capabilities import run as aggregate_capabilities
from l9_constellation_topology.stages.aggregate_repositories import run as aggregate_repositories
from l9_constellation_topology.stages.ingest_packets import adapt_packets, ingest_paths
from l9_constellation_topology.stages.normalize_models import run as normalize
from l9_constellation_topology.topology.capability_builder import build_capabilities
from l9_constellation_topology.topology.graph_builder import build_topology_graph

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "repository_model_packets"


def compiled_parts():
    packets = ingest_paths((FIXTURES / "l9-gate-sdk", FIXTURES / "l9-mcp-server"))
    inputs = normalize(adapt_packets(packets))
    repositories, conflicts, unknowns = aggregate_repositories(inputs.repositories)
    capabilities, _capability_conflicts = aggregate_capabilities(inputs.capabilities)
    capabilities = build_capabilities(repositories, inputs.artifacts, capabilities)
    graph, edges = build_topology_graph(
        repositories, inputs.artifacts, capabilities, inputs.relationships
    )
    return repositories, inputs.artifacts, capabilities, graph, edges, conflicts, unknowns


def test_graph_preserves_two_repository_nodes() -> None:
    _, _, _, graph, edges, _, _ = compiled_parts()
    repository_nodes = [
        record for record in graph if record.record_type == "node" and record.label == "Repository"
    ]
    assert {record.entity_id for record in repository_nodes} == {
        "repo:l9-gate-sdk",
        "repo:l9-mcp-server",
    }
    assert any(
        edge.source_id == "repo:l9-mcp-server" and edge.target_id == "repo:l9-gate-sdk"
        for edge in edges
    )


def test_graph_contains_artifact_and_capability_edges() -> None:
    _, artifacts, capabilities, _, edges, _, _ = compiled_parts()
    assert artifacts
    assert capabilities
    assert any(edge.edge_type.value == "CONTAINS" for edge in edges)
    assert any(edge.edge_type.value == "IMPLEMENTS" for edge in edges)


def test_semantic_graph_has_no_absolute_source_paths() -> None:
    _, _, _, graph, _, _, _ = compiled_parts()
    for record in graph:
        source_path = record.properties.get("source_path")
        if source_path:
            assert not str(source_path).startswith("/")


# --- ADR-0037: artifact classification is not a relation -------------------------

CLASSIFICATION_PROMOTED = {"GOVERNED_BY", "DOCUMENTED_BY", "VALIDATED_BY"}
CLASSIFIED_TYPES = {"architecture-decision", "governance", "documentation", "ci-workflow"}


def test_artifact_classification_is_not_promoted_to_a_relation() -> None:
    repositories, artifacts, _, graph, edges, _, _ = compiled_parts()
    classified = [artifact for artifact in artifacts if artifact.artifact_type in CLASSIFIED_TYPES]
    # The fixtures do contain every classified type, so the absence below is not vacuous.
    assert {artifact.artifact_type for artifact in classified} == CLASSIFIED_TYPES
    repository_ids = {repository.repository_id for repository in repositories}
    artifact_ids = {artifact.artifact_id for artifact in artifacts}
    assert not [
        edge
        for edge in edges
        if edge.edge_type.value in CLASSIFICATION_PROMOTED
        and edge.source_id in repository_ids
        and edge.target_id in artifact_ids
    ]
    # The classification itself survives as a node property, and inventory stays.
    nodes = {record.entity_id: record for record in graph if record.record_type == "node"}
    contained = {edge.target_id for edge in edges if edge.edge_type.value == "CONTAINS"}
    for artifact in classified:
        assert nodes[artifact.artifact_id].properties["artifact_type"] == artifact.artifact_type
        assert artifact.artifact_id in contained


#: Every edge the pre-ADR-0037 `foundational-two-repo` golden recorded that the
#: promotion did not create. Literal on purpose: a regenerated golden cannot
#: vouch for itself, so these ids are the record of what they were before.
PRE_ADR_0037_RETAINED_EDGE_IDS = frozenset(
    {
        "edge:0ab54ce4140474447958e85527229cb29558bb0687ec79a5b5f8965efd56440e",
        "edge:3c7bab0550a422f17a8d067aaf79ad8c80ef015203f185800a57b4c581cd2448",
        "edge:5c667c6a5adffd07fcbadeff1bd3109fc1d4dd769ddceafff31a5b566de5f8d4",
        "edge:5e6ee5aac02353cc52a521458815e12a7f7411fe4eaf7dad0ed1b9d5780ee9e4",
        "edge:742f3f52e137823c58b0a63a61ac412fdaeeda38de92e289618bd1794a015a42",
        "edge:745dc14ad3a08071dd46aafe689684ea55174edada32085426165ef8bcc4ffa8",
        "edge:7b9e8040a00002399d85dfd80160f38002e2af7e6b566b244a4995664fbfeefc",
        "edge:bcb26b22bfd5c72032c9bc9522aef656467b45223ad1c41a0cc231c57723c192",
        "edge:ccf26f542d4bf0f8a77a17720f8d46cfd9066467d694fd8d1b0960320e63680d",
        "edge:d85fdf456c96b1361a0068c3660e5a4ec23fc598a844c28f32e4b1b679d169fb",
        "edge:db2445d97aca22d40bcb1dffd2e4715bff905a92441d22875af9f34416037415",
        "edge:e6972fd66faa76edbf46a5f804d81d2751b67e1dae58800aa7a1bbcbf9333cc5",
        "edge:eaeb6d1adaec51da7aa8ad6e038e3c1534cf0c0aa85fd293c789e416c8edb992",
        "edge:eec41296fefa3ef80858bc727ea2988a6088d01c64f064099378e18947d56fd4",
    }
)


def test_retained_edges_keep_their_identity() -> None:
    """Removing the promotion re-identifies nothing else (ADR-0012, ADR-0037)."""
    golden = (
        ROOT / "tests/fixtures/topology_packets/foundational-two-repo/payload/edge-records.json"
    )
    recorded = {item["edge_id"] for item in json.loads(golden.read_text(encoding="utf-8"))}
    assert recorded == PRE_ADR_0037_RETAINED_EDGE_IDS
    _, _, _, _, edges, _, _ = compiled_parts()
    assert {edge.edge_id for edge in edges} == PRE_ADR_0037_RETAINED_EDGE_IDS


def test_producer_declared_documentation_relations_still_flow_through() -> None:
    repositories, artifacts, capabilities, _, _, _, _ = compiled_parts()
    artifact = next(item for item in artifacts if item.artifact_type == "documentation")
    declared = tuple(
        EdgeRecord(
            edge_id=f"edge:declared:{edge_type.value}",
            source_id=artifact.repository_id,
            target_id=artifact.artifact_id,
            edge_type=edge_type,
            evidence_refs=artifact.evidence_refs,
        )
        for edge_type in (EdgeType.governed_by, EdgeType.documented_by, EdgeType.validated_by)
    )
    _, edges = build_topology_graph(repositories, artifacts, capabilities, declared)
    assert {edge.edge_id for edge in declared} <= {edge.edge_id for edge in edges}
