"""Bounded upstream and downstream impact traversal.

Two readings of one graph are offered, and they answer different questions.

**Generic reachability** (the default) answers "which entities are connected under
the selected edge taxonomy and direction?". It walks the traversable taxonomy,
and it is what every existing caller and the compiler's own impact stage rely on.
Reachability does not by itself prove an operational dependency.

**Resolved dependency impact** (``resolution_aware=True``, ADR-0035) answers
"which entities sit in a justified dependency chain, and which declared
dependencies stay unresolved?". It differs from reachability in three ways:

* It walks only dependency relations, ``DEPENDENCY_EDGE_TYPES``
  (``DEPENDS_ON`` and ``BLOCKED_BY``). ``CONTAINS``, ``DOCUMENTED_BY``,
  ``GOVERNED_BY`` and the other traversable relations are real, but they are not
  dependencies.
* It judges each edge's target with the rule of the producer that emitted it
  (``dependency_target_resolution``). A missing ``target_resolution`` property is
  never read as "resolved": an edge is resolved only on positive producer
  evidence.
* It never crosses an unresolved or ambiguous edge and never counts that edge's
  endpoint as affected. Every such edge the traversal reaches is reported in
  ``ImpactIndex.unresolved_edge_ids``, so the declaration stays visible.
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

#: Relations resolved dependency impact walks. Every other relation is outside
#: the dependency question, however traversable it is for reachability.
DEPENDENCY_EDGE_TYPES: frozenset[EdgeType] = frozenset({EdgeType.depends_on, EdgeType.blocked_by})

#: The edge property the work projector records when it resolves a target.
TARGET_RESOLUTION_PROPERTY = "target_resolution"

#: The work projector's one resolved state: the target is one observed artifact.
RESOLVED_TARGET_RESOLUTION = "exact-artifact"

#: The edge property the claim projector records for the endpoint it emitted.
ENDPOINT_KIND_PROPERTY = "endpoint_kind"

#: The claim projector's explicit external package identity (``package:<name>``).
EXTERNAL_PACKAGE_ENDPOINT = "external-package-reference"

#: Why a dependency edge's target is resolved or not, by originating producer.
TargetResolution = Literal[
    "resolved-exact-artifact",
    "resolved-external-package",
    "resolved-observed-entity",
    "unresolved-recorded",
    "unresolved-no-producer-evidence",
]


def dependency_target_resolution(
    edge: EdgeRecord, observed_entity_ids: frozenset[str]
) -> TargetResolution:
    """Judge a dependency edge's target with the rule of the producer that emitted it.

    * **Work projector** (records ``target_resolution``): resolved only for
      ``exact-artifact``. ``ambiguous``, ``unresolved`` and any other recorded
      value are unresolved.
    * **Claim projector, ``package.dependency``** (records ``endpoint_kind:
      external-package-reference``): resolved. The endpoint is exactly the
      external package identity the manifest named, and nothing was guessed to
      reach it (Case H). It is not claimed to be a constellation repository.
    * **Graph builder, repository upstream dependencies** (records neither):
      resolved only when the target is an entity this packet observed.
      Aggregation turns an unmatched dependency name into an unknown, not an
      edge, so an observed target is that producer's positive evidence.
    * Anything else is unresolved. Absent producer evidence is not resolution.
    """
    recorded = edge.properties.get(TARGET_RESOLUTION_PROPERTY)
    if recorded is not None:
        return (
            "resolved-exact-artifact"
            if recorded == RESOLVED_TARGET_RESOLUTION
            else "unresolved-recorded"
        )
    if edge.properties.get(ENDPOINT_KIND_PROPERTY) == EXTERNAL_PACKAGE_ENDPOINT:
        return "resolved-external-package"
    if edge.target_id in observed_entity_ids:
        return "resolved-observed-entity"
    return "unresolved-no-producer-evidence"


def edge_is_resolved(edge: EdgeRecord, observed_entity_ids: frozenset[str]) -> bool:
    """Return whether ``edge`` can carry a resolved dependency-impact conclusion."""
    return dependency_target_resolution(edge, observed_entity_ids).startswith("resolved-")


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
    observed_entity_ids: frozenset[str] = frozenset(),
) -> ImpactIndex:
    """Return generic reachability, or resolved dependency impact when asked.

    ``observed_entity_ids`` is read only with ``resolution_aware``: the entities
    the packet observed (its repositories and artifacts), which is the evidence
    a property-less graph-builder dependency edge's target needs.
    """
    if direction not in {"upstream", "downstream", "both"}:
        raise ValueError(f"invalid impact direction: {direction}")
    if maximum_depth < 0:
        raise ValueError("maximum_depth cannot be negative")
    if resolution_aware and edge_types is not None and not edge_types <= DEPENDENCY_EDGE_TYPES:
        outside = sorted(member.value for member in edge_types - DEPENDENCY_EDGE_TYPES)
        raise ValueError(
            "resolution-aware impact walks dependency relations only "
            f"({sorted(member.value for member in DEPENDENCY_EDGE_TYPES)}); not: {outside}"
        )
    # The default is the *traversable* taxonomy, not every edge type. Byte
    # identity and a textual reference are real relations that are not
    # dependencies, and defaulting to `set(EdgeType)` would have silently pulled
    # both into canonical impact the moment they were added to the enum.
    #
    # An explicit `edge_types` is still honoured verbatim: a caller that asks to
    # traverse duplicates is answering a different question deliberately, and
    # this is the one place that distinction can be made.
    if resolution_aware:
        allowed_types = set(edge_types if edge_types is not None else DEPENDENCY_EDGE_TYPES)
    else:
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
        if resolution_aware and not edge_is_resolved(edge, observed_entity_ids):
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
