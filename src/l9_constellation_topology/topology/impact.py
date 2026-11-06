"""Bounded upstream and downstream impact traversal.

Two readings of one graph are offered, and they answer different questions.

The default is generic reachability over the traversable edge taxonomy, the
behaviour every existing caller and the compiler's own impact stage rely on.

``resolution_aware=True`` answers the dependency-impact question instead (ADR-0035).
A work relation whose target the compiler could not resolve to one observed
artifact still exists as a canonical edge — dropping it would lose the
declaration — but its endpoint is an explicitly-labelled reference node, not a
thing whose blast radius is known. Such an edge is a *declared* dependency, not a
*resolved* one. Resolution-aware impact does not traverse it and does not count
its endpoint as affected; it reports the edge id in ``unresolved_edge_ids`` so the
declaration stays visible. Every other edge is resolved for this purpose,
including a dependency on an explicitly-labelled external package (Case H): that
identity is exactly what the source named, and nothing was guessed to reach it.
"""

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

#: The edge property a projector records when it had to resolve a target.
TARGET_RESOLUTION_PROPERTY = "target_resolution"

#: Recorded resolution states that cannot support a resolved impact conclusion.
UNRESOLVED_TARGET_RESOLUTIONS: frozenset[str] = frozenset({"unresolved", "ambiguous"})


def edge_is_resolved(edge: EdgeRecord) -> bool:
    """Return whether ``edge`` can carry a resolved dependency-impact conclusion.

    Only an edge whose projector recorded a target resolution of ``unresolved``
    or ``ambiguous`` is unresolved. An edge with no recorded resolution named its
    endpoint explicitly and is resolved for this purpose.
    """
    return edge.properties.get(TARGET_RESOLUTION_PROPERTY) not in UNRESOLVED_TARGET_RESOLUTIONS


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
    resolution_aware: bool = False,
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
    # Resolution-aware only: unresolved edges, kept apart so a traversal that
    # reaches one of their endpoints can report it without crossing it.
    unresolved_outgoing: dict[str, list[str]] = defaultdict(list)
    unresolved_incoming: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge.edge_type not in allowed_types:
            continue
        if _CONFIDENCE_ORDER[edge.confidence.level] < _CONFIDENCE_ORDER[minimum_confidence]:
            continue
        if resolution_aware and not edge_is_resolved(edge):
            unresolved_outgoing[edge.source_id].append(edge.edge_id)
            unresolved_incoming[edge.target_id].append(edge.edge_id)
            continue
        outgoing[edge.source_id].append((edge.target_id, edge.edge_id))
        incoming[edge.target_id].append((edge.source_id, edge.edge_id))

    traversals: list[tuple[dict[str, list[tuple[str, str]]], dict[str, list[str]]]] = []
    if direction in {"upstream", "both"}:
        traversals.append((outgoing, unresolved_outgoing))
    if direction in {"downstream", "both"}:
        traversals.append((incoming, unresolved_incoming))

    affected: set[str] = set()
    paths: set[tuple[str, ...]] = set()
    for adjacency, unresolved_adjacency in traversals:
        queue: deque[tuple[str, tuple[str, ...], int]] = deque([(subject_id, (subject_id,), 0)])
        visited = {subject_id}
        while queue:
            current, path, depth = queue.popleft()
            if depth >= maximum_depth:
                continue
            # A declared dependency the traversal reached but cannot cross.
            unresolved.extend(unresolved_adjacency.get(current, ()))
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
