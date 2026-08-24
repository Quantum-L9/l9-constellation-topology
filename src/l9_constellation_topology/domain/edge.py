"""Canonical topology edges and graph records.

The edge taxonomy is versioned. Every member is a relation some observation
actually established, and adding one is a contract change rather than a
convenience: an edge type is what downstream traversal, impact, and publication
all key on, so a type that means something slightly different from what a
consumer assumed is worse than no type at all.

Three members were added for corpus topology, and what each is allowed to mean
is stated here rather than left to the code that emits it:

``DUPLICATE_OF``
    Exact byte identity. Not similarity, not a matching filename, not a high
    embedding score. It is the one relation in this taxonomy that is *decided*
    rather than observed or declared, and it is symmetric.

``BLOCKED_BY``
    A document explicitly declared that its work is blocked by something. A
    declaration, never inferred from a status or a missing file.

``REFERENCES``
    A document explicitly named another. Weaker than ``DEPENDS_ON``: naming
    something is not depending on it, and collapsing the two would turn every
    "see also" into a dependency edge that impact analysis would then traverse.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field

from l9_constellation_topology.run.evidence import semantic_hash

from .base import FrozenModel
from .confidence import (
    Authority,
    Completeness,
    ConfidenceAssessment,
    ConfidenceLevel,
    DerivationMethod,
    EvidenceStrength,
)

EDGE_TAXONOMY_ID = "l9-topology-edge-taxonomy"

#: 2.0.0 adds ``DUPLICATE_OF``, ``BLOCKED_BY``, and ``REFERENCES``, and declares
#: which edge types canonical impact traversal admits. 1.x had neither the three
#: members nor the traversal declaration.
EDGE_TAXONOMY_VERSION = "2.0.0"


class EdgeType(StrEnum):
    contains = "CONTAINS"
    depends_on = "DEPENDS_ON"
    implements = "IMPLEMENTS"
    exposes = "EXPOSES"
    validated_by = "VALIDATED_BY"
    governed_by = "GOVERNED_BY"
    owned_by = "OWNED_BY"
    documented_by = "DOCUMENTED_BY"
    produces = "PRODUCES"
    consumes = "CONSUMES"
    derived_from = "DERIVED_FROM"
    supersedes = "SUPERSEDES"
    routes_to = "ROUTES_TO"
    publishes_to = "PUBLISHES_TO"
    member_of = "MEMBER_OF"
    #: Exact byte identity. See the module docstring: nothing weaker qualifies.
    duplicate_of = "DUPLICATE_OF"
    #: An explicitly declared blocker.
    blocked_by = "BLOCKED_BY"
    #: An explicit textual reference. Weaker than a dependency.
    references = "REFERENCES"


#: Edge types canonical impact traversal must not follow.
#:
#: ``DUPLICATE_OF`` says two files hold the same bytes. It says nothing about one
#: needing the other, so following it would make every copy of a shared licence
#: file a dependency hop and connect otherwise unrelated repositories through it.
#: The relation is real and worth recording; it is not a dependency, and impact
#: is a dependency question.
#:
#: ``REFERENCES`` is excluded for the same reason at lower volume: a document
#: mentioning another is not a dependency on it.
NON_TRAVERSABLE_EDGE_TYPES: frozenset[EdgeType] = frozenset(
    {EdgeType.duplicate_of, EdgeType.references}
)

#: Edge types canonical impact traversal admits by default.
TRAVERSABLE_EDGE_TYPES: frozenset[EdgeType] = frozenset(EdgeType) - NON_TRAVERSABLE_EDGE_TYPES


#: Method recorded on every ``DUPLICATE_OF`` edge and its evidence, so the graph
#: states what decided the relation rather than leaving it to be assumed.
EXACT_DUPLICATE_METHOD = "content-hash-equality/v1"


def canonical_pair(left: str, right: str) -> tuple[str, str]:
    """Return two endpoints of a symmetric relation in a fixed order.

    Byte equality is symmetric, so ``(a, b)`` and ``(b, a)`` are one relation and
    must hash to one identity. Ordering by identity is what makes that true
    regardless of which side the producer happened to write first.
    """
    return (left, right) if left <= right else (right, left)


def duplicate_confidence() -> ConfidenceAssessment:
    """Return the confidence of a byte-identity relation.

    ``validated_machine`` rather than ``source``: no repository *declared* these
    files identical, a comparison established it. It is nonetheless the strongest
    derivation this compiler has — equality of two hashes is decided, not
    inferred — so the level is high and the method is deterministic.
    """
    return ConfidenceAssessment(
        level=ConfidenceLevel.high,
        evidence_strength=EvidenceStrength.direct,
        derivation_method=DerivationMethod.deterministic,
        authority=Authority.validated_machine,
        completeness=Completeness.complete,
    )


def edge_taxonomy_view() -> dict[str, object]:
    """Return the exact edge semantics this compiler build applies."""
    return {
        "id": EDGE_TAXONOMY_ID,
        "version": EDGE_TAXONOMY_VERSION,
        "edge_types": sorted(member.value for member in EdgeType),
        "non_traversable_edge_types": sorted(member.value for member in NON_TRAVERSABLE_EDGE_TYPES),
    }


def edge_taxonomy_hash() -> str:
    """Return the hash bound into ``TopologyPacket.policy_hashes``."""
    return semantic_hash(edge_taxonomy_view())


class Direction(StrEnum):
    outbound = "outbound"
    inbound = "inbound"
    bidirectional = "bidirectional"


class EdgeRecord(FrozenModel):
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    direction: Direction = Direction.outbound
    properties: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    confidence: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment.unknown)


class GraphRecord(FrozenModel):
    record_type: Literal["node", "edge"]
    label: str
    entity_id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    confidence: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment.unknown)
