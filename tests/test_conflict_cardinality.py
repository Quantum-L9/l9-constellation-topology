"""Multiplicity is not contradiction.

A repository written in Python and Shell holds two true values of one set-valued
fact. Reporting that as an unresolved conflict is not conservatism: publication
holds any candidate whose source field is in conflict, so a false conflict
silently withholds facts that were never in doubt.

These tests pin the distinction in both directions — set-valued multiplicity must
never conflict, and genuine single-valued incompatibility must always conflict —
and pin that the reconciliation policy is versioned into topology identity.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.domain import ConfidenceAssessment
from l9_constellation_topology.reconciliation import (
    RECONCILIATION_POLICY_VERSION,
    SET_VALUED_FIELDS,
    SINGLE_VALUED_FIELDS,
    cardinality_of,
    is_conflicting,
    reconciliation_policy_hash,
    reconciliation_policy_view,
)
from l9_constellation_topology.run import EvidenceSourceRef, make_evidence_record
from l9_constellation_topology.stages.reconcile_evidence import run as reconcile_evidence

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)

#: Fields the contract requires to aggregate rather than conflict.
CONTRACT_SET_VALUED = (
    "languages",
    "workflows",
    "package_managers",
    "governance_refs",
    "adr_refs",
    "artifact_ids",
    "capability_ids",
    "declared_actions",
)


def _evidence(subject: str, field: str | None, value: object, *, path: str) -> object:
    return make_evidence_record(
        subject_id=subject,
        field=field,
        stage="test",
        evidence_class="observed",
        source_type="file",
        source_ref=EvidenceSourceRef(source_path=path),
        value=value,
        confidence=ConfidenceAssessment.deterministic(),
        producer="test",
        producer_version="1.0.0",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _reconcile(field: str | None, values: tuple[object, ...]) -> tuple[tuple, tuple, tuple]:
    evidence = tuple(
        _evidence("repo:subject", field, value, path=f"observed/{index}.txt")
        for index, value in enumerate(values)
    )
    return reconcile_evidence(evidence)


@pytest.mark.parametrize("field", CONTRACT_SET_VALUED)
def test_contract_set_valued_fields_are_declared_as_sets(field: str) -> None:
    assert cardinality_of(field) == "set"
    assert field in SET_VALUED_FIELDS


def test_python_and_sql_are_not_conflicting_languages() -> None:
    _, conflicts, unknowns = _reconcile("languages", ("Python", "SQL"))
    assert conflicts == ()
    assert unknowns == ()


def test_multiple_workflows_are_not_a_conflict() -> None:
    _, conflicts, unknowns = _reconcile(
        "workflows", (".github/workflows/ci.yml", ".github/workflows/governance.yml")
    )
    assert conflicts == ()
    assert unknowns == ()


def test_multiple_governance_refs_are_not_a_conflict() -> None:
    _, conflicts, unknowns = _reconcile(
        "governance_refs", ("AGENTS.md", "SECURITY.md", "assets/CODEOWNERS")
    )
    assert conflicts == ()
    assert unknowns == ()


def test_execute_and_describe_can_coexist_as_declared_actions() -> None:
    _, conflicts, unknowns = _reconcile("declared_actions", ("execute", "describe"))
    assert conflicts == ()
    assert unknowns == ()


def test_incompatible_single_value_claims_create_a_conflict() -> None:
    _, conflicts, unknowns = _reconcile("name", ("alpha", "beta"))
    assert len(conflicts) == 1
    assert conflicts[0].field == "name"
    assert conflicts[0].values == ("alpha", "beta")
    assert unknowns == ()


def test_a_conflict_preserves_every_contributing_evidence_reference() -> None:
    evidence, conflicts, _ = _reconcile("source_revision", ("git:aaa", "git:bbb"))
    assert len(conflicts) == 1
    assert set(conflicts[0].evidence_refs) == {record.evidence_id for record in evidence}


def test_competing_authority_claims_are_preserved_not_resolved() -> None:
    """Reconciliation reports divergence; it never picks a winner."""
    _, conflicts, _ = _reconcile("primary_role", ("gateway", "worker"))
    assert len(conflicts) == 1
    assert conflicts[0].values == ("gateway", "worker")


def test_unknown_cardinality_does_not_invent_a_conflict() -> None:
    """An undeclared field yields an explicit unknown, not a contradiction."""
    evidence, conflicts, unknowns = _reconcile(
        "a_field_with_no_declared_cardinality", ("one", "two")
    )
    assert conflicts == ()
    assert len(unknowns) == 1
    assert unknowns[0].field == "a_field_with_no_declared_cardinality"
    assert set(unknowns[0].evidence_refs) == {record.evidence_id for record in evidence}
    assert "no declared cardinality" in unknowns[0].reason


def test_a_single_observed_value_is_never_divergent() -> None:
    for field in ("name", "languages", "undeclared_field"):
        _, conflicts, unknowns = _reconcile(field, ("only",))
        assert conflicts == ()
        assert unknowns == ()


def test_structured_values_differing_only_in_key_order_are_one_value() -> None:
    _, conflicts, unknowns = _reconcile(
        "name", ({"a": 1, "b": 2}, {"b": 2, "a": 1})
    )
    assert conflicts == ()
    assert unknowns == ()


def test_absent_field_carries_no_per_field_claim() -> None:
    """Evidence without a field makes no claim about a field, so it cannot conflict."""
    assert cardinality_of(None) == "unknown"
    _, conflicts, unknowns = _reconcile(None, ("one", "two"))
    assert conflicts == ()
    assert unknowns == ()


def test_no_field_is_declared_with_two_cardinalities() -> None:
    assert not SET_VALUED_FIELDS & SINGLE_VALUED_FIELDS


def test_is_conflicting_requires_single_cardinality() -> None:
    assert is_conflicting("name", ("a", "b"))
    assert not is_conflicting("languages", ("a", "b"))
    assert not is_conflicting("undeclared", ("a", "b"))
    assert not is_conflicting("name", ("a",))


def test_reconciliation_policy_is_versioned_into_topology_identity() -> None:
    """A change in reconciliation meaning cannot reuse an older packet identity."""
    result = compile_topology(ROOT, INPUTS, created_at=datetime(2026, 7, 21, tzinfo=UTC))
    policy_hashes = result.materialized.packet.policy_hashes

    assert policy_hashes["reconciliation"] == reconciliation_policy_hash()
    assert reconciliation_policy_view()["version"] == RECONCILIATION_POLICY_VERSION
    # policy_hashes participates in the topology semantic view, so binding the
    # reconciliation hash there is what makes the versioning load-bearing.
    from l9_constellation_topology.packets.topology_packet import topology_packet_semantic_view

    assert "policy_hashes" in topology_packet_semantic_view(result.materialized.packet)


def test_real_fixture_compilation_reports_no_false_conflicts() -> None:
    """The sample constellation declares set-valued facts and no contradictions."""
    result = compile_topology(ROOT, INPUTS, created_at=datetime(2026, 7, 21, tzinfo=UTC))
    state = result.materialized.state

    conflicting_set_fields = [
        conflict.field for conflict in state.conflicts if cardinality_of(conflict.field) == "set"
    ]
    assert conflicting_set_fields == []

    # Aggregation kept the values rather than discarding them to avoid a conflict.
    repository = state.repository_records[0]
    assert repository.languages == tuple(sorted(set(repository.languages)))
