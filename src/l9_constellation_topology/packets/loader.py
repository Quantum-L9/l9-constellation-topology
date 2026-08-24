"""Safe local packet and packet-bundle loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.run.evidence import artifact_hash, semantic_hash

from .common import PacketBundleManifest
from .repository_model import RepositoryModelPacket, RepositoryModelPayload
from .topology_packet import MaterializedTopology, TopologyPacket, calculate_topology_semantic_hash
from .validation_receipt import (
    ValidationReceipt,
    validate_validation_receipt,
)
from .validator import validate_repository_model_packet


class PacketLoadError(ValueError):
    """Raised when a packet bundle cannot be loaded or verified safely."""


@dataclass(frozen=True)
class RepositoryModelBundle:
    root: Path
    manifest: PacketBundleManifest
    packet: RepositoryModelPacket
    receipt: ValidationReceipt


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PacketLoadError(f"cannot load JSON from {path}: {exc}") from exc


def _resolve_member(root: Path, relative_path: str) -> Path:
    if "://" in relative_path or relative_path.startswith("urn:"):
        raise PacketLoadError(
            f"remote packet member cannot be loaded by local loader: {relative_path}"
        )
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise PacketLoadError(f"packet reference escapes bundle root: {relative_path}") from exc
    if not candidate.is_file():
        raise PacketLoadError(f"packet member does not exist: {relative_path}")
    return candidate


def verify_bundle_manifest(bundle_root: Path) -> PacketBundleManifest:
    bundle_root = bundle_root.resolve()
    manifest_path = bundle_root / "manifest.json"
    manifest = PacketBundleManifest.model_validate(_read_json(manifest_path))
    for member in manifest.files:
        path = _resolve_member(bundle_root, member.path)
        content = path.read_bytes()
        if artifact_hash(content) != member.content_hash:
            raise PacketLoadError(f"bundle member hash mismatch: {member.path}")
        if len(content) != member.size_bytes:
            raise PacketLoadError(f"bundle member size mismatch: {member.path}")
    calculated_artifact_hash = semantic_hash(manifest.files)
    if manifest.artifact_hash != calculated_artifact_hash:
        raise PacketLoadError(
            "bundle manifest artifact hash mismatch: "
            f"expected {manifest.artifact_hash}, calculated {calculated_artifact_hash}"
        )
    return manifest


def _materialize_repository_payload(
    root: Path, packet: RepositoryModelPacket
) -> RepositoryModelPacket:
    if packet.payload is not None:
        return packet
    payload_parts: dict[str, Any] = {}
    for key, reference in packet.payload_refs.items():
        member_path = _resolve_member(root, reference)
        payload_parts[key] = _read_json(member_path)
    payload = RepositoryModelPayload(
        repositories=tuple(payload_parts.get("repositories", ())),
        artifacts=tuple(payload_parts.get("artifacts", ())),
        capabilities=tuple(payload_parts.get("capabilities", ())),
        relationships=tuple(payload_parts.get("relationships", ())),
        evidence=tuple(payload_parts.get("evidence", ())),
        diagnostics=tuple(payload_parts.get("diagnostics", ())),
    )
    return packet.model_copy(update={"payload": payload})


def load_repository_model_packet(path: Path) -> RepositoryModelPacket:
    path = path.resolve()
    if path.is_dir():
        verify_bundle_manifest(path)
        packet_path = path / "packet.json"
        root = path
    else:
        packet_path = path
        root = path.parent
    packet = RepositoryModelPacket.model_validate(_read_json(packet_path))
    return _materialize_repository_payload(root, packet)


def load_repository_model_bundle(path: Path) -> RepositoryModelBundle:
    root = path.resolve()
    if not root.is_dir():
        raise PacketLoadError("canonical Repository Model input must be a packet bundle directory")
    manifest = verify_bundle_manifest(root)
    packet = _materialize_repository_payload(
        root,
        RepositoryModelPacket.model_validate(_read_json(root / "packet.json")),
    )
    validate_repository_model_packet(packet)
    if manifest.packet_id != packet.packet_id:
        raise PacketLoadError("manifest packet_id does not match packet.json")
    if manifest.semantic_hash != packet.semantic_hash:
        raise PacketLoadError("manifest semantic_hash does not match packet.json")

    receipt_ref = packet.validation.receipt_ref
    if receipt_ref and "://" not in receipt_ref and not receipt_ref.startswith("urn:"):
        receipt_path = _resolve_member(root, receipt_ref)
    else:
        receipt_path = _resolve_member(root, "receipts/validation-receipt.json")
    receipt = ValidationReceipt.model_validate(_read_json(receipt_path))
    validate_validation_receipt(receipt)
    if receipt.status != "passed":
        raise PacketLoadError(f"input validation receipt status is {receipt.status!r}")
    if receipt.subject_packet_id != packet.packet_id:
        raise PacketLoadError("input validation receipt references a different packet")
    if receipt.subject_semantic_hash != packet.semantic_hash:
        raise PacketLoadError("input validation receipt references a different semantic hash")
    return RepositoryModelBundle(root=root, manifest=manifest, packet=packet, receipt=receipt)


def load_topology_bundle(bundle_root: Path) -> tuple[MaterializedTopology, ValidationReceipt]:
    bundle_root = bundle_root.resolve()
    manifest = verify_bundle_manifest(bundle_root)
    packet = TopologyPacket.model_validate(_read_json(bundle_root / "packet.json"))
    if packet.packet_id != manifest.packet_id:
        raise PacketLoadError("manifest packet_id does not match packet.json")
    if packet.semantic_hash != manifest.semantic_hash:
        raise PacketLoadError("manifest semantic_hash does not match packet.json")
    calculated_semantic_hash = calculate_topology_semantic_hash(packet)
    if calculated_semantic_hash != packet.semantic_hash:
        raise PacketLoadError(
            "topology packet semantic hash mismatch: "
            f"expected {packet.semantic_hash}, calculated {calculated_semantic_hash}"
        )

    def load_records(key: str) -> Any:
        reference = packet.payload_refs.get(key)
        if reference is None:
            return []
        content = _resolve_member(bundle_root, reference).read_bytes()
        expected_hash = packet.payload_hashes.get(key)
        if expected_hash is None:
            raise PacketLoadError(f"topology packet is missing payload hash for {key}")
        if artifact_hash(content) != expected_hash:
            raise PacketLoadError(f"topology payload hash mismatch for {key}")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise PacketLoadError(f"invalid topology payload JSON for {key}") from exc

    # Every domain is read by name. A 1.0.0 bundle declares no ref for the
    # domains 1.1.0 added, and `load_records` answers an absent ref with an empty
    # list, so an older packet loads as itself rather than failing on files it
    # never had a reason to write.
    state = TopologyState(
        repository_records=tuple(load_records("repository_records")),
        artifact_records=tuple(load_records("artifact_records")),
        capability_records=tuple(load_records("capability_records")),
        semantic_claims=tuple(load_records("semantic_claims")),
        edge_records=tuple(load_records("edge_records")),
        flow_records=tuple(load_records("flow_records")),
        graph_records=tuple(load_records("graph_records")),
        risks=tuple(load_records("risks")),
        maturity=tuple(load_records("maturity")),
        impact_indexes=tuple(load_records("impact_indexes")),
        corpus_records=tuple(load_records("corpus_records")),
        root_records=tuple(load_records("root_records")),
        candidate_relations=tuple(load_records("candidate_relations")),
        candidate_clusters=tuple(load_records("candidate_clusters")),
        readiness_evidence=tuple(load_records("readiness_evidence")),
        topology_reasoning_candidates=tuple(load_records("topology_reasoning_candidates")),
        evidence=tuple(load_records("evidence")),
        diagnostics=tuple(load_records("diagnostics")),
        unknowns=tuple(load_records("unknowns")),
        conflicts=tuple(load_records("conflicts")),
    )
    receipt_ref = packet.validation.receipt_ref
    if receipt_ref is None:
        raise PacketLoadError("topology packet does not reference a validation receipt")
    receipt = ValidationReceipt.model_validate(
        _read_json(_resolve_member(bundle_root, receipt_ref))
    )
    validate_validation_receipt(receipt)
    if receipt.status != "passed":
        raise PacketLoadError(f"topology validation status is {receipt.status!r}")
    if receipt.subject_packet_id != packet.packet_id:
        raise PacketLoadError("topology receipt references a different packet")
    if receipt.subject_semantic_hash != packet.semantic_hash:
        raise PacketLoadError("topology receipt references a different semantic hash")
    return MaterializedTopology(packet=packet, state=state), receipt
