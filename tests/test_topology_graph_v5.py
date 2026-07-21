from pathlib import Path

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
