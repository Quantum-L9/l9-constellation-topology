"""Repository Model Packet v1 to canonical internal records."""

from __future__ import annotations

from dataclasses import dataclass

from l9_constellation_topology.domain import (
    ArtifactRecord,
    CapabilityRecord,
    EdgeRecord,
    RepositoryRecord,
)
from l9_constellation_topology.packets.repository_model import RepositoryModelPacket
from l9_constellation_topology.packets.validator import validate_repository_model_packet
from l9_constellation_topology.run.evidence import EvidenceRecord


@dataclass(frozen=True)
class NormalizedRepositoryModel:
    repositories: tuple[RepositoryRecord, ...]
    artifacts: tuple[ArtifactRecord, ...]
    capabilities: tuple[CapabilityRecord, ...]
    relationships: tuple[EdgeRecord, ...]
    evidence: tuple[EvidenceRecord, ...]
    diagnostics: tuple[dict[str, object], ...]


class RepositoryModelV1Adapter:
    packet_version = "1.0.0"

    def adapt(self, packet: RepositoryModelPacket) -> NormalizedRepositoryModel:
        validate_repository_model_packet(packet, supported_versions={self.packet_version})
        if packet.payload is None:
            raise ValueError("validated packet payload is unexpectedly absent")
        return NormalizedRepositoryModel(
            repositories=packet.payload.repositories,
            artifacts=packet.payload.artifacts,
            capabilities=packet.payload.capabilities,
            relationships=packet.payload.relationships,
            evidence=packet.payload.evidence,
            diagnostics=packet.payload.diagnostics,
        )
