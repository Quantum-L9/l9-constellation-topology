"""Establish repository boundaries, merge duplicate records, and resolve dependencies.

Set-valued repository facts are unioned across duplicate records. Only the
single-valued facts that identify the repository itself — its name and the
revision it was observed at — can contradict one another, and those remain
blocking conflicts.
"""

from __future__ import annotations

from collections import defaultdict

from l9_constellation_topology.domain import ConflictRecord, RepositoryRecord, UnknownRecord
from l9_constellation_topology.reconciliation import is_conflicting
from l9_constellation_topology.run import stable_id

#: Repository facts that admit exactly one true value per repository identity.
_IDENTIFYING_FIELDS = ("source_revision", "name")


def _merge_records(
    records: list[RepositoryRecord],
) -> tuple[RepositoryRecord, tuple[ConflictRecord, ...]]:
    first = records[0]
    all_evidence = tuple(sorted({ref for record in records for ref in record.evidence_refs}))
    conflicts: list[ConflictRecord] = []
    for field in _IDENTIFYING_FIELDS:
        values = tuple(sorted({getattr(record, field) for record in records}))
        if not is_conflicting(field, values):
            continue
        conflicts.append(
            ConflictRecord(
                conflict_id=stable_id(
                    "conflict",
                    {"id": first.repository_id, "field": field, "values": values},
                ),
                subject_id=first.repository_id,
                field=field,
                values=values,
                evidence_refs=all_evidence,
                blocking=True,
            )
        )

    def union(field: str) -> tuple[str, ...]:
        return tuple(sorted({value for record in records for value in getattr(record, field)}))

    merged = first.model_copy(
        update={
            "secondary_roles": union("secondary_roles"),
            "languages": union("languages"),
            "package_managers": union("package_managers"),
            "entrypoints": union("entrypoints"),
            "workflows": union("workflows"),
            "adr_refs": union("adr_refs"),
            "governance_refs": union("governance_refs"),
            "capability_ids": union("capability_ids"),
            "artifact_ids": union("artifact_ids"),
            "upstream_repository_ids": union("upstream_repository_ids"),
            "downstream_repository_ids": union("downstream_repository_ids"),
            "unresolved_dependencies": union("unresolved_dependencies"),
            "owner_ids": union("owner_ids"),
            "evidence_refs": union("evidence_refs"),
        }
    )
    return merged, tuple(conflicts)


def run(
    records: tuple[RepositoryRecord, ...],
) -> tuple[tuple[RepositoryRecord, ...], tuple[ConflictRecord, ...], tuple[UnknownRecord, ...]]:
    grouped: dict[str, list[RepositoryRecord]] = defaultdict(list)
    for record in records:
        grouped[record.repository_id].append(record)

    merged: list[RepositoryRecord] = []
    conflicts: list[ConflictRecord] = []
    for repository_id in sorted(grouped):
        item, item_conflicts = _merge_records(grouped[repository_id])
        merged.append(item)
        conflicts.extend(item_conflicts)

    name_lookup: dict[str, str] = {}
    for record in merged:
        name_lookup[record.name.lower()] = record.repository_id
        name_lookup[record.repository_id.removeprefix("repo:").lower()] = record.repository_id

    resolved_records: list[RepositoryRecord] = []
    unknowns: list[UnknownRecord] = []
    downstream: dict[str, set[str]] = defaultdict(set)
    for record in merged:
        upstream = set(record.upstream_repository_ids)
        unresolved: list[str] = []
        for dependency in record.unresolved_dependencies:
            target = name_lookup.get(dependency.lower().replace("_", "-")) or name_lookup.get(
                dependency.lower()
            )
            if target and target != record.repository_id:
                upstream.add(target)
                downstream[target].add(record.repository_id)
            elif dependency:
                unresolved.append(dependency)
                unknowns.append(
                    UnknownRecord(
                        unknown_id=stable_id(
                            "unknown",
                            {"repository_id": record.repository_id, "dependency": dependency},
                        ),
                        subject_id=record.repository_id,
                        field="upstream_repository_ids",
                        reason=f"dependency {dependency!r} does not resolve to an input repository",
                        evidence_refs=record.evidence_refs,
                    )
                )
        resolved_records.append(
            record.model_copy(
                update={
                    "upstream_repository_ids": tuple(sorted(upstream)),
                    "unresolved_dependencies": tuple(sorted(unresolved)),
                }
            )
        )

    final_records = tuple(
        record.model_copy(
            update={
                "downstream_repository_ids": tuple(
                    sorted(downstream.get(record.repository_id, set()))
                )
            }
        )
        for record in resolved_records
    )
    return final_records, tuple(conflicts), tuple(unknowns)
