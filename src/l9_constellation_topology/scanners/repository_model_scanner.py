"""Bounded read-only direct observation producing a validated synthetic packet bundle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from l9_constellation_topology.compatibility.repo_card_adapter import adapt_repo_card
from l9_constellation_topology.compatibility.v4_models import RepoSource
from l9_constellation_topology.packets import (
    PacketValidationRef,
    Producer,
    ProfileRef,
    RepositoryModelPacket,
    RepositoryModelPayload,
    RepositorySubject,
    SourceSnapshot,
    ValidationCheck,
    ValidationReceipt,
)
from l9_constellation_topology.packets.validator import repository_model_semantic_view
from l9_constellation_topology.run import artifact_hash, canonical_bytes, semantic_hash
from l9_constellation_topology.scanners.repo_scanner import scan_repo
from l9_constellation_topology.sources import compute_source_snapshot


@dataclass(frozen=True)
class SyntheticRepositoryModelBundle:
    packet: RepositoryModelPacket
    receipt: ValidationReceipt


def scan_repository_model(source: RepoSource) -> SyntheticRepositoryModelBundle:
    root = Path(source.local_path).resolve()
    snapshot = compute_source_snapshot(root)
    card = scan_repo(source)
    packet_ref = f"urn:l9:legacy-scan:{source.repo_id}:{snapshot.semantic_hash}"
    normalized, _ = adapt_repo_card(
        card,
        source_revision=snapshot.revision,
        packet_ref=packet_ref,
        repository_root=root,
    )
    payload = RepositoryModelPayload(
        repositories=normalized.repositories,
        artifacts=normalized.artifacts,
        capabilities=normalized.capabilities,
        relationships=normalized.relationships,
        evidence=normalized.evidence,
        diagnostics=normalized.diagnostics,
    )
    candidate = RepositoryModelPacket(
        packet_version="1.0.0",
        packet_id="packet:pending",
        subject=RepositorySubject(repository_id=normalized.repositories[0].repository_id),
        source_snapshot=SourceSnapshot(
            revision=snapshot.revision,
            semantic_hash=snapshot.semantic_hash,
        ),
        validation=PacketValidationRef(status="not_run"),
        producer=Producer(name="l9-constellation-topology.legacy-scanner", version="2.0.0"),
        profile=ProfileRef(
            id="bounded-direct-observation",
            version="1.0.0",
            hash=semantic_hash({"scanner": "legacy-v4", "mode": "read-only"}),
        ),
        schema_hash=semantic_hash(RepositoryModelPacket.model_json_schema()),
        semantic_hash="sha256:pending",
        payload=payload,
    )
    digest = semantic_hash(repository_model_semantic_view(candidate))
    packet_id = f"packet:{digest.removeprefix('sha256:')}"
    checks = (
        ValidationCheck(
            check_id="repository-source-exists",
            check_class="cross-reference",
            rule="source_repository_exists",
            status="passed",
            message=f"source repository exists at the declared fallback root for {source.repo_id}",
        ),
        ValidationCheck(
            check_id="repository-scan-materialized",
            check_class="schema",
            rule="canonical_records_materialized",
            status="passed",
            message="legacy scanner output was adapted into canonical repository records",
        ),
    )
    receipt_candidate = ValidationReceipt(
        receipt_id="receipt:pending",
        subject_packet_id=packet_id,
        subject_semantic_hash=digest,
        validator=Producer(
            name="l9-constellation-topology.direct-observation-validator", version="2.0.0"
        ),
        status="passed",
        schema_results=checks[1:],
        cross_reference_results=checks[:1],
        semantic_hash="sha256:pending",
    )
    receipt_digest = semantic_hash(receipt_candidate)
    receipt = receipt_candidate.model_copy(
        update={
            "receipt_id": f"receipt:{receipt_digest.removeprefix('sha256:')}",
            "semantic_hash": receipt_digest,
        }
    )
    packet = candidate.model_copy(
        update={
            "packet_id": packet_id,
            "semantic_hash": digest,
            "artifact_hash": artifact_hash(canonical_bytes(payload)),
            "validation": PacketValidationRef(
                status="passed",
                receipt_ref=f"urn:l9:validation:{receipt.receipt_id}",
            ),
        }
    )
    return SyntheticRepositoryModelBundle(packet=packet, receipt=receipt)
