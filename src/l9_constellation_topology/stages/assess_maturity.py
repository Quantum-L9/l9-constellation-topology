from typing import Any

from l9_constellation_topology.domain import MaturityAssessment, RepositoryRecord
from l9_constellation_topology.run import EvidenceRecord
from l9_constellation_topology.topology.maturity import assess_maturity


def run(
    repositories: tuple[RepositoryRecord, ...],
    evidence: tuple[EvidenceRecord, ...],
    profile: dict[str, Any],
) -> tuple[MaturityAssessment, ...]:
    return assess_maturity(repositories, evidence, profile)
