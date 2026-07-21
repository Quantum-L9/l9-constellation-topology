from datetime import UTC, datetime
from pathlib import Path

import pytest

from l9_constellation_topology.compiler import (
    commit_compilation,
    compile_topology,
)
from l9_constellation_topology.domain import ConflictRecord
from l9_constellation_topology.io import MemoryOutputSink, PacketBundleOutputSink, WritePolicy
from l9_constellation_topology.packets import load_topology_bundle
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


def test_packet_bundle_round_trip(tmp_path: Path) -> None:
    result = compile_topology(ROOT, INPUTS)
    receipt = commit_compilation(result, PacketBundleOutputSink(tmp_path))
    assert receipt.status == "passed"
    materialized, validation = load_topology_bundle(tmp_path)
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
    receipt = validate_topology(result.materialized.packet, state, result.input_bundles)
    assert receipt.status == "failed"
    sink = MemoryOutputSink(
        WritePolicy(
            allowed_output_roots=(".",),
            allowed_artifact_kinds=("topology-packet", "validation-receipt"),
            allow_overwrite=True,
            require_expected_hash_for_replace=False,
        )
    )
    with pytest.raises(ValueError, match="failed validation"):
        # A deliberately failed result cannot enter the sink boundary.
        commit_compilation(
            result.__class__(
                materialized=result.materialized,
                validation_receipt=receipt,
                input_bundles=result.input_bundles,
                configuration=result.configuration,
                artifacts=result.artifacts,
            ),
            sink,
        )
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
