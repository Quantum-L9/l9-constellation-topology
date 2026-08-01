#!/usr/bin/env python3
"""Regenerate deterministic Repository Model Packet fixtures from local sample repositories."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from generated_artifact_sync import GeneratedArtifact, synchronize

from l9_constellation_topology.compatibility.v4_models import RepoSource
from l9_constellation_topology.packets import (
    PacketBundleManifest,
    PacketFileEntry,
    PacketValidationRef,
)
from l9_constellation_topology.run import artifact_hash, canonical_bytes, semantic_hash
from l9_constellation_topology.scanners.repository_model_scanner import scan_repository_model

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "fixtures" / "sample_constellation"
DESTINATION = ROOT / "tests" / "fixtures" / "repository_model_packets"


def build_bundle_artifacts(repo_name: str) -> tuple[GeneratedArtifact, ...]:
    source_root = SAMPLE / repo_name
    bundle = scan_repository_model(
        RepoSource(repo_id=repo_name, name=repo_name, local_path=str(source_root))
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
        for repo_name in ("l9-gate-sdk", "l9-mcp-server")
        for artifact in build_bundle_artifacts(repo_name)
    )
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
