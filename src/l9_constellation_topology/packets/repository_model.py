"""Repository Model Packet v1 contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from l9_constellation_topology.domain.artifact import ArtifactRecord
from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.domain.capability import CapabilityRecord
from l9_constellation_topology.domain.edge import EdgeRecord
from l9_constellation_topology.domain.repository import RepositoryRecord
from l9_constellation_topology.run.evidence import EvidenceRecord

from .common import PacketValidationRef, Producer, ProfileRef, SourceSnapshot


class RepositorySubject(FrozenModel):
    repository_id: str


class RepositoryModelPayload(FrozenModel):
    repositories: tuple[RepositoryRecord, ...] = ()
    artifacts: tuple[ArtifactRecord, ...] = ()
    capabilities: tuple[CapabilityRecord, ...] = ()
    relationships: tuple[EdgeRecord, ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()
    diagnostics: tuple[dict[str, Any], ...] = ()


class RepositoryModelPacket(FrozenModel):
    packet_type: Literal["l9.repository-model"] = "l9.repository-model"
    packet_version: str
    packet_id: str
    subject: RepositorySubject
    source_snapshot: SourceSnapshot
    validation: PacketValidationRef
    producer: Producer
    profile: ProfileRef
    schema_hash: str
    semantic_hash: str
    artifact_hash: str | None = None
    payload_refs: dict[str, str] = Field(default_factory=dict)
    payload: RepositoryModelPayload | None = None
