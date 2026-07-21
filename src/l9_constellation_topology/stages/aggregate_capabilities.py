"""Merge identical capability identities without discarding lineage."""

from __future__ import annotations

from collections import defaultdict

from l9_constellation_topology.domain import CapabilityRecord, ConflictRecord
from l9_constellation_topology.run import stable_id


def run(
    records: tuple[CapabilityRecord, ...],
) -> tuple[tuple[CapabilityRecord, ...], tuple[ConflictRecord, ...]]:
    grouped: dict[str, list[CapabilityRecord]] = defaultdict(list)
    for record in records:
        grouped[record.capability_id].append(record)
    merged: list[CapabilityRecord] = []
    conflicts: list[ConflictRecord] = []
    for capability_id in sorted(grouped):
        items = grouped[capability_id]
        first = items[0]
        descriptions = tuple(sorted({item.description for item in items}))
        if len(descriptions) > 1:
            conflicts.append(
                ConflictRecord(
                    conflict_id=stable_id(
                        "conflict",
                        {
                            "capability_id": capability_id,
                            "field": "description",
                            "values": descriptions,
                        },
                    ),
                    subject_id=capability_id,
                    field="description",
                    values=descriptions,
                    evidence_refs=tuple(
                        sorted({ref for item in items for ref in item.evidence_refs})
                    ),
                    blocking=False,
                )
            )

        def union(
            field: str,
            capability_items: tuple[CapabilityRecord, ...] = tuple(items),
        ) -> tuple[str, ...]:
            return tuple(
                sorted({value for item in capability_items for value in getattr(item, field)})
            )

        merged.append(
            first.model_copy(
                update={
                    "implemented_by": union("implemented_by"),
                    "exposed_by": union("exposed_by"),
                    "validated_by": union("validated_by"),
                    "governed_by": union("governed_by"),
                    "evidence_refs": union("evidence_refs"),
                }
            )
        )
    return tuple(merged), tuple(conflicts)
