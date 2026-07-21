from l9_constellation_topology.domain import ConfidenceAssessment, RepositoryRecord
from l9_constellation_topology.stages.aggregate_repositories import run


def repo(repo_id: str, name: str, deps: tuple[str, ...] = ()) -> RepositoryRecord:
    return RepositoryRecord(
        repository_id=repo_id,
        name=name,
        source_revision="git:abc",
        packet_ref=f"packet:{name}",
        unresolved_dependencies=deps,
        confidence=ConfidenceAssessment.direct(),
    )


def test_two_repository_boundaries_are_preserved() -> None:
    records, conflicts, unknowns = run(
        (
            repo("repo:l9-gate-sdk", "l9-gate-sdk"),
            repo("repo:l9-mcp-server", "l9-mcp-server", ("l9-gate-sdk",)),
        )
    )
    assert {record.repository_id for record in records} == {
        "repo:l9-gate-sdk",
        "repo:l9-mcp-server",
    }
    mcp = next(record for record in records if record.repository_id == "repo:l9-mcp-server")
    assert mcp.upstream_repository_ids == ("repo:l9-gate-sdk",)
    assert conflicts == ()
    assert unknowns == ()


def test_conflicting_revisions_are_blocking() -> None:
    left = repo("repo:a", "a")
    right = left.model_copy(update={"source_revision": "git:def"})
    _, conflicts, _ = run((left, right))
    assert any(conflict.blocking for conflict in conflicts)
