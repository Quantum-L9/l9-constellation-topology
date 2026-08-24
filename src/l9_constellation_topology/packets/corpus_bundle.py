"""Render and load Corpus Intelligence Packet bundles.

The bundle shape mirrors the Repository Model and Topology bundles exactly — a
``packet.json``, one JSON file per payload domain, and a ``manifest.json``
binding every member to its hash — because a consumer that already knows how to
verify one packet bundle should not need a second procedure for this one.

Splitting the payload across files rather than embedding it is what makes
``payload_hashes`` useful: a domain's hash is the hash of the exact bytes on
disk, so a reader can verify one domain without materializing the rest, and a
change confined to one domain is visible as a change to one hash.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from l9_constellation_topology.io import RenderedArtifact
from l9_constellation_topology.run.evidence import (
    artifact_hash,
    canonical_bytes,
    semantic_hash,
    utc_now,
)

from .common import PacketBundleManifest, PacketFileEntry
from .corpus_intelligence import (
    CORPUS_PAYLOAD_FIELDS,
    CorpusIntelligencePacket,
    CorpusIntelligencePayload,
    corpus_intelligence_semantic_view,
    corpus_payload_path,
    corpus_payload_refs,
)


def corpus_payload_bytes(payload: CorpusIntelligencePayload) -> dict[str, bytes]:
    """Return the canonical bytes of each payload domain."""
    return {
        field: canonical_bytes(getattr(payload, field)) + b"\n" for field in CORPUS_PAYLOAD_FIELDS
    }


def corpus_payload_hashes(payload: CorpusIntelligencePayload) -> dict[str, str]:
    """Return the hash of each payload domain's exact serialized bytes."""
    return {
        field: artifact_hash(content) for field, content in corpus_payload_bytes(payload).items()
    }


def calculate_corpus_semantic_hash(packet: CorpusIntelligencePacket) -> str:
    return semantic_hash(corpus_intelligence_semantic_view(packet))


def finalize_corpus_intelligence_packet(
    packet: CorpusIntelligencePacket,
) -> CorpusIntelligencePacket:
    """Bind payload refs, payload hashes, and identity to the carried payload.

    Identity is derived rather than supplied, so a caller cannot hand in a
    packet whose declared hash disagrees with its own contents.
    """
    if packet.payload is None:
        raise ValueError("cannot finalize a corpus intelligence packet without a payload")
    candidate = packet.model_copy(
        update={
            "payload_refs": corpus_payload_refs(),
            "payload_hashes": corpus_payload_hashes(packet.payload),
            "packet_id": "packet:pending",
            "semantic_hash": "sha256:pending",
        }
    )
    digest = calculate_corpus_semantic_hash(candidate)
    return candidate.model_copy(
        update={
            "packet_id": f"packet:{digest.removeprefix('sha256:')}",
            "semantic_hash": digest,
        }
    )


def build_corpus_intelligence_bundle_artifacts(
    packet: CorpusIntelligencePacket,
    *,
    created_at: datetime | None = None,
) -> tuple[RenderedArtifact, ...]:
    """Render every file of a corpus intelligence bundle."""
    if packet.payload is None:
        raise ValueError("cannot render a corpus intelligence bundle without a payload")
    payloads = corpus_payload_bytes(packet.payload)
    mismatched = tuple(
        sorted(
            field
            for field, content in payloads.items()
            if packet.payload_hashes.get(field) != artifact_hash(content)
        )
    )
    if mismatched:
        raise ValueError(
            "corpus payload hashes do not match the carried payload: "
            f"{', '.join(mismatched)}; finalize the packet before rendering"
        )

    def _artifact(
        logical_id: str, destination: str, content: bytes, digest: str | None
    ) -> RenderedArtifact:
        return RenderedArtifact(
            logical_id=logical_id,
            destination_path=destination,
            artifact_kind="debug-artifact",
            media_type="application/json",
            content=content,
            content_hash=artifact_hash(content),
            semantic_hash=digest,
            source_refs=(packet.packet_id,),
        )

    artifacts = [
        _artifact(
            f"corpus-payload:{field}",
            corpus_payload_path(field),
            payloads[field],
            packet.payload_hashes[field],
        )
        for field in sorted(payloads)
    ]
    # The payload is written to its own files and referenced by hash, so the
    # packet document itself carries refs rather than a second inline copy that
    # could disagree with them.
    packet_bytes = canonical_bytes(packet.model_dump(exclude={"payload"})) + b"\n"
    artifacts.append(
        _artifact("corpus-intelligence-packet", "packet.json", packet_bytes, packet.semantic_hash)
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
            "corpus-intelligence-bundle-manifest",
            "manifest.json",
            manifest_bytes,
            manifest.artifact_hash,
        )
    )
    return tuple(sorted(artifacts, key=lambda artifact: artifact.destination_path))


def _read_payload(root: Path, packet: CorpusIntelligencePacket) -> CorpusIntelligencePayload:
    """Read every payload domain, verifying each against its declared hash.

    Every domain is mandatory to carry. Unlike the Topology Packet — where a
    1.0.0 bundle legitimately declares no ref for a domain 1.1.0 added — a
    missing corpus ref means the bundle is incomplete rather than older, so it is
    refused rather than read as an empty domain.
    """
    from .loader import PacketLoadError

    parts: dict[str, Any] = {}
    for field in CORPUS_PAYLOAD_FIELDS:
        reference = packet.payload_refs.get(field)
        if reference is None:
            raise PacketLoadError(f"corpus intelligence packet is missing payload ref for {field}")
        try:
            content = (root / reference).read_bytes()
        except OSError as exc:
            raise PacketLoadError(f"cannot read corpus payload {reference}: {exc}") from exc
        expected = packet.payload_hashes.get(field)
        if expected is None:
            raise PacketLoadError(f"corpus intelligence packet is missing payload hash for {field}")
        if artifact_hash(content) != expected:
            raise PacketLoadError(f"corpus payload hash mismatch for {field}")
        parts[field] = json.loads(content)
    return CorpusIntelligencePayload.model_validate(parts)


@dataclass(frozen=True)
class CorpusIntelligenceBundle:
    """A loaded, hash-verified corpus intelligence bundle."""

    root: Path
    manifest: PacketBundleManifest
    packet: CorpusIntelligencePacket


def load_corpus_intelligence_bundle(path: Path) -> CorpusIntelligenceBundle:
    """Load a corpus intelligence bundle, verifying every hash it declares.

    Imported lazily from the shared loader so this module does not import it at
    definition time: the loader is the single place that knows how to verify a
    bundle manifest and refuse a member path that escapes the bundle root, and
    duplicating either here would let the two drift.
    """
    from .loader import PacketLoadError, verify_bundle_manifest

    root = path.resolve()
    if not root.is_dir():
        raise PacketLoadError(
            "canonical Corpus Intelligence input must be a packet bundle directory"
        )
    manifest = verify_bundle_manifest(root)

    def _read(relative: str) -> Any:
        member = root / relative
        try:
            member.relative_to(root)
        except ValueError as exc:  # pragma: no cover - manifest verification precedes this
            raise PacketLoadError(f"packet reference escapes bundle root: {relative}") from exc
        try:
            return json.loads(member.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PacketLoadError(f"cannot load JSON from {member}: {exc}") from exc

    packet = CorpusIntelligencePacket.model_validate(_read("packet.json"))
    if manifest.packet_id != packet.packet_id:
        raise PacketLoadError("manifest packet_id does not match packet.json")
    if manifest.semantic_hash != packet.semantic_hash:
        raise PacketLoadError("manifest semantic_hash does not match packet.json")

    payload = _read_payload(root, packet)

    materialized = packet.model_copy(update={"payload": payload})
    calculated = calculate_corpus_semantic_hash(materialized)
    if calculated != packet.semantic_hash:
        raise PacketLoadError(
            "corpus intelligence semantic hash mismatch: "
            f"expected {packet.semantic_hash}, calculated {calculated}"
        )
    return CorpusIntelligenceBundle(root=root, manifest=manifest, packet=materialized)
