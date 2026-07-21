"""Canonical artifact record."""

from __future__ import annotations

from pydantic import Field, field_validator

from l9_constellation_topology.run.evidence import normalize_source_path

from .base import FrozenModel
from .confidence import ConfidenceAssessment


class ArtifactRecord(FrozenModel):
    artifact_id: str
    repository_id: str
    source_path: str
    artifact_type: str
    family: str | None = None
    content_hash: str
    body_hash: str | None = None
    capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    packet_ref: str
    confidence: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment.unknown)

    @field_validator("source_path")
    @classmethod
    def path_is_portable(cls, value: str) -> str:
        return normalize_source_path(value)
