"""Tests for impact/blast_radius traversal."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

from l9_constellation_topology.models import Confidence, RepoCard
from l9_constellation_topology.topology.graph_builder import build_graph
from l9_constellation_topology.topology.impact import blast_radius


def _make_card(repo_id: str, deps: list[str]) -> RepoCard:
    return RepoCard(
        repo_id=repo_id,
        name=repo_id,
        path=f"/fake/{repo_id}",
        primary_role="service",
        upstream_dependencies=deps,
        confidence=Confidence.medium,
    )


def test_blast_radius_unknown_entity():
    cards = [_make_card("a", []), _make_card("b", ["a"])]
    records, _ = build_graph(cards)
    result = blast_radius("repo:nonexistent", records)
    assert result["found"] is False


def test_blast_radius_leaf_node_no_dependents():
    cards = [_make_card("a", []), _make_card("b", ["a"])]
    records, _ = build_graph(cards)
    result = blast_radius("repo:a", records)
    assert result["found"] is True
    assert "repo:b" in result["affected"]


def test_blast_radius_no_dependents():
    cards = [_make_card("a", []), _make_card("b", ["a"])]
    records, _ = build_graph(cards)
    result = blast_radius("repo:b", records)
    assert result["found"] is True
    assert result["affected"] == []


def test_blast_radius_chain():
    cards = [
        _make_card("a", []),
        _make_card("b", ["a"]),
        _make_card("c", ["b"]),
    ]
    records, _ = build_graph(cards)
    result = blast_radius("repo:a", records)
    assert "repo:b" in result["affected"]
    assert "repo:c" in result["affected"]
