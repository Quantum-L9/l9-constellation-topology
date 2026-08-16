"""Producer-declared uncertainty must reach the unknown register, not stop at diagnostics."""

from __future__ import annotations

from l9_constellation_topology.run.diagnostics import normalize_diagnostic
from l9_constellation_topology.stages.derive_unknowns import run as derive_unknowns

PACKET = "packet:0000000000000000000000000000000000000000000000000000000000000000"
REPO = "repo:cryptoxdog/golden-repo"
ARTIFACT = "artifact:1111111111111111111111111111111111111111111111111111111111111111"


def _diagnostic(raw: dict[str, object], index: int = 0):
    return normalize_diagnostic(raw, source_packet_id=PACKET, index=index)


def _unsupported(field: str, index: int = 0):
    return _diagnostic(
        {
            "code": "unsupported-by-evidence",
            "severity": "info",
            "category": "coverage",
            "message": f"{field} is not derivable from inventory evidence.",
            "stage": "meta-injector-inventory",
            "subject_id": REPO,
            "details": {"field": field},
        },
        index,
    )


def test_unsupported_by_evidence_becomes_an_unknown_scoped_to_its_field() -> None:
    unknowns = derive_unknowns((_unsupported("primary_role"),))
    assert len(unknowns) == 1
    assert unknowns[0].subject_id == REPO
    assert unknowns[0].field == "primary_role"
    assert "not derivable" in unknowns[0].reason


def test_inventory_unknown_is_scoped_so_it_cannot_blanket_hold() -> None:
    """An unrecognized extension must not hold facts that never depended on classification."""
    diagnostic = _diagnostic(
        {
            "code": "inventory-unknown",
            "severity": "warning",
            "category": "observation",
            "message": "Inventory recorded an unknown for deploy/x.tftpl.",
            "stage": "meta-injector-inventory",
            "subject_id": ARTIFACT,
            "details": {"source_path": "deploy/x.tftpl", "unknown": "unrecognized_extension"},
        }
    )
    unknowns = derive_unknowns((diagnostic,))
    assert len(unknowns) == 1
    assert unknowns[0].field == "artifact_type"
    assert unknowns[0].field is not None, "a None field would be material to every candidate"


def test_a_field_less_declaration_stays_material_to_everything() -> None:
    """Fail-closed: when the producer names no field, the unknown holds the whole subject."""
    diagnostic = _diagnostic(
        {
            "code": "unsupported-by-evidence",
            "severity": "info",
            "message": "Something could not be established.",
            "subject_id": REPO,
        }
    )
    unknowns = derive_unknowns((diagnostic,))
    assert unknowns[0].field is None


def test_unrelated_diagnostics_produce_no_unknowns() -> None:
    unrelated = _diagnostic(
        {"code": "folders-not-emitted", "severity": "info", "subject_id": REPO}, 1
    )
    unknowns = derive_unknowns((_unsupported("entrypoints"), unrelated))
    assert len(unknowns) == 1
    assert unknowns[0].field == "entrypoints"


def test_derivation_is_deterministic_and_ordered() -> None:
    batch = (_unsupported("entrypoints", 0), _unsupported("capabilities", 1))
    first_ids = [record.unknown_id for record in derive_unknowns(batch)]
    second_ids = [record.unknown_id for record in derive_unknowns(batch)]
    assert first_ids == second_ids == sorted(first_ids)


def test_a_diagnostic_without_a_subject_yields_no_unknown() -> None:
    diagnostic = _diagnostic({"code": "unsupported-by-evidence", "details": {"field": "x"}})
    assert derive_unknowns((diagnostic,)) == ()
