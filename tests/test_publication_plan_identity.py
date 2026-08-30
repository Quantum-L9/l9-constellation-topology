"""``plan_id`` is contract identity, and the tests say which contract.

The field was carried and never pinned. Nothing said whether re-planning an
unchanged topology reproduces it, whether a policy change moves it, or whether
publication time is inside it — so a consumer had no way to know if it could
treat a repeated id as "already seen" or had to redo the work.

Each property below is one a consumer would otherwise have to guess at, and
guessing either way is expensive: treating a stable id as new work does it
twice, treating a moved id as cosmetic skips work never done.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.publication import (
    build_publication_plan,
    load_publication_policy,
)

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)
FIXED_TIME = datetime(2026, 3, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def materialized():
    return compile_topology(ROOT, INPUTS, created_at=FIXED_TIME).materialized


@pytest.fixture(scope="module")
def policy():
    return load_publication_policy(ROOT)


def test_the_id_is_derived_from_the_semantic_hash(materialized, policy) -> None:
    plan = build_publication_plan(materialized, policy, published_at=FIXED_TIME)
    assert plan.plan_id == f"publication-plan:{plan.semantic_hash.removeprefix('sha256:')}"


def test_replanning_an_unchanged_topology_reproduces_the_id(materialized, policy) -> None:
    """The property that makes it usable as "have I seen this plan?"."""
    first = build_publication_plan(materialized, policy, published_at=FIXED_TIME)
    second = build_publication_plan(materialized, policy, published_at=FIXED_TIME)
    assert first.plan_id == second.plan_id


def test_publication_time_is_outside_the_identity(materialized, policy) -> None:
    """The same plan published later is the same plan.

    If time were inside it, every re-plan would look like new work and the id
    would carry no information at all.
    """
    early = build_publication_plan(materialized, policy, published_at=FIXED_TIME)
    late = build_publication_plan(
        materialized, policy, published_at=FIXED_TIME + timedelta(days=30)
    )
    assert early.plan_id == late.plan_id
    assert early.published_at != late.published_at


def test_a_policy_change_moves_the_id(materialized, policy) -> None:
    """A plan built under different rules is a different plan.

    Narrowing the eligible edge types changes which facts are published. An id
    that did not move would tell a consumer it had already applied a plan whose
    contents it has never seen.
    """
    narrowed = policy.model_copy(
        update={"eligible_edge_types": tuple(policy.eligible_edge_types[:3])}
    )
    baseline = build_publication_plan(materialized, policy, published_at=FIXED_TIME)
    changed = build_publication_plan(materialized, narrowed, published_at=FIXED_TIME)
    assert baseline.plan_id != changed.plan_id
    assert baseline.policy_hash != changed.policy_hash


def test_the_id_binds_the_topology_it_was_planned_from(materialized, policy) -> None:
    """A plan names its source, and its identity covers that name.

    Otherwise two plans over two different topologies could share an id, and a
    consumer applying by id would write facts about the wrong compile.
    """
    plan = build_publication_plan(materialized, policy, published_at=FIXED_TIME)
    assert plan.source_topology_semantic_hash == materialized.packet.semantic_hash
    assert plan.source_topology_packet.packet_id == materialized.packet.packet_id

    moved = materialized.model_copy(
        update={
            "packet": materialized.packet.model_copy(update={"semantic_hash": "sha256:" + "e" * 64})
        }
    )
    assert build_publication_plan(moved, policy, published_at=FIXED_TIME).plan_id != plan.plan_id
