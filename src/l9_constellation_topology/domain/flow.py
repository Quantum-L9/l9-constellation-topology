"""Canonical information-flow record."""

from __future__ import annotations

from pydantic import Field

from .base import FrozenModel
from .confidence import ConfidenceAssessment


class FlowRecord(FrozenModel):
    flow_id: str
    name: str
    source_id: str
    target_id: str
    flow_type: str
    packet_type: str | None = None
    description: str
    stage_sequence: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    confidence: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment.unknown)
