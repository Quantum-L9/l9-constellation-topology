"""Deterministically deduplicate evidence and preserve divergent values as conflicts."""

from __future__ import annotations

from collections import defaultdict

from l9_constellation_topology.domain import ConflictRecord
from l9_constellation_topology.run import EvidenceRecord, stable_id


def run(
    evidence: tuple[EvidenceRecord, ...],
) -> tuple[tuple[EvidenceRecord, ...], tuple[ConflictRecord, ...]]:
    by_id = {record.evidence_id: record for record in evidence}
    by_subject_field: dict[tuple[str, str | None], list[EvidenceRecord]] = defaultdict(list)
    for record in by_id.values():
        by_subject_field[(record.subject_id, record.field)].append(record)

    conflicts: list[ConflictRecord] = []
    for (subject_id, field), records in sorted(by_subject_field.items()):
        values = tuple(sorted({str(record.value) for record in records}))
        if field is not None and len(values) > 1:
            evidence_refs = tuple(sorted(record.evidence_id for record in records))
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
    return tuple(sorted(by_id.values(), key=lambda item: item.evidence_id)), tuple(conflicts)
