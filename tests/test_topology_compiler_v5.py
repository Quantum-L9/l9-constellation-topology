from datetime import UTC, datetime
from pathlib import Path

import pytest

from l9_constellation_topology.compiler import (
    CANONICAL_CREATED_AT,
    commit_compilation,
    compile_topology,
)
from l9_constellation_topology.domain import ConflictRecord
from l9_constellation_topology.io import MemoryOutputSink, PacketBundleOutputSink, WritePolicy
from l9_constellation_topology.packets import load_topology_bundle
from l9_constellation_topology.run import artifact_hash, canonical_bytes
from l9_constellation_topology.validation.topology_validator import validate_topology

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)


def test_compiler_emits_validated_two_repository_topology() -> None:
    result = compile_topology(ROOT, INPUTS)
    packet = result.materialized.packet
    assert result.validation_receipt.status == "passed"
    assert packet.validation.status == "passed"
    assert [record.repository_id for record in result.materialized.state.repository_records] == [
        "repo:l9-gate-sdk",
        "repo:l9-mcp-server",
    ]
    assert packet.packet_id == f"packet:{packet.semantic_hash.removeprefix('sha256:')}"
    assert packet.payload_refs["repository_records"] == "payload/repository-records.json"


def test_semantic_hash_ignores_execution_time() -> None:
    first = compile_topology(
        ROOT,
        INPUTS,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = compile_topology(
        ROOT,
        INPUTS,
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    assert first.materialized.packet.semantic_hash == second.materialized.packet.semantic_hash
    assert first.materialized.packet.packet_id == second.materialized.packet.packet_id
    assert first.materialized.packet.artifact_hash != second.materialized.packet.artifact_hash


def test_default_compile_is_byte_reproducible() -> None:
    """Two default compiles of the same inputs must emit identical bytes.

    Canonical compilation reads no clock, so reproducibility holds without
    weakening ``artifact_hash``, which still covers the exact emitted bytes.
    """
    first = compile_topology(ROOT, INPUTS).materialized.packet
    second = compile_topology(ROOT, INPUTS).materialized.packet
    assert first.created_at == second.created_at == CANONICAL_CREATED_AT
    assert first.semantic_hash == second.semantic_hash
    assert first.artifact_hash == second.artifact_hash
    assert canonical_bytes(first.model_dump(exclude={"artifact_hash"})) == canonical_bytes(
        second.model_dump(exclude={"artifact_hash"})
    )


def test_artifact_hash_verifies_the_exact_emitted_bytes() -> None:
    """``artifact_hash`` stays an exact-byte digest, including ``created_at``."""
    packet = compile_topology(ROOT, INPUTS).materialized.packet
    recomputed = artifact_hash(canonical_bytes(packet.model_dump(exclude={"artifact_hash"})))
    assert packet.artifact_hash == recomputed


def test_explicit_timestamp_changes_bytes_but_not_meaning() -> None:
    default = compile_topology(ROOT, INPUTS).materialized.packet
    injected = compile_topology(
        ROOT, INPUTS, created_at=datetime(2026, 8, 16, tzinfo=UTC)
    ).materialized.packet
    assert injected.created_at != default.created_at
    assert injected.artifact_hash != default.artifact_hash
    assert injected.semantic_hash == default.semantic_hash
    # The injected packet is still exactly what it claims to be.
    assert injected.artifact_hash == artifact_hash(
        canonical_bytes(injected.model_dump(exclude={"artifact_hash"}))
    )


def test_packet_bundle_round_trip(tmp_path: Path) -> None:
    result = compile_topology(ROOT, INPUTS)
    bundle_path = tmp_path / "bundle"
    receipt = commit_compilation(result, PacketBundleOutputSink(bundle_path))
    assert receipt.status == "passed"
    materialized, validation = load_topology_bundle(bundle_path)
    assert validation.status == "passed"
    assert materialized.packet.packet_id == result.materialized.packet.packet_id
    assert materialized.state == result.materialized.state


def test_failed_validation_commits_zero_outputs() -> None:
    result = compile_topology(ROOT, INPUTS)
    state = result.materialized.state.model_copy(
        update={
            "conflicts": (
                *result.materialized.state.conflicts,
                ConflictRecord(
                    conflict_id="conflict:blocking",
                    subject_id="repo:l9-gate-sdk",
                    field="source_revision",
                    values=("git:a", "git:b"),
                    blocking=True,
                ),
            )
        }
    )
    receipt = validate_topology(
        result.materialized.packet,
        state,
        result.input_bundles,
        schema_root=ROOT,
    )
    assert receipt.status == "failed"
    sink = MemoryOutputSink(
        WritePolicy(
            allowed_output_roots=(".",),
            allowed_artifact_kinds=("topology-packet", "validation-receipt"),
            allow_overwrite=True,
            require_expected_hash_for_replace=False,
        )
    )
    # Build the failed result outside the raises block (S5778: single raising invocation)
    failed_result = result.__class__(
        materialized=result.materialized,
        validation_receipt=receipt,
        input_bundles=result.input_bundles,
        configuration=result.configuration,
        artifacts=result.artifacts,
    )
    with pytest.raises(ValueError, match="failed validation"):
        # A deliberately failed result cannot enter the sink boundary.
        commit_compilation(failed_result, sink)
    assert sink.storage == {}


def test_golden_topology_bundle_matches_fixed_compiler_output() -> None:
    golden_path = ROOT / "tests/fixtures/topology_packets/foundational-two-repo"
    golden, golden_receipt = load_topology_bundle(golden_path)
    compiled = compile_topology(
        ROOT,
        INPUTS,
        created_at=datetime(2026, 7, 21, tzinfo=UTC),
    )
    assert golden_receipt.status == "passed"
    assert golden.packet == compiled.materialized.packet
    assert golden.state == compiled.materialized.state
