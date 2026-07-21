"""Tests for graph_builder."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample_constellation"


from l9_constellation_topology.models import Confidence, RepoCard, RepoSource
from l9_constellation_topology.scanners.repo_scanner import scan_many
from l9_constellation_topology.topology.graph_builder import build_graph, build_node


def _make_card(repo_id: str, name: str, deps: list[str]) -> RepoCard:
    return RepoCard(
        repo_id=repo_id,
        name=name,
        path=f"/fake/{repo_id}",
        primary_role="service",
        upstream_dependencies=deps,
        confidence=Confidence.medium,
    )


def test_build_node_returns_graph_record():
    card = _make_card("repo-a", "repo-a", [])
    node = build_node(card)
    assert node.id == "repo:repo-a"
    assert node.record_type.value == "node"


def test_build_graph_one_node():
    cards = [_make_card("repo-a", "repo-a", [])]
    records, edges = build_graph(cards)
    assert len(records) == 1
    assert len(edges) == 0


def test_build_graph_dependency_edge():
    cards = [
        _make_card("repo-a", "repo-a", ["repo-b"]),
        _make_card("repo-b", "repo-b", []),
    ]
    records, _edges = build_graph(cards)
    node_ids = [r.id for r in records if r.record_type.value == "node"]
    edge_records = [r for r in records if r.record_type.value == "edge"]
    assert "repo:repo-a" in node_ids
    assert "repo:repo-b" in node_ids
    assert len(edge_records) == 1
    assert edge_records[0].properties["source"] == "repo-a"
    assert edge_records[0].properties["target"] == "repo-b"


def test_build_graph_from_fixture():
    sources = [
        RepoSource(
            repo_id="l9-gate-sdk", name="l9-gate-sdk", local_path=str(FIXTURE / "l9-gate-sdk")
        ),
        RepoSource(
            repo_id="l9-mcp-server", name="l9-mcp-server", local_path=str(FIXTURE / "l9-mcp-server")
        ),
    ]
    cards = scan_many(sources)
    records, _edges = build_graph(cards)
    assert len(records) >= 2
