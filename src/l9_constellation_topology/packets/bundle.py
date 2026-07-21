"""Topology Packet bundle rendering without external effects."""

from __future__ import annotations

from datetime import datetime

from l9_constellation_topology.domain import TopologyState
from l9_constellation_topology.io import RenderedArtifact
from l9_constellation_topology.run.evidence import (
    artifact_hash,
    canonical_bytes,
    semantic_hash,
    utc_now,
)

from .common import PacketBundleManifest, PacketFileEntry
from .payloads import topology_payload_bytes, topology_payload_path
from .topology_packet import TopologyPacket
from .validation_receipt import ValidationReceipt


def _artifact(
    *,
    logical_id: str,
    destination_path: str,
    artifact_kind: str,
    media_type: str,
    content: bytes,
    semantic_digest: str | None,
    source_refs: tuple[str, ...],
) -> RenderedArtifact:
    return RenderedArtifact(
        logical_id=logical_id,
        destination_path=destination_path,
        artifact_kind=artifact_kind,  # type: ignore[arg-type]
        media_type=media_type,
        content=content,
        content_hash=artifact_hash(content),
        semantic_hash=semantic_digest,
        source_refs=source_refs,
    )


def build_topology_bundle_artifacts(
    packet: TopologyPacket,
    state: TopologyState,
    receipt: ValidationReceipt,
    *,
    created_at: datetime | None = None,
) -> tuple[RenderedArtifact, ...]:
    if receipt.status != "passed":
        raise ValueError("cannot render a canonical bundle for failed topology validation")
    payloads = topology_payload_bytes(state)
    artifacts: list[RenderedArtifact] = []
    for field in sorted(payloads):
        artifacts.append(
            _artifact(
                logical_id=f"topology-payload:{field}",
                destination_path=topology_payload_path(field),
                artifact_kind="topology-packet",
                media_type="application/json",
                content=payloads[field],
                semantic_digest=packet.payload_hashes[field],
                source_refs=(packet.packet_id,),
            )
        )

    packet_bytes = canonical_bytes(packet) + b"\n"
    receipt_bytes = canonical_bytes(receipt) + b"\n"
    artifacts.extend(
        (
            _artifact(
                logical_id="topology-packet",
                destination_path="packet.json",
                artifact_kind="topology-packet",
                media_type="application/json",
                content=packet_bytes,
                semantic_digest=packet.semantic_hash,
                source_refs=tuple(ref.packet_id for ref in packet.inputs.repository_model_packets),
            ),
            _artifact(
                logical_id="topology-validation-receipt",
                destination_path="receipts/validation-receipt.json",
                artifact_kind="validation-receipt",
                media_type="application/json",
                content=receipt_bytes,
                semantic_digest=receipt.semantic_hash,
                source_refs=(packet.packet_id,),
            ),
        )
    )

    entries = tuple(
        PacketFileEntry(
            path=item.destination_path,
            media_type=item.media_type,
            content_hash=item.content_hash,
            size_bytes=len(item.content),
        )
        for item in sorted(artifacts, key=lambda artifact: artifact.destination_path)
    )
    manifest = PacketBundleManifest(
        packet_id=packet.packet_id,
        packet_type=packet.packet_type,
        packet_version=packet.packet_version,
        semantic_hash=packet.semantic_hash,
        artifact_hash=semantic_hash(entries),
        files=entries,
        created_at=created_at if created_at is not None else utc_now(),
    )
    manifest_bytes = canonical_bytes(manifest) + b"\n"
    artifacts.append(
        _artifact(
            logical_id="topology-bundle-manifest",
            destination_path="manifest.json",
            artifact_kind="topology-packet",
            media_type="application/json",
            content=manifest_bytes,
            semantic_digest=manifest.artifact_hash,
            source_refs=(packet.packet_id,),
        )
    )
    return tuple(sorted(artifacts, key=lambda artifact: artifact.destination_path))
