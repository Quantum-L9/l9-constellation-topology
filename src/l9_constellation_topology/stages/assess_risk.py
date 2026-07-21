from typing import Any

from l9_constellation_topology.domain import RepositoryRecord, RiskRecord
from l9_constellation_topology.topology.risk import assess_topology_risks


def run(
    repositories: tuple[RepositoryRecord, ...],
    profile: dict[str, Any],
) -> tuple[RiskRecord, ...]:
    return assess_topology_risks(repositories, profile)
