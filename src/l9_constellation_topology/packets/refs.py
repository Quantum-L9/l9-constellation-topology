"""Packet references passed between workflow stages."""

from __future__ import annotations

from l9_constellation_topology.domain.base import FrozenModel

from .common import ValidationStatus


class PacketRef(FrozenModel):
    packet_id: str
    packet_type: str
    packet_version: str
    uri: str
    semantic_hash: str
    artifact_hash: str | None = None
    validation_status: ValidationStatus
    subject_id: str | None = None
    source_revision: str | None = None
