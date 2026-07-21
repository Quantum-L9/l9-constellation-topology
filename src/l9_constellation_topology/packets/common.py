"""Shared packet contract value objects."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.run.evidence import utc_now

ValidationStatus = Literal["passed", "failed", "not_run", "blocked"]


class Producer(FrozenModel):
    name: str
    version: str


class ProfileRef(FrozenModel):
    id: str
    version: str
    hash: str


class SourceSnapshot(FrozenModel):
    revision: str
    semantic_hash: str


class PacketValidationRef(FrozenModel):
    status: ValidationStatus
    receipt_ref: str | None = None


class PacketLineage(FrozenModel):
    parent_packet_ids: tuple[str, ...] = ()
    root_packet_id: str | None = None
    generation: int = Field(default=0, ge=0)


class PacketFileEntry(FrozenModel):
    path: str
    media_type: str
    content_hash: str
    size_bytes: int = Field(ge=0)


class PacketBundleManifest(FrozenModel):
    manifest_version: str = "1.0.0"
    packet_id: str
    packet_type: str
    packet_version: str
    semantic_hash: str
    artifact_hash: str
    files: tuple[PacketFileEntry, ...]
    created_at: datetime = Field(default_factory=utc_now)
