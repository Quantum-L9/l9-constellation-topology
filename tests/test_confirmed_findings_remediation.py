from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml

from l9_constellation_topology.compiler import (
    TopologyCompilationError,
    calculate_idempotency_key,
    commit_compilation,
    compile_topology,
)
from l9_constellation_topology.config import resolve_configuration
from l9_constellation_topology.io import FileSystemOutputSink, PacketBundleOutputSink
from l9_constellation_topology.packets import (
    PacketBundleManifest,
    PacketFileEntry,
    PacketRef,
    PacketValidationRef,
    Producer,
    ValidationCheck,
    ValidationReceipt,
    finalize_validation_receipt,
    load_repository_model_bundle,
    load_topology_bundle,
)
from l9_constellation_topology.packets.validator import repository_model_semantic_view
from l9_constellation_topology.run import artifact_hash, canonical_bytes, semantic_hash
from l9_constellation_topology.validation.topology_validator import validate_topology
from l9_constellation_topology.worker import LocalPacketRegistry, RegistryEntry

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)


def _packet_refs() -> tuple[PacketRef, ...]:
    refs: list[PacketRef] = []
    for path in INPUTS:
        packet = load_repository_model_bundle(path).packet
        refs.append(
            PacketRef(
                packet_id=packet.packet_id,
                packet_type=packet.packet_type,
                packet_version=packet.packet_version,
                uri=path.resolve().as_uri(),
                semantic_hash=packet.semantic_hash,
                artifact_hash=packet.artifact_hash,
                validation_status="passed",
                subject_id=packet.subject.repository_id,
                source_revision=packet.source_snapshot.revision,
            )
        )
    return tuple(refs)


def _copy_configuration(destination: Path) -> None:
    shutil.copytree(ROOT / ".l9", destination / ".l9")
    shutil.copytree(ROOT / "contracts", destination / "contracts")
    shutil.copytree(ROOT / "schemas", destination / "schemas")


def test_idempotency_fingerprint_changes_for_every_semantic_policy(tmp_path: Path) -> None:
    refs = _packet_refs()
    base = resolve_configuration(ROOT)
    base_key = calculate_idempotency_key(
        refs,
        base,
        compiler_build_identity="git:" + "a" * 40,
    )
    for profile_name in (
        "topology-profile.yaml",
        "risk-profile.yaml",
        "maturity-profile.yaml",
        "report-profile.yaml",
        "packet-profile.yaml",
        "output-policy.yaml",
    ):
        root = tmp_path / profile_name.removesuffix(".yaml")
        _copy_configuration(root)
        profile_path = root / ".l9" / profile_name
        profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        profile["remediation_test_marker"] = profile_name
        profile_path.write_text(yaml.safe_dump(profile, sort_keys=True), encoding="utf-8")
        changed = resolve_configuration(root)
        assert (
            calculate_idempotency_key(
                refs,
                changed,
                compiler_build_identity="git:" + "a" * 40,
            )
            != base_key
        )


def test_idempotency_fingerprint_changes_for_schema_and_build_identity(tmp_path: Path) -> None:
    refs = _packet_refs()
    base = resolve_configuration(ROOT)
    base_key = calculate_idempotency_key(
        refs,
        base,
        compiler_build_identity="git:" + "a" * 40,
    )
    root = tmp_path / "schema-change"
    _copy_configuration(root)
    schema = root / "contracts/topology-packet.schema.json"
    schema.write_text(schema.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    changed = resolve_configuration(root)
    assert (
        calculate_idempotency_key(
            refs,
            changed,
            compiler_build_identity="git:" + "a" * 40,
        )
        != base_key
    )
    assert (
        calculate_idempotency_key(
            refs,
            base,
            compiler_build_identity="git:" + "b" * 40,
        )
        != base_key
    )


def _write_bundle_with_diagnostic(source: Path, destination: Path) -> Path:
    bundle = load_repository_model_bundle(source)
    packet = bundle.packet
    assert packet.payload is not None
    payload = packet.payload.model_copy(
        update={
            "diagnostics": (
                {
                    "code": "upstream-partial-analysis",
                    "severity": "warning",
                    "stage": "artifact-analysis",
                    "message": "One optional source could not be analyzed.",
                    "subject_id": packet.subject.repository_id,
                },
            )
        }
    )
    candidate = packet.model_copy(
        update={
            "packet_id": "packet:pending",
            "semantic_hash": "sha256:pending",
            "artifact_hash": None,
            "payload": payload,
            "validation": PacketValidationRef(status="not_run"),
        }
    )
    digest = semantic_hash(repository_model_semantic_view(candidate))
    packet_id = f"packet:{digest.removeprefix('sha256:')}"
    receipt = finalize_validation_receipt(
        ValidationReceipt(
            receipt_id="receipt:pending",
            subject_packet_id=packet_id,
            subject_semantic_hash=digest,
            validator=Producer(name="test-fixture-validator", version="1.0.0"),
            status="passed",
            schema_results=(
                ValidationCheck(
                    check_id="fixture-valid",
                    check_class="schema",
                    rule="fixture_packet_valid",
                    status="passed",
                    message="Diagnostic fixture is valid.",
                ),
            ),
            semantic_hash="sha256:pending",
        )
    )
    final_packet = candidate.model_copy(
        update={
            "packet_id": packet_id,
            "semantic_hash": digest,
            "artifact_hash": artifact_hash(canonical_bytes(payload)),
            "validation": PacketValidationRef(
                status="passed",
                receipt_ref="receipts/validation-receipt.json",
            ),
        }
    )
    destination.mkdir(parents=True)
    receipt_path = destination / "receipts/validation-receipt.json"
    receipt_path.parent.mkdir(parents=True)
    packet_bytes = canonical_bytes(final_packet) + b"\n"
    receipt_bytes = canonical_bytes(receipt) + b"\n"
    (destination / "packet.json").write_bytes(packet_bytes)
    receipt_path.write_bytes(receipt_bytes)
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
        packet_id=packet_id,
        packet_type=final_packet.packet_type,
        packet_version=final_packet.packet_version,
        semantic_hash=digest,
        artifact_hash=semantic_hash(files),
        files=files,
    )
    (destination / "manifest.json").write_bytes(canonical_bytes(manifest) + b"\n")
    return destination


def test_input_diagnostics_are_preserved_and_round_trip(tmp_path: Path) -> None:
    diagnostic_input = _write_bundle_with_diagnostic(INPUTS[0], tmp_path / "diagnostic-input")
    result = compile_topology(ROOT, (diagnostic_input, INPUTS[1]))
    diagnostics = result.materialized.state.diagnostics
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "upstream-partial-analysis"
    assert diagnostics[0].source_packet_id == result.input_bundles[0].packet.packet_id
    conservation = next(
        check
        for check in result.validation_receipt.cross_reference_results
        if check.check_id == "cross-diagnostic-conservation"
    )
    assert conservation.status == "passed"
    output = tmp_path / "topology-output"
    assert commit_compilation(result, PacketBundleOutputSink(output)).status == "passed"
    loaded, _ = load_topology_bundle(output)
    assert loaded.state.diagnostics == diagnostics

    stripped = result.materialized.state.model_copy(update={"diagnostics": ()})
    failed = validate_topology(
        result.materialized.packet,
        stripped,
        result.input_bundles,
        schema_root=ROOT,
    )
    assert failed.status == "failed"


def test_independent_json_schema_validation_can_block_compilation(tmp_path: Path) -> None:
    root = tmp_path / "invalid-schema-root"
    _copy_configuration(root)
    schema_path = root / "contracts/topology-packet.schema.json"
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    schema["properties"]["packet_type"]["const"] = "l9.not-topology"
    import json

    schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(TopologyCompilationError) as captured:
        compile_topology(root, INPUTS)
    check = next(
        item
        for item in captured.value.receipt.schema_results
        if item.check_id == "json-schema-topology-packet"
    )
    assert check.status == "failed"
    assert check.details["validation_layer"] == "json-schema"


def test_packet_bundle_commit_is_atomic_on_staging_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = compile_topology(ROOT, INPUTS)
    target = tmp_path / "atomic-bundle"
    original = FileSystemOutputSink._atomic_write
    calls = 0

    def fail_after_first(self, path: Path, content: bytes, *, exclusive: bool = False) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated staging failure")
        original(self, path, content, exclusive=exclusive)

    monkeypatch.setattr(FileSystemOutputSink, "_atomic_write", fail_after_first)
    receipt = commit_compilation(result, PacketBundleOutputSink(target))
    assert receipt.status == "failed"
    assert not target.exists()
    assert not list(tmp_path.glob(".atomic-bundle.staging-*"))


def _registry_entry(index: int) -> RegistryEntry:
    packet_id = f"packet:{index:064x}"
    ref = PacketRef(
        packet_id=packet_id,
        packet_type="l9.topology",
        packet_version="1.0.0",
        uri=f"file:///tmp/{packet_id}",
        semantic_hash=f"sha256:{index:064x}",
        artifact_hash=f"sha256:{index + 1:064x}",
        validation_status="passed",
    )
    return RegistryEntry(
        idempotency_key=f"sha256:{index + 2:064x}",
        packet_ref=ref,
        validation_receipt_uri="file:///tmp/validation.json",
        commit_receipt_uri="file:///tmp/commit.json",
        metadata={"bundle_manifest_digest": f"sha256:{index + 3:064x}"},
    )


def test_local_registry_is_transaction_safe_under_concurrent_writers(tmp_path: Path) -> None:
    registry = LocalPacketRegistry(tmp_path / "registry.sqlite3")
    entries = tuple(_registry_entry(index) for index in range(1, 17))
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(registry.register, entries))
    for entry in entries:
        assert registry.get(entry.idempotency_key) == entry
