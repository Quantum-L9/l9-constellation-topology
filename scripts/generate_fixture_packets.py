#!/usr/bin/env python3
"""Regenerate deterministic packet fixtures from local sample repositories.

Both the Repository Model Packet inputs and the golden Topology Packet bundle
compiled from them are generated here. Generation is byte-reproducible: every
input that would otherwise vary by wall clock or by checkout location is placed
under explicit control.

Two such inputs exist, and both are volatile rather than semantic — the semantic
hashes strip timestamps, and the fixtures' declared revision is derived from the
sample content itself:

* ``created_at`` is pinned to :data:`FIXTURE_CREATED_AT`.
* ``source_revision`` is derived from the sample tree's own content hash rather
  than from this repository's git ``HEAD``, which is what previously made a
  regeneration check meaningful only at the exact commit the fixtures were
  generated at.

Because that variance is now controlled, ``--check`` is part of the standard
validation gate rather than an on-demand diagnostic.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from generated_artifact_sync import GeneratedArtifact, synchronize

from l9_constellation_topology.compatibility.v4_models import RepoSource
from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.packets import (
    PacketBundleManifest,
    PacketFileEntry,
    PacketValidationRef,
)
from l9_constellation_topology.run import artifact_hash, canonical_bytes, semantic_hash
from l9_constellation_topology.scanners.repository_model_scanner import scan_repository_model
from l9_constellation_topology.sources import compute_source_snapshot

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "fixtures" / "sample_constellation"
DESTINATION = ROOT / "tests" / "fixtures" / "repository_model_packets"
TOPOLOGY_DESTINATION = ROOT / "tests" / "fixtures" / "topology_packets" / "foundational-two-repo"

SAMPLE_REPOSITORIES = ("l9-gate-sdk", "l9-mcp-server")

#: Emission stamp pinned into every generated fixture. Any fixed instant works:
#: it is stripped from every semantic hash and exists only to fix the bytes.
FIXTURE_CREATED_AT = datetime(2026, 7, 21, tzinfo=UTC)


def fixture_source_revision(source_root: Path) -> str:
    """Return a revision derived from the sample content, not from a checkout.

    The sample repositories are directories inside this repository rather than
    independent clones, so their git ``HEAD`` is this repository's ``HEAD`` and
    would change on every unrelated commit.
    """
    snapshot = compute_source_snapshot(source_root)
    return f"tree:{snapshot.semantic_hash.removeprefix('sha256:')}"


def build_bundle_artifacts(repo_name: str) -> tuple[GeneratedArtifact, ...]:
    source_root = SAMPLE / repo_name
    bundle = scan_repository_model(
        RepoSource(repo_id=repo_name, name=repo_name, local_path=str(source_root)),
        created_at=FIXTURE_CREATED_AT,
        source_revision=fixture_source_revision(source_root),
    )
    destination = DESTINATION / repo_name

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
    files = (
        PacketFileEntry(
            path="packet.json",
            media_type="application/json",
            content_hash=artifact_hash(packet_bytes),
            size_bytes=len(packet_bytes),
        ),
        PacketFileEntry(
            path="receipts/validation-receipt.json",
            media_type="application/json",
            content_hash=artifact_hash(receipt_bytes),
            size_bytes=len(receipt_bytes),
        ),
    )
    manifest = PacketBundleManifest(
        packet_id=packet.packet_id,
        packet_type=packet.packet_type,
        packet_version=packet.packet_version,
        semantic_hash=packet.semantic_hash,
        artifact_hash=semantic_hash(files),
        files=files,
        created_at=FIXTURE_CREATED_AT,
    )
    return (
        GeneratedArtifact(destination / "packet.json", packet_bytes),
        GeneratedArtifact(
            destination / "receipts" / "validation-receipt.json",
            receipt_bytes,
        ),
        GeneratedArtifact(
            destination / "manifest.json",
            canonical_bytes(manifest) + b"\n",
        ),
    )


def build_topology_bundle_fixture() -> tuple[GeneratedArtifact, ...]:
    """Compile the golden Topology Packet bundle from the generated inputs.

    The golden bundle is a compiler output, so it is generated rather than hand
    maintained: a change to compiler meaning shows up as a reviewable fixture
    diff instead of a hand-edited packet that silently drifts from the code.
    """
    result = compile_topology(
        ROOT,
        tuple(DESTINATION / repo_name for repo_name in SAMPLE_REPOSITORIES),
        created_at=FIXTURE_CREATED_AT,
    )
    return tuple(
        GeneratedArtifact(TOPOLOGY_DESTINATION / artifact.destination_path, artifact.content)
        for artifact in result.artifacts
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when generated fixtures differ; never modify files.",
    )
    args = parser.parse_args(argv)
    artifacts = tuple(
        artifact
        for repo_name in SAMPLE_REPOSITORIES
        for artifact in build_bundle_artifacts(repo_name)
    )
    # The golden topology bundle is compiled from the Repository Model fixtures on
    # disk, so it is built after they have been written in an update run and read
    # as-is during a check run.
    if not args.check:
        synchronize(artifacts, check=False)
    artifacts = (*artifacts, *build_topology_bundle_fixture())
    findings = synchronize(artifacts, check=args.check)
    if args.check and findings:
        for finding in findings:
            print(f"{finding.kind}: {finding.path.relative_to(ROOT)}")
        return 1
    if not args.check:
        for finding in findings:
            print(f"updated: {finding.path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
