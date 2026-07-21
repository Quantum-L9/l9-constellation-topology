from l9_constellation_topology.domain import RepositoryRecord
from l9_constellation_topology.topology.classifier import classify_repository


def run(
    repositories: tuple[RepositoryRecord, ...],
    role_taxonomy: dict[str, list[str] | tuple[str, ...]],
) -> tuple[RepositoryRecord, ...]:
    return tuple(classify_repository(record, role_taxonomy) for record in repositories)
