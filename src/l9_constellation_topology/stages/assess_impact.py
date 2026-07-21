from l9_constellation_topology.domain import EdgeRecord, ImpactIndex, RepositoryRecord
from l9_constellation_topology.topology.impact import assess_impact


def run(
    repositories: tuple[RepositoryRecord, ...],
    edges: tuple[EdgeRecord, ...],
) -> tuple[ImpactIndex, ...]:
    return tuple(
        assess_impact(repository.repository_id, edges, direction="downstream", maximum_depth=10)
        for repository in repositories
    )
