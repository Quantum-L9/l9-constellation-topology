"""Deduplicate evidence and classify divergent values by declared cardinality.

Divergence is classified, never suppressed. A single-valued fact observed with
two values is a conflict. A set-valued fact observed with two values is an
aggregate. A fact whose cardinality the policy does not declare produces an
explicit unknown so the divergence stays visible without being misreported as a
contradiction. Every branch keeps the full evidence reference set.
"""

from __future__ import annotations

from collections import defaultdict

from l9_constellation_topology.domain import ConflictRecord, UnknownRecord
from l9_constellation_topology.reconciliation import (
    UNDECLARED_CARDINALITY_REASON,
    cardinality_of,
)
from l9_constellation_topology.run import EvidenceRecord, canonical_json, stable_id


def run(
    evidence: tuple[EvidenceRecord, ...],
) -> tuple[tuple[EvidenceRecord, ...], tuple[ConflictRecord, ...], tuple[UnknownRecord, ...]]:
    by_id = {record.evidence_id: record for record in evidence}
    by_subject_field: dict[tuple[str, str | None], list[EvidenceRecord]] = defaultdict(list)
    for record in by_id.values():
        by_subject_field[(record.subject_id, record.field)].append(record)

    conflicts: list[ConflictRecord] = []
    unknowns: list[UnknownRecord] = []
    for (subject_id, field), records in sorted(
        by_subject_field.items(), key=lambda item: (item[0][0], item[0][1] or "")
    ):
        # Values may be structured, so distinctness is decided canonically: two
        # mappings that differ only in key order are one value, not two. The
        # rendered form stays human-readable for operators reading a conflict.
        distinct = {canonical_json(record.value): record.value for record in records}
        values = tuple(sorted(str(value) for value in distinct.values()))
        if field is None or len(distinct) < 2:
            continue
        evidence_refs = tuple(sorted(record.evidence_id for record in records))
        cardinality = cardinality_of(field)
        if cardinality == "single":
            conflicts.append(
                ConflictRecord(
                    conflict_id=stable_id(
                        "conflict",
                        {"subject_id": subject_id, "field": field, "values": values},
                    ),
                    subject_id=subject_id,
                    field=field,
                    values=values,
                    evidence_refs=evidence_refs,
                    blocking=False,
                )
            )
        elif cardinality == "unknown":
            unknowns.append(
                UnknownRecord(
                    unknown_id=stable_id(
                        "unknown",
                        {"subject_id": subject_id, "field": field, "values": values},
                    ),
                    subject_id=subject_id,
                    field=field,
                    reason=f"{UNDECLARED_CARDINALITY_REASON}: {field!r} observed with "
                    f"{len(values)} distinct values",
                    evidence_refs=evidence_refs,
                )
            )
        # A set-valued fact aggregates in the record-merging stages that own it.
        # Nothing is dropped here: every contributing evidence record survives.
    return (
        tuple(sorted(by_id.values(), key=lambda item: item.evidence_id)),
        tuple(conflicts),
        tuple(unknowns),
    )
