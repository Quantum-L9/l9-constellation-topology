"""A requested external effect, separated from rendered content."""

from __future__ import annotations

from l9_constellation_topology.domain.base import FrozenModel

from .rendered_artifact import RenderedArtifact


class WriteIntent(FrozenModel):
    artifact: RenderedArtifact
    expected_existing_hash: str | None = None
    required: bool = True
