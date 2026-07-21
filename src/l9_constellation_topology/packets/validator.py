"""Packet-level validation independent of topology invariants."""

from __future__ import annotations

from dataclasses import dataclass

from l9_constellation_topology.run.evidence import semantic_hash

from .repository_model import RepositoryModelPacket


@dataclass(frozen=True)
class PacketValidationError(ValueError):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def repository_model_semantic_view(packet: RepositoryModelPacket) -> dict[str, object]:
    return {
        "packet_type": packet.packet_type,
        "packet_version": packet.packet_version,
        "subject": packet.subject,
        "source_snapshot": packet.source_snapshot,
        "producer": packet.producer,
        "profile": packet.profile,
        "schema_hash": packet.schema_hash,
        "payload_refs": packet.payload_refs,
        "payload": packet.payload,
    }


def validate_repository_model_packet(
    packet: RepositoryModelPacket,
    *,
    supported_versions: set[str] | None = None,
) -> None:
    versions = supported_versions or {"1.0.0"}
    if packet.packet_version not in versions:
        raise PacketValidationError(
            "unsupported-contract-version",
            f"repository model packet version {packet.packet_version!r} is not supported",
        )
    if packet.validation.status != "passed":
        raise PacketValidationError(
            "input-validation-failed",
            f"parent packet validation status is {packet.validation.status!r}",
        )
    if not packet.source_snapshot.revision:
        raise PacketValidationError("missing-source-revision", "source revision is required")
    if packet.payload is None:
        raise PacketValidationError("missing-payload", "repository model payload is unresolved")
    calculated = semantic_hash(repository_model_semantic_view(packet))
    if calculated != packet.semantic_hash:
        raise PacketValidationError(
            "semantic-hash-mismatch",
            f"expected {packet.semantic_hash}, calculated {calculated}",
        )
