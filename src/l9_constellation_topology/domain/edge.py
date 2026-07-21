"""Canonical topology edges and graph records."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field

from .base import FrozenModel
from .confidence import ConfidenceAssessment


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
