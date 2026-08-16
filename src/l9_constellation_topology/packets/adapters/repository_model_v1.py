"""Repository Model Packet v1 to canonical internal records."""

from __future__ import annotations

from dataclasses import dataclass

from l9_constellation_topology.domain import (
    ArtifactRecord,
    CapabilityRecord,
    EdgeRecord,
    RepositoryRecord,
)
from l9_constellation_topology.packets.repository_model import (
    RepositoryModelAssertion,
    RepositoryModelPacket,
)
from l9_constellation_topology.packets.validator import (
    SUPPORTED_REPOSITORY_MODEL_VERSIONS,
    validate_repository_model_packet,
)
from l9_constellation_topology.run.diagnostics import Diagnostic, normalize_diagnostic
from l9_constellation_topology.run.evidence import EvidenceRecord


@dataclass(frozen=True)
class NormalizedRepositoryModel:
    packet_id: str
    repositories: tuple[RepositoryRecord, ...]
    artifacts: tuple[ArtifactRecord, ...]
    capabilities: tuple[CapabilityRecord, ...]
    relationships: tuple[EdgeRecord, ...]
    evidence: tuple[EvidenceRecord, ...]
    diagnostics: tuple[Diagnostic, ...]
    #: Empty for 1.0.0 inputs, which carry no assertion domain.
    assertions: tuple[RepositoryModelAssertion, ...] = ()


class RepositoryModelV1Adapter:
    #: Retained for callers that report the adapter's primary contract version.
    packet_version = "1.1.0"
    supported_versions = SUPPORTED_REPOSITORY_MODEL_VERSIONS

    def adapt(self, packet: RepositoryModelPacket) -> NormalizedRepositoryModel:
        validate_repository_model_packet(packet, supported_versions=set(self.supported_versions))
        if packet.payload is None:
            raise ValueError("validated packet payload is unexpectedly absent")
        diagnostics = tuple(
            normalize_diagnostic(raw, source_packet_id=packet.packet_id, index=index)
            for index, raw in enumerate(packet.payload.diagnostics)
        )
        return NormalizedRepositoryModel(
            packet_id=packet.packet_id,
            repositories=packet.payload.repositories,
            artifacts=packet.payload.artifacts,
            capabilities=packet.payload.capabilities,
            relationships=packet.payload.relationships,
            evidence=packet.payload.evidence,
            diagnostics=diagnostics,
            assertions=packet.payload.assertions or (),
        )
