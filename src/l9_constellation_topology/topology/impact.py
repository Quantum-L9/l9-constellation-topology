"""Bounded upstream and downstream impact traversal."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Literal

from l9_constellation_topology.compatibility.v4_models import (
    Confidence,
    RecordType,
)
from l9_constellation_topology.compatibility.v4_models import (
    GraphRecord as LegacyGraphRecord,
)
from l9_constellation_topology.domain import ConfidenceLevel, EdgeRecord, EdgeType, ImpactIndex
from l9_constellation_topology.domain.edge import TRAVERSABLE_EDGE_TYPES

_CONFIDENCE_ORDER = {
    ConfidenceLevel.low: 0,
    ConfidenceLevel.medium: 1,
    ConfidenceLevel.high: 2,
}


def assess_impact(
    subject_id: str,
    edges: tuple[EdgeRecord, ...],
    *,
    direction: Literal["upstream", "downstream", "both"] = "downstream",
    maximum_depth: int = 10,
    edge_types: set[EdgeType] | None = None,
    minimum_confidence: ConfidenceLevel = ConfidenceLevel.low,
) -> ImpactIndex:
    if direction not in {"upstream", "downstream", "both"}:
        raise ValueError(f"invalid impact direction: {direction}")
    if maximum_depth < 0:
        raise ValueError("maximum_depth cannot be negative")
    # The default is the *traversable* taxonomy, not every edge type. Byte
    # identity and a textual reference are real relations that are not
    # dependencies, and defaulting to `set(EdgeType)` would have silently pulled
    # both into canonical impact the moment they were added to the enum.
    #
    # An explicit `edge_types` is still honoured verbatim: a caller that asks to
    # traverse duplicates is answering a different question deliberately, and
    # this is the one place that distinction can be made.
    allowed_types = edge_types if edge_types is not None else set(TRAVERSABLE_EDGE_TYPES)
    outgoing: dict[str, list[tuple[str, str]]] = defaultdict(list)
    incoming: dict[str, list[tuple[str, str]]] = defaultdict(list)
    unresolved: list[str] = []
    for edge in edges:
        if edge.edge_type not in allowed_types:
            continue
        if _CONFIDENCE_ORDER[edge.confidence.level] < _CONFIDENCE_ORDER[minimum_confidence]:
            continue
        outgoing[edge.source_id].append((edge.target_id, edge.edge_id))
        incoming[edge.target_id].append((edge.source_id, edge.edge_id))

    traversals: list[tuple[str, dict[str, list[tuple[str, str]]]]] = []
    if direction in {"upstream", "both"}:
        traversals.append(("upstream", outgoing))
    if direction in {"downstream", "both"}:
        traversals.append(("downstream", incoming))

    affected: set[str] = set()
    paths: set[tuple[str, ...]] = set()
    for _, adjacency in traversals:
        queue: deque[tuple[str, tuple[str, ...], int]] = deque([(subject_id, (subject_id,), 0)])
        visited = {subject_id}
        while queue:
            current, path, depth = queue.popleft()
            if depth >= maximum_depth:
                continue
            for target, _edge_id in sorted(adjacency.get(current, [])):
                next_path = (*path, target)
                paths.add(next_path)
                affected.add(target)
                if target not in visited:
                    visited.add(target)
                    queue.append((target, next_path, depth + 1))

    repository_ids = tuple(sorted(entity for entity in affected if entity.startswith("repo:")))
    capability_ids = tuple(
        sorted(entity for entity in affected if entity.startswith("capability:"))
    )
    return ImpactIndex(
        subject_id=subject_id,
        direction=direction,
        maximum_depth=maximum_depth,
        affected_entity_ids=tuple(sorted(affected)),
        paths=tuple(sorted(paths)),
        unresolved_edge_ids=tuple(sorted(set(unresolved))),
        affected_repository_ids=repository_ids,
        affected_capability_ids=capability_ids,
    )


# Legacy compatibility functions.
def build_reverse_adjacency(records: list[LegacyGraphRecord]) -> dict[str, list[str]]:
    reverse: dict[str, list[str]] = defaultdict(list)
    for record in records:
        if record.record_type != RecordType.edge:
            continue
        source = record.properties.get("source")
        target = record.properties.get("target")
        if source and target:
            reverse[f"repo:{target}"].append(f"repo:{source}")
    return dict(reverse)


def blast_radius(entity_id: str, records: list[LegacyGraphRecord]) -> dict[str, Any]:
    reverse = build_reverse_adjacency(records)
    node_ids = {record.id for record in records if record.record_type == RecordType.node}
    if entity_id not in node_ids:
        return {
            "entity_id": entity_id,
            "found": False,
            "affected": [],
            "paths": [],
            "confidence": Confidence.low.value,
        }
    visited: set[str] = set()
    queue: deque[tuple[str, list[str]]] = deque([(entity_id, [entity_id])])
    paths: list[list[str]] = []
    affected: list[str] = []
    while queue:
        current, path = queue.popleft()
        for dependent in reverse.get(current, []):
            if dependent in visited:
                continue
            visited.add(dependent)
            next_path = [*path, dependent]
            paths.append(next_path)
            affected.append(dependent)
            queue.append((dependent, next_path))
    return {
        "entity_id": entity_id,
        "found": True,
        "affected": affected,
        "affected_count": len(affected),
        "paths": paths,
        "confidence": Confidence.high.value if affected else Confidence.medium.value,
        "note": "blast_radius_via_reverse_dependency_traversal",
    }
