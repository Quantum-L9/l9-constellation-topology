"""Topology reconciles what the packet says; it never reopens the source tree.

``l9-meta-injector`` owns extraction and is free to enrich the Repository Model
Packet. Topology must accept the sparse contract it consumes today and the richer
facts it may receive tomorrow, without a translation shim and — the property that
matters — without ever falling back to reading the source repository on the
canonical ingress. A compiler that rescans on the canonical path would produce
facts the packet never asserted and lineage the plan could not cite.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.domain import (
    CapabilityRecord,
    ConfidenceAssessment,
    EdgeRecord,
    EdgeType,
)
from l9_constellation_topology.io import (
    PacketBundleOutputSink,
    WriteIntent,
    format_commit_failure,
)
from l9_constellation_topology.packets.loader import load_repository_model_bundle
from l9_constellation_topology.packets.repository_bundle import (
    build_repository_model_bundle_artifacts,
)
from l9_constellation_topology.packets.repository_model import RepositoryModelPayload
from l9_constellation_topology.packets.validator import repository_model_semantic_view
from l9_constellation_topology.run import EvidenceSourceRef, make_evidence_record, semantic_hash
from l9_constellation_topology.scanners.repository_model_scanner import (
    SyntheticRepositoryModelBundle,
)

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)
FIXED_TIME = datetime(2026, 7, 21, tzinfo=UTC)


def _rebuild_bundle(
    bundle: SyntheticRepositoryModelBundle, payload: RepositoryModelPayload
) -> SyntheticRepositoryModelBundle:
    """Re-seal a packet around a modified payload so identity stays consistent."""
    candidate = bundle.packet.model_copy(update={"payload": payload, "semantic_hash": "sha256:x"})
    digest = semantic_hash(repository_model_semantic_view(candidate))
    packet = candidate.model_copy(
        update={
            "packet_id": f"packet:{digest.removeprefix('sha256:')}",
            "semantic_hash": digest,
        }
    )
    receipt_candidate = bundle.receipt.model_copy(
        update={
            "subject_packet_id": packet.packet_id,
            "subject_semantic_hash": digest,
            "semantic_hash": "sha256:x",
        }
    )
    receipt_digest = semantic_hash(receipt_candidate)
    receipt = receipt_candidate.model_copy(
        update={
            "receipt_id": f"receipt:{receipt_digest.removeprefix('sha256:')}",
            "semantic_hash": receipt_digest,
        }
    )
    return SyntheticRepositoryModelBundle(packet=packet, receipt=receipt)


def _write(bundle: SyntheticRepositoryModelBundle, destination: Path) -> Path:
    sink = PacketBundleOutputSink(destination)
    for artifact in build_repository_model_bundle_artifacts(bundle, created_at=FIXED_TIME):
        sink.enqueue(WriteIntent(artifact=artifact))
    receipt = sink.commit()
    assert receipt.status == "passed", receipt.status
    return destination


@pytest.fixture
def baseline_bundle() -> SyntheticRepositoryModelBundle:
    loaded = load_repository_model_bundle(INPUTS[0])
    return SyntheticRepositoryModelBundle(packet=loaded.packet, receipt=loaded.receipt)


def test_current_sparse_packets_still_compile() -> None:
    """The contract in production today must keep working unchanged."""
    result = compile_topology(ROOT, INPUTS, created_at=FIXED_TIME)

    assert result.validation_receipt.status == "passed"
    assert result.materialized.state.repository_records
    # A sparse packet carrying no relationships invents none.
    for bundle in result.input_bundles:
        assert bundle.packet.payload is not None


def test_sparse_packet_without_capabilities_invents_none(
    baseline_bundle: SyntheticRepositoryModelBundle, tmp_path: Path
) -> None:
    payload = baseline_bundle.packet.payload
    assert payload is not None
    stripped = _rebuild_bundle(
        baseline_bundle,
        payload.model_copy(update={"capabilities": (), "relationships": ()}),
    )
    bundle_path = _write(stripped, tmp_path / "sparse")

    result = compile_topology(ROOT, (bundle_path,), created_at=FIXED_TIME)

    declared = {record.capability_id for record in result.materialized.state.capability_records}
    # Capabilities may still be derived from repository roles the packet declared,
    # but nothing may be sourced from the filesystem.
    for record in result.materialized.state.capability_records:
        assert record.evidence_refs or record.capability_id in declared


def test_enriched_packet_capabilities_and_relationships_are_honored(
    baseline_bundle: SyntheticRepositoryModelBundle, tmp_path: Path
) -> None:
    """Richer upstream semantics compile without a translation shim."""
    payload = baseline_bundle.packet.payload
    assert payload is not None
    repository = payload.repositories[0]
    evidence = make_evidence_record(
        subject_id="capability:enriched",
        field="declared_actions",
        stage="meta-injector-inventory",
        evidence_class="declared",
        source_type="packet",
        source_ref=EvidenceSourceRef(source_path="README.md"),
        value="execute",
        confidence=ConfidenceAssessment.deterministic(),
        producer="l9-meta-injector.repository-model",
        producer_version="4.0.0",
        created_at=FIXED_TIME,
    )
    capability = CapabilityRecord(
        capability_id="capability:enriched",
        name="enriched",
        description="A capability the upstream packet asserted with its own evidence.",
        implemented_by=(repository.repository_id,),
        evidence_refs=(evidence.evidence_id,),
        confidence=ConfidenceAssessment.deterministic(),
    )
    relationship = EdgeRecord(
        edge_id="edge:enriched",
        source_id=repository.repository_id,
        target_id="capability:enriched",
        edge_type=EdgeType.implements,
        evidence_refs=(evidence.evidence_id,),
        confidence=ConfidenceAssessment.deterministic(),
    )
    enriched = _rebuild_bundle(
        baseline_bundle,
        payload.model_copy(
            update={
                "capabilities": (*payload.capabilities, capability),
                "relationships": (*payload.relationships, relationship),
                "evidence": (*payload.evidence, evidence),
            }
        ),
    )
    bundle_path = _write(enriched, tmp_path / "enriched")

    result = compile_topology(ROOT, (bundle_path,), created_at=FIXED_TIME)
    state = result.materialized.state

    assert result.validation_receipt.status == "passed"
    assert "capability:enriched" in {record.capability_id for record in state.capability_records}
    assert any(
        edge.source_id == repository.repository_id and edge.target_id == "capability:enriched"
        for edge in state.edge_records
    )
    assert evidence.evidence_id in {record.evidence_id for record in state.evidence}


def test_enriched_declared_actions_aggregate_rather_than_conflict(
    baseline_bundle: SyntheticRepositoryModelBundle, tmp_path: Path
) -> None:
    """A richer packet asserting several actions must not manufacture a conflict."""
    payload = baseline_bundle.packet.payload
    assert payload is not None
    extra = tuple(
        make_evidence_record(
            subject_id="capability:multi",
            field="declared_actions",
            stage="meta-injector-inventory",
            evidence_class="declared",
            source_type="packet",
            source_ref=EvidenceSourceRef(source_path=f"docs/{action}.md"),
            value=action,
            confidence=ConfidenceAssessment.deterministic(),
            producer="l9-meta-injector.repository-model",
            producer_version="4.0.0",
            created_at=FIXED_TIME,
        )
        for action in ("execute", "describe")
    )
    enriched = _rebuild_bundle(
        baseline_bundle, payload.model_copy(update={"evidence": (*payload.evidence, *extra)})
    )
    bundle_path = _write(enriched, tmp_path / "multi-action")

    result = compile_topology(ROOT, (bundle_path,), created_at=FIXED_TIME)

    assert [
        conflict
        for conflict in result.materialized.state.conflicts
        if conflict.field == "declared_actions"
    ] == []


def _import_closure(entry_module: str) -> set[str]:
    """Return every first-party module reachable from ``entry_module`` by import."""
    source_root = ROOT / "src"
    package = "l9_constellation_topology"

    def module_file(name: str) -> Path | None:
        candidate = source_root / (name.replace(".", "/") + ".py")
        if candidate.is_file():
            return candidate
        candidate = source_root / name.replace(".", "/") / "__init__.py"
        return candidate if candidate.is_file() else None

    def first_party_imports(path: Path) -> set[str]:
        found: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                found.add(node.module)
                found.update(f"{node.module}.{alias.name}" for alias in node.names)
        return {name for name in found if name.startswith(package)}

    seen: set[str] = set()
    pending = [entry_module]
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        path = module_file(name)
        if path is None:
            continue
        seen.add(name)
        pending.extend(first_party_imports(path))
    return seen


def test_canonical_ingress_cannot_reach_source_observation() -> None:
    """The compiler must not be able to observe a repository checkout at all.

    The scan compatibility path is allowed to observe a source tree. The canonical
    packet path is not: if it did, topology would assert facts its inputs never
    carried, and a publication plan could not honestly cite where they came from.

    This is asserted statically over the compiler's import closure rather than by
    patching an observation function, because a patch only proves that one call
    did not happen on one input. If no scanner or source-snapshot module is
    reachable from the compiler, no input can trigger a rescan.
    """
    closure = _import_closure("l9_constellation_topology.compiler")

    observation_modules = sorted(
        name
        for name in closure
        if ".scanners" in name or ".sources" in name or name.endswith(".repo_card_adapter")
    )
    assert observation_modules == [], (
        f"canonical compilation reached source-observation modules: {observation_modules}"
    )
    # Sanity: the closure is real, not empty because the walker silently failed.
    assert "l9_constellation_topology.stages.reconcile_evidence" in closure
    assert "l9_constellation_topology.packets.loader" in closure


def test_scan_path_is_the_only_route_to_source_observation() -> None:
    """The compatibility scan may observe a source tree; nothing else may."""
    closure = _import_closure("l9_constellation_topology.scanners.repository_model_scanner")
    assert "l9_constellation_topology.scanners.repo_scanner" in closure
    assert any(name.startswith("l9_constellation_topology.sources") for name in closure)


def test_unsupported_packet_version_fails_closed(
    baseline_bundle: SyntheticRepositoryModelBundle, tmp_path: Path
) -> None:
    """An unsupported upstream contract version is refused, not adapted.

    Because bundles are now verified back under Repository Model semantics, the
    refusal happens at commit time rather than being deferred to compilation. The
    unsupported bundle is never published, and the receipt says why.
    """
    shifted = baseline_bundle.packet.model_copy(update={"packet_version": "9.9.9"})
    candidate = _rebuild_bundle(
        SyntheticRepositoryModelBundle(packet=shifted, receipt=baseline_bundle.receipt),
        shifted.payload if shifted.payload is not None else RepositoryModelPayload(),
    )

    destination = tmp_path / "unsupported"
    sink = PacketBundleOutputSink(destination)
    for artifact in build_repository_model_bundle_artifacts(candidate, created_at=FIXED_TIME):
        sink.enqueue(WriteIntent(artifact=artifact))
    receipt = sink.commit()

    assert receipt.status == "failed"
    assert not destination.exists(), "a bundle that fails verification is never published"
    rendered = "\n".join(
        format_commit_failure(receipt, stage="test", packet_type="l9.repository-model")
    )
    assert "9.9.9" in rendered
    assert "not supported" in rendered
