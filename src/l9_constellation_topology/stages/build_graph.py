from l9_constellation_topology.domain import (
    ArtifactRecord,
    CapabilityRecord,
    EdgeRecord,
    GraphRecord,
    RepositoryRecord,
)
from l9_constellation_topology.topology.graph_builder import build_topology_graph


def run(
    repositories: tuple[RepositoryRecord, ...],
    artifacts: tuple[ArtifactRecord, ...],
    capabilities: tuple[CapabilityRecord, ...],
    declared_edges: tuple[EdgeRecord, ...],
) -> tuple[tuple[GraphRecord, ...], tuple[EdgeRecord, ...]]:
    return build_topology_graph(repositories, artifacts, capabilities, declared_edges)
