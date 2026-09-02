"""Observation time and publication time are different coordinates.

``valid_from`` says when this compiler stated a fact. ``source_observed_at``
says when the fact was seen. Carrying only the first made a dependency declared
months ago and one added this morning arrive with the same validity start.

The absence of a retraction test here is deliberate and is the subject of
ADR-0027: a fact missing from a compile must not close a fact in durable
memory, because no producer in this pipeline asserts that it observed a scope
exhaustively.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.publication import (
    PublicationPolicy,
    build_publication_plan,
    load_publication_policy,
)

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
    ROOT / "tests/fixtures/repository_model_packets/l9-assertion-sample",
)
FIXED_TIME = datetime(2026, 3, 1, tzinfo=UTC)
LATER_TIME = datetime(2026, 9, 17, tzinfo=UTC)


@pytest.fixture(scope="module")
def policy() -> PublicationPolicy:
    return load_publication_policy(ROOT)


@pytest.fixture(scope="module")
def materialized():
    return compile_topology(ROOT, INPUTS, created_at=FIXED_TIME).materialized


@pytest.fixture(scope="module")
def plan(materialized, policy):
    return build_publication_plan(materialized, policy, published_at=FIXED_TIME)


def test_evidence_backed_facts_carry_an_observation_time(plan) -> None:
    supported = [item for item in plan.candidates if item.lowering.resolved_evidence_ids]
    assert supported, "fixture produced no evidence-backed candidates"
    assert all(item.memory_intent.request.source_observed_at is not None for item in supported)


def test_an_unsupported_fact_claims_no_observation_time(plan) -> None:
    """Publication time is not a substitute for an observation that never happened."""
    unsupported = [item for item in plan.candidates if not item.lowering.resolved_evidence_ids]
    assert all(item.memory_intent.request.source_observed_at is None for item in unsupported)


def test_observation_time_is_not_publication_time(plan) -> None:
    observed = {
        item.memory_intent.request.source_observed_at
        for item in plan.candidates
        if item.memory_intent.request.source_observed_at is not None
    }
    assert observed, "no candidate carried an observation time"
    # The point of the field is that it can differ from valid_from. If every
    # value equalled publication time the field would be decoration.
    assert observed != {FIXED_TIME}
    assert all(item.memory_intent.request.valid_from == FIXED_TIME for item in plan.candidates)


def test_republishing_at_a_later_time_does_not_re_key_an_unchanged_fact(
    materialized, policy, plan
) -> None:
    """An unchanged fact keeps its durable identity, so its valid_from cannot drift.

    The record is never rewritten on republication: the key matches, the write
    answers DUPLICATE, and the original validity start stands. That is a
    consequence of separating fact identity from write identity, and this test
    exists so a change to either temporal field cannot quietly break it.
    """
    later = build_publication_plan(materialized, policy, published_at=LATER_TIME)
    assert {item.idempotency_key for item in later.candidates} == {
        item.idempotency_key for item in plan.candidates
    }
    assert {item.candidate_id for item in later.candidates} == {
        item.candidate_id for item in plan.candidates
    }


def test_no_candidate_requests_a_retraction(plan) -> None:
    """Absence must not retract; see ADR-0027 for what would unblock it."""
    for candidate in plan.candidates:
        request = candidate.memory_intent.request
        assert candidate.memory_intent.operation == "memory.ingest"
        assert request.valid_to is None
        assert request.supersedes == ()
