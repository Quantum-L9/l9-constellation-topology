"""Rendered bytes with explicit identity and provenance."""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator, model_validator

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.run.evidence import artifact_hash, normalize_source_path

ArtifactKind = Literal[
    "topology-packet",
    "validation-receipt",
    "report-manifest",
    "human-report",
    "graph-export",
    "risk-report",
    "maturity-report",
    "diagram",
    "debug-artifact",
    "commit-receipt",
]


class RenderedArtifact(FrozenModel):
    logical_id: str
    destination_path: str
    artifact_kind: ArtifactKind
    media_type: str
    content: bytes
    content_hash: str
    semantic_hash: str | None = None
    source_refs: tuple[str, ...] = ()

    @field_validator("destination_path")
    @classmethod
    def destination_is_relative(cls, value: str) -> str:
        return normalize_source_path(value)

    @model_validator(mode="after")
    def content_hash_matches(self) -> RenderedArtifact:
        calculated = artifact_hash(self.content)
        if self.content_hash != calculated:
            raise ValueError(
                f"content_hash mismatch for {self.logical_id}: "
                f"expected {self.content_hash}, calculated {calculated}"
            )
        return self
