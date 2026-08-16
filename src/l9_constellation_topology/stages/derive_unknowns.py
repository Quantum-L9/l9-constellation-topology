"""Translate producer-declared uncertainty into first-class unknown records.

A Repository Model Packet states what its producer could not establish: `primary_role` stays
`unknown`, `entrypoints` and `dependencies` are reported as unsupported by the available
evidence, and unclassifiable files are recorded as inventory unknowns. Until this stage that
uncertainty existed only as diagnostics, so `TopologyState.unknowns` held nothing but
unresolved dependency names and the publication policy's `hold_on_material_unknown` switch
had an empty channel to read — a fail-closed control that could not close.

Materiality is not a flag. `publication.eligibility` holds a candidate when an unknown has no
field or names a field the candidate asserts, so the field assigned here decides the blast
radius: a repository-scoped `primary_role` unknown holds the repository entity, while an
unclassified file scoped to `artifact_type` does not hold unrelated relationship facts.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from l9_constellation_topology.domain import UnknownRecord
from l9_constellation_topology.run import Diagnostic, stable_id

# The producer names the field it could not establish in the diagnostic itself.
FIELD_BEARING_CODES: frozenset[str] = frozenset({"unsupported-by-evidence"})

# Codes whose field is implied by the diagnostic's meaning rather than carried in it.
FIXED_FIELD_BY_CODE: Mapping[str, str] = {
    # Inventory could not classify a file. Scoped to the classification it failed to make so
    # an unrecognized extension does not hold facts that never depended on it.
    "inventory-unknown": "artifact_type",
}

UNKNOWN_BEARING_CODES: frozenset[str] = FIELD_BEARING_CODES | frozenset(FIXED_FIELD_BY_CODE)


def _declared_field(diagnostic: Diagnostic) -> str | None:
    """Read the field the producer named, or None when it named none.

    Returning None is the fail-closed direction: an unknown without a field is material to
    every candidate on its subject.
    """
    fixed = FIXED_FIELD_BY_CODE.get(diagnostic.code)
    if fixed is not None:
        return fixed
    raw: Any = diagnostic.details.get("raw")
    if not isinstance(raw, Mapping):
        return None
    details: Any = raw.get("details")
    if not isinstance(details, Mapping):
        return None
    value = details.get("field")
    return str(value) if value else None


def run(diagnostics: tuple[Diagnostic, ...]) -> tuple[UnknownRecord, ...]:
    """Return the unknown records declared by these diagnostics.

    Derivation is purely additive: the diagnostics themselves are returned to the caller
    untouched. Marking a translated diagnostic with `disposition="translated"` would read
    well, but `validation.topology_validator` conserves input diagnostics by counting the
    `preserved` disposition, and re-labelling them would make a fail-closed conservation
    rule pass for the wrong reason. Nothing is lost by leaving them alone.
    """
    unknowns: list[UnknownRecord] = []
    for diagnostic in diagnostics:
        if diagnostic.code not in UNKNOWN_BEARING_CODES or diagnostic.subject_id is None:
            continue
        field = _declared_field(diagnostic)
        unknowns.append(
            UnknownRecord(
                unknown_id=stable_id(
                    "unknown",
                    {
                        "diagnostic_id": diagnostic.diagnostic_id,
                        "subject_id": diagnostic.subject_id,
                        "field": field,
                    },
                ),
                subject_id=diagnostic.subject_id,
                field=field,
                reason=diagnostic.message,
                evidence_refs=diagnostic.evidence_refs,
            )
        )
    return tuple(sorted(unknowns, key=lambda record: record.unknown_id))
