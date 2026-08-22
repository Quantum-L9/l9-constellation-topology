"""Deterministically deduplicate evidence and classify divergent values.

Divergence is only a conflict where the field's declared cardinality makes two
values mutually exclusive. Set-valued fields aggregate downstream, and fields
whose cardinality is undeclared are surfaced as unknowns rather than being
turned into conflicts that were never observed.

Assertion-derived evidence is deduplicated here but deliberately not classified
here. Its ``field`` is an assertion *predicate*, whose arity is declared by the
predicate registry rather than by the field-cardinality contract this stage
reads. Judging it here would apply the wrong policy and reach the wrong answer
in both directions: fourteen values of ``package.dependency`` would be reported
as an undeclared-cardinality unknown, and two competing values of
``package.name`` would be reported as an unknown rather than as the conflict
they are. ``reconcile_assertions`` owns that judgement, with the right registry;
two stages adjudicating one fact under two policies is how a fact ends up both
aggregated and contradicted.
"""

from __future__ import annotations

from collections import defaultdict

from l9_constellation_topology.cardinality import Cardinality, cardinality_of
from l9_constellation_topology.domain import ConflictRecord, UnknownRecord
from l9_constellation_topology.packets.assertion_evidence import ASSERTION_EVIDENCE_STAGE
from l9_constellation_topology.run import EvidenceRecord, canonical_json, stable_id


def run(
    evidence: tuple[EvidenceRecord, ...],
) -> tuple[tuple[EvidenceRecord, ...], tuple[ConflictRecord, ...], tuple[UnknownRecord, ...]]:
    by_id = {record.evidence_id: record for record in evidence}
    by_subject_field: dict[tuple[str, str | None], list[EvidenceRecord]] = defaultdict(list)
    for record in by_id.values():
        if record.stage == ASSERTION_EVIDENCE_STAGE:
            continue
        by_subject_field[(record.subject_id, record.field)].append(record)

    conflicts: list[ConflictRecord] = []
    unknowns: list[UnknownRecord] = []
    for (subject_id, field), records in sorted(
        by_subject_field.items(), key=lambda item: (item[0][0], item[0][1] or "")
    ):
        # Values may be structured, so distinctness is decided canonically: two
        # mappings that differ only in key order are one value, not two.
        distinct = {canonical_json(record.value): record.value for record in records}
        values = tuple(sorted(str(value) for value in distinct.values()))
        if field is None or len(distinct) < 2:
            continue
        evidence_refs = tuple(sorted(record.evidence_id for record in records))
        cardinality = cardinality_of(field)
        if cardinality is Cardinality.SET:
            # Distinct values of a set-valued field agree; aggregation happens
            # downstream and no contradiction exists to record.
            continue
        if cardinality is Cardinality.SINGLE:
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
            continue
        unknowns.append(
            UnknownRecord(
                unknown_id=stable_id(
                    "unknown",
                    {"subject_id": subject_id, "field": field, "values": values},
                ),
                subject_id=subject_id,
                field=field,
                reason=(
                    "field cardinality is not declared; divergent values are preserved "
                    "without asserting a conflict"
                ),
                evidence_refs=evidence_refs,
            )
        )
    return (
        tuple(sorted(by_id.values(), key=lambda item: item.evidence_id)),
        tuple(conflicts),
        tuple(unknowns),
    )
