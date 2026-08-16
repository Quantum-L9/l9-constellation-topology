"""Conflict detection must respect declared field cardinality.

Plurality is not contradiction. These tests pin the distinction between a
set-valued field aggregating many true values, a single-valued field holding
two incompatible claims, and a field whose cardinality nobody declared.
"""

from __future__ import annotations

from l9_constellation_topology.cardinality import (
    FIELD_CARDINALITY_CONTRACT_ID,
    FIELD_CARDINALITY_CONTRACT_VERSION,
    Cardinality,
    cardinality_of,
)
from l9_constellation_topology.domain.confidence import ConfidenceAssessment
from l9_constellation_topology.run import EvidenceSourceRef, make_evidence_record
from l9_constellation_topology.stages.reconcile_evidence import run as reconcile_evidence

_CONFIDENCE = ConfidenceAssessment(
    level="high",
    evidence_strength="direct",
    derivation_method="declared",
    authority="source",
    completeness="sufficient",
)


def _evidence(subject_id: str, field: str, value: str, source_path: str):
    return make_evidence_record(
        subject_id=subject_id,
        field=field,
        stage="test",
        evidence_class="declared",
        source_type="file",
        source_ref=EvidenceSourceRef(source_path=source_path),
        value=value,
        confidence=_CONFIDENCE,
        producer="test",
        producer_version="1.0.0",
    )


def test_multiple_languages_are_not_a_conflict() -> None:
    evidence = (
        _evidence("repo:golden", "languages", "python", "pyproject.toml"),
        _evidence("repo:golden", "languages", "shell", "bootstrap.sh"),
    )
    _, conflicts, unknowns = reconcile_evidence(evidence)
    assert conflicts == ()
    assert unknowns == ()


def test_multiple_set_valued_members_are_not_a_conflict() -> None:
    """A repository legitimately exposes many capabilities at once."""
    evidence = (
        _evidence("repo:golden", "capability_ids", "capability:execute", "spec.yaml"),
        _evidence("repo:golden", "capability_ids", "capability:describe", "spec.yaml"),
    )
    _, conflicts, unknowns = reconcile_evidence(evidence)
    assert conflicts == ()
    assert unknowns == ()


def test_contradictory_single_valued_claims_are_a_conflict() -> None:
    """Two names for one repository is a real disagreement."""
    evidence = (
        _evidence("repo:golden", "name", "l9-service", "pyproject.toml"),
        _evidence("repo:golden", "name", "golden-repo-ai-review-system", "spec.yaml"),
    )
    _, conflicts, unknowns = reconcile_evidence(evidence)
    assert unknowns == ()
    assert len(conflicts) == 1
    assert conflicts[0].field == "name"
    assert conflicts[0].values == ("golden-repo-ai-review-system", "l9-service")
    # Both competing claims survive, and both sources remain reachable.
    assert len(conflicts[0].evidence_refs) == 2


def test_undeclared_cardinality_does_not_invent_a_conflict() -> None:
    evidence = (
        _evidence("repo:golden", "not_a_declared_field", "alpha", "a.md"),
        _evidence("repo:golden", "not_a_declared_field", "beta", "b.md"),
    )
    _, conflicts, unknowns = reconcile_evidence(evidence)
    assert conflicts == ()
    assert len(unknowns) == 1
    assert unknowns[0].field == "not_a_declared_field"
    assert "cardinality is not declared" in unknowns[0].reason
    assert len(unknowns[0].evidence_refs) == 2


def test_single_value_never_conflicts_regardless_of_cardinality() -> None:
    for field in ("name", "languages", "not_a_declared_field"):
        evidence = (
            _evidence("repo:golden", field, "only", "a.md"),
            _evidence("repo:golden", field, "only", "b.md"),
        )
        _, conflicts, unknowns = reconcile_evidence(evidence)
        assert conflicts == (), field
        assert unknowns == (), field


def test_stale_and_current_authority_are_both_preserved() -> None:
    """The specimen declares itself deprecated and a reference implementation.

    The older claim is not deleted because a stronger one exists; the conflict
    record carries both values and both evidence references.
    """
    evidence = (
        _evidence("repo:golden", "primary_role", "deprecated-bootstrap", "README.md"),
        _evidence("repo:golden", "primary_role", "reference-implementation", "README.md"),
    )
    _, conflicts, _ = reconcile_evidence(evidence)
    assert len(conflicts) == 1
    assert conflicts[0].values == ("deprecated-bootstrap", "reference-implementation")


def test_reconciliation_is_deterministic() -> None:
    evidence = (
        _evidence("repo:b", "name", "two", "b.md"),
        _evidence("repo:a", "name", "one", "a.md"),
        _evidence("repo:a", "name", "uno", "c.md"),
        _evidence("repo:b", "zzz_undeclared", "x", "d.md"),
        _evidence("repo:b", "zzz_undeclared", "y", "e.md"),
    )
    first = reconcile_evidence(evidence)
    second = reconcile_evidence(tuple(reversed(evidence)))
    assert first == second


def test_declared_cardinality_matches_the_domain_records() -> None:
    assert cardinality_of("languages") is Cardinality.SET
    assert cardinality_of("upstream_repository_ids") is Cardinality.SET
    assert cardinality_of("name") is Cardinality.SINGLE
    assert cardinality_of("source_revision") is Cardinality.SINGLE
    assert cardinality_of("nothing_declares_this") is Cardinality.UNKNOWN
    assert cardinality_of(None) is Cardinality.UNKNOWN


def test_cardinality_contract_binds_to_compiler_identity() -> None:
    from pathlib import Path

    from l9_constellation_topology.stages.resolve_config import run as resolve_config

    root = Path(__file__).resolve().parents[1]
    configuration = resolve_config(root)
    assert (
        configuration.active_contract_versions[FIELD_CARDINALITY_CONTRACT_ID]
        == FIELD_CARDINALITY_CONTRACT_VERSION
    )
