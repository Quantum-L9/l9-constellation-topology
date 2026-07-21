"""Pure bundle rendering for bounded direct-observation compatibility inputs."""

from __future__ import annotations

from l9_constellation_topology.io import RenderedArtifact
from l9_constellation_topology.packets.common import (
    PacketBundleManifest,
    PacketFileEntry,
    PacketValidationRef,
)
from l9_constellation_topology.run import artifact_hash, canonical_bytes, semantic_hash
from l9_constellation_topology.scanners.repository_model_scanner import (
    SyntheticRepositoryModelBundle,
)


def build_repository_model_bundle_artifacts(
    bundle: SyntheticRepositoryModelBundle,
) -> tuple[RenderedArtifact, ...]:
    packet = bundle.packet.model_copy(
        update={
            "validation": PacketValidationRef(
                status="passed",
                receipt_ref="receipts/validation-receipt.json",
            )
        }
    )
    packet_bytes = canonical_bytes(packet) + b"\n"
    receipt_bytes = canonical_bytes(bundle.receipt) + b"\n"
    data = (
        (
            "repository-model-packet",
            "packet.json",
            "application/json",
            packet_bytes,
            packet.semantic_hash,
        ),
        (
            "repository-model-validation-receipt",
            "receipts/validation-receipt.json",
            "application/json",
            receipt_bytes,
            bundle.receipt.semantic_hash,
        ),
    )
    artifacts = tuple(
        RenderedArtifact(
            logical_id=logical_id,
            destination_path=path,
            artifact_kind="debug-artifact",
            media_type=media_type,
            content=content,
            content_hash=artifact_hash(content),
            semantic_hash=digest,
            source_refs=(packet.packet_id,),
        )
        for logical_id, path, media_type, content, digest in data
    )
    entries = tuple(
        PacketFileEntry(
            path=artifact.destination_path,
            media_type=artifact.media_type,
            content_hash=artifact.content_hash,
            size_bytes=len(artifact.content),
        )
        for artifact in artifacts
    )
    manifest = PacketBundleManifest(
        packet_id=packet.packet_id,
        packet_type=packet.packet_type,
        packet_version=packet.packet_version,
        semantic_hash=packet.semantic_hash,
        artifact_hash=semantic_hash(entries),
        files=entries,
    )
    manifest_content = canonical_bytes(manifest) + b"\n"
    manifest_artifact = RenderedArtifact(
        logical_id="repository-model-bundle-manifest",
        destination_path="manifest.json",
        artifact_kind="debug-artifact",
        media_type="application/json",
        content=manifest_content,
        content_hash=artifact_hash(manifest_content),
        semantic_hash=manifest.artifact_hash,
        source_refs=(packet.packet_id,),
    )
    return (*artifacts, manifest_artifact)
