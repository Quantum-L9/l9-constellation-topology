"""Policy governing all compiler-owned external writes."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel

from .rendered_artifact import ArtifactKind


class WritePolicy(FrozenModel):
    mode: Literal["dry-run", "write"] = "write"
    allowed_output_roots: tuple[str, ...] = (".",)
    allowed_artifact_kinds: tuple[ArtifactKind, ...]
    allow_overwrite: bool = False
    require_expected_hash_for_replace: bool = True
    enforce_path_containment: bool = True
    reject_collisions: bool = True
    atomic_writes: bool = True
    maximum_output_count: int = Field(default=1000, gt=0)
    maximum_output_bytes: int = Field(default=268_435_456, gt=0)
