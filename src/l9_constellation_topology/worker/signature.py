"""HMAC-SHA256 signing profile for foundational Gate-less execution."""

from __future__ import annotations

import hashlib
import hmac

from l9_constellation_topology.packets.transport import (
    TransportPacket,
    TransportSecurity,
    TransportSignature,
)
from l9_constellation_topology.run import canonical_bytes, semantic_hash

from .errors import WorkerError


def transport_signing_view(packet: TransportPacket) -> dict[str, object]:
    header = packet.header.model_dump(mode="json", exclude={"packet_id", "created_at"})
    return {
        "header": header,
        "provenance": packet.provenance,
        "governance": packet.governance,
        "attachments": packet.attachments,
        "payload": packet.payload,
    }


def calculate_transport_packet_id(packet: TransportPacket) -> str:
    digest = semantic_hash(transport_signing_view(packet))
    return f"packet:{digest.removeprefix('sha256:')}"


def _signature_value(packet: TransportPacket, key: bytes) -> str:
    digest = hmac.new(
        key,
        canonical_bytes(transport_signing_view(packet)),
        hashlib.sha256,
    ).hexdigest()
    return f"hmac-sha256:{digest}"


def sign_transport_packet(
    packet: TransportPacket,
    *,
    key: bytes,
    key_id: str,
) -> TransportPacket:
    if not key:
        raise ValueError("TransportPacket signing key may not be empty")
    packet_id = calculate_transport_packet_id(packet)
    identified = packet.model_copy(
        update={"header": packet.header.model_copy(update={"packet_id": packet_id})}
    )
    signature = TransportSignature(
        algorithm="hmac-sha256",
        key_id=key_id,
        value=_signature_value(identified, key),
    )
    return identified.model_copy(update={"security": TransportSecurity(signatures=(signature,))})


def verify_transport_packet(
    packet: TransportPacket,
    *,
    key: bytes,
    allowed_algorithms: tuple[str, ...],
    allowed_key_ids: tuple[str, ...] = (),
) -> None:
    expected_packet_id = calculate_transport_packet_id(packet)
    if packet.header.packet_id != expected_packet_id:
        raise WorkerError(
            "transport-packet-id-mismatch",
            f"expected {expected_packet_id}, got {packet.header.packet_id}",
            blocked=True,
        )
    candidates = tuple(
        signature
        for signature in packet.security.signatures
        if signature.algorithm in allowed_algorithms
        and (not allowed_key_ids or signature.key_id in allowed_key_ids)
    )
    if not candidates:
        raise WorkerError(
            "transport-signature-missing",
            "no allowed TransportPacket signature and key identity is present",
            blocked=True,
        )
    expected = _signature_value(packet, key)
    if not any(hmac.compare_digest(signature.value, expected) for signature in candidates):
        raise WorkerError(
            "transport-signature-invalid",
            "TransportPacket HMAC verification failed",
            blocked=True,
        )
