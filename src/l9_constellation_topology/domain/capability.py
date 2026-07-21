"""Canonical capability record."""

from __future__ import annotations

from pydantic import Field

from .base import FrozenModel
from .confidence import ConfidenceAssessment


class CapabilityRecord(FrozenModel):
    capability_id: str
    name: str
    description: str
    implemented_by: tuple[str, ...] = ()
    exposed_by: tuple[str, ...] = ()
    validated_by: tuple[str, ...] = ()
    governed_by: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    confidence: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment.unknown)
