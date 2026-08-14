from __future__ import annotations

import json
from pathlib import Path

import pytest

from l9_constellation_topology.cli import run as cli_run
from l9_constellation_topology.compatibility.v4_models import RepoSource
from l9_constellation_topology.evidence import (
    deep_freeze,
    hash_all_artifacts,
    hash_artifact,
    sha256_hash,
)
from l9_constellation_topology.io import (
    CompositeOutputSink,
    MemoryOutputSink,
    PacketBundleOutputSink,
    RenderedArtifact,
    WriteIntent,
    WritePolicy,
)
from l9_constellation_topology.packets import TransportPacket
from l9_constellation_topology.packets.loader import (
    load_repository_model_bundle,
    load_topology_bundle,
)
from l9_constellation_topology.packets.repository_bundle import (
    build_repository_model_bundle_artifacts,
)
from l9_constellation_topology.run import artifact_hash
from l9_constellation_topology.scanners.repository_model_scanner import scan_repository_model
from l9_constellation_topology.sources.filesystem_reader import FileSystemSourceReader
from l9_constellation_topology.stages.observe_fallbacks import run as observe_fallback
from l9_constellation_topology.worker.control_packet import _load_payload
from l9_constellation_topology.worker.control_packet import run as run_control_packet
from l9_constellation_topology.worker.signature import verify_transport_packet

KEY = "runtime-test-key"
KEY_ID = "foundational-hmac-v1"


def _artifact(path: str = "packet.json", content: bytes = b"payload") -> RenderedArtifact:
    return RenderedArtifact(
        logical_id=path,
        destination_path=path,
        artifact_kind="topology-packet",
        media_type="application/json",
        content=content,
        content_hash=artifact_hash(content),
    )


def _policy(*, roots: tuple[str, ...] = (".",)) -> WritePolicy:
    return WritePolicy(
        allowed_output_roots=roots,
        allowed_artifact_kinds=("topology-packet",),
        allow_overwrite=True,
        require_expected_hash_for_replace=False,
    )


def _sample_repo(root: Path) -> Path:
    repo = root / "sample"
    repo.mkdir()
    (repo / "README.md").write_text("# Sample\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (repo / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    return repo


def test_legacy_evidence_helpers_remain_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "a.txt"
    first.write_text("alpha", encoding="utf-8")
    frozen = deep_freeze({"b": [2, 1], "a": {"value": True}})
    assert isinstance(frozen, frozenset)
    assert deep_freeze("unchanged") == "unchanged"
    assert len(sha256_hash("alpha")) == 64
    artifact = hash_artifact(first)
    assert artifact["path"] == "a.txt"
    assert artifact["size_bytes"] == 5
    manifest = hash_all_artifacts([tmp_path / "missing.txt", first])
    assert len(manifest["artifacts"]) == 1
    assert str(manifest["manifest_sha256"]).startswith("sha256:")


def test_filesystem_reader_is_read_only_and_contained(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        FileSystemSourceReader("repo:missing", tmp_path / "missing", "git:" + "0" * 40)
    repo = _sample_repo(tmp_path)
    (repo / ".git").mkdir()
    (repo / ".git" / "ignored").write_text("hidden", encoding="utf-8")
    reader = FileSystemSourceReader("repo:sample", repo, "git:" + "1" * 40)
    assert reader.exists("README.md")
    assert reader.read_text("README.md") == "# Sample\n"
    assert reader.read_bytes("module.py") == b"VALUE = 1\n"
    assert reader.iter_files() == ("README.md", "module.py", "pyproject.toml")
    with pytest.raises(ValueError):
        reader.read_text("../outside.txt")


def test_composite_sink_fans_out_and_propagates_blocking() -> None:
    with pytest.raises(ValueError, match="at least one"):
        CompositeOutputSink(())
    left = MemoryOutputSink(_policy())
    right = MemoryOutputSink(_policy())
    composite = CompositeOutputSink((left, right))
    composite.enqueue(WriteIntent(artifact=_artifact()))
    assert len(composite.plan().entries) == 2
    receipt = composite.commit()
    assert receipt.status == "passed"
    assert len(receipt.results) == 2
    assert left.storage["packet.json"] == b"payload"
    assert right.storage["packet.json"] == b"payload"
    composite.clear()

    blocked = CompositeOutputSink((MemoryOutputSink(_policy(roots=("allowed",))),))
    blocked.enqueue(WriteIntent(artifact=_artifact()))
    assert blocked.plan().status == "blocked"
    assert blocked.commit().status == "blocked"


def test_direct_observation_fallback_and_repository_bundle(tmp_path: Path) -> None:
    repo = _sample_repo(tmp_path)
    with pytest.raises(ValueError, match="disabled"):
        observe_fallback(
            repository_id="repo:sample",
            name="sample",
            source_root=repo,
            expected_role="library",
            allowed=False,
        )
    normalized = observe_fallback(
        repository_id="repo:sample",
        name="sample",
        source_root=repo,
        expected_role="library",
        allowed=True,
    )
    assert normalized.repositories[0].repository_id == "repo:sample"

    synthetic = scan_repository_model(
        RepoSource(
            repo_id="sample",
            name="sample",
            local_path=str(repo),
            expected_role="library",
        )
    )
    artifacts = build_repository_model_bundle_artifacts(synthetic)
    assert [artifact.destination_path for artifact in artifacts] == [
        "packet.json",
        "receipts/validation-receipt.json",
        "manifest.json",
    ]


def test_packet_bundle_sink_verifies_by_bundle_kind(tmp_path: Path) -> None:
    """A Repository Model Packet bundle must commit through the sink only when the
    matching verifier is supplied; the default Topology Packet verifier must reject it."""
    repo = _sample_repo(tmp_path)
    synthetic = scan_repository_model(
        RepoSource(repo_id="sample", name="sample", local_path=str(repo), expected_role="library")
    )
    artifacts = build_repository_model_bundle_artifacts(synthetic)

    # Default verifier is Topology-Packet-only: a Repository Model bundle is rejected.
    default_sink = PacketBundleOutputSink(tmp_path / "default", allow_overwrite=True)
    for artifact in artifacts:
        default_sink.enqueue(WriteIntent(artifact=artifact))
    assert default_sink.commit().status == "failed"
    assert not (tmp_path / "default").exists()

    # With the Repository Model verifier the same bundle commits cleanly.
    rmp_sink = PacketBundleOutputSink(
        tmp_path / "rmp",
        allow_overwrite=True,
        bundle_verifier=load_repository_model_bundle,
    )
    for artifact in artifacts:
        rmp_sink.enqueue(WriteIntent(artifact=artifact))
    assert rmp_sink.commit().status == "passed"
    loaded = load_repository_model_bundle(tmp_path / "rmp")
    assert loaded.packet.subject.repository_id == "repo:sample"


def test_scan_compatibility_ingress_produces_valid_topology_bundle(tmp_path: Path) -> None:
    """End-to-end regression for the scan compatibility path (ISSUE-004): scanning a
    source repository must compile to a passing, loadable Topology Packet bundle."""
    repo = _sample_repo(tmp_path)
    out = tmp_path / "scanned-topology"
    project_root = Path(__file__).resolve().parents[1]
    exit_code = cli_run(
        [
            "scan",
            "--repo-root",
            str(project_root),
            "--source-repo",
            str(repo),
            "--repository-id",
            "sample",
            "--expected-role",
            "library",
            "--out",
            str(out),
        ]
    )
    assert exit_code == 0
    materialized, receipt = load_topology_bundle(out)
    assert receipt.status == "passed"
    assert materialized.packet.packet_type == "l9.topology"
    assert any(
        record.repository_id == "repo:sample" for record in materialized.state.repository_records
    )


def test_control_packet_cli_validates_payload_and_writes_signed_packet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload_path = tmp_path / "replay.json"
    payload_path.write_text(
        json.dumps(
            {
                "payload_schema": "l9.replay-request/1.0.0",
                "data": {
                    "run_id": "run:test",
                    "stage_id": "stage:test",
                    "packet_id": "packet:test",
                    "reason": "operator verification",
                    "dry_run": True,
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "signed.json"
    monkeypatch.setenv("L9_DISPATCH_HMAC_KEY", KEY)
    monkeypatch.setenv("L9_DISPATCH_HMAC_KEY_ID", KEY_ID)
    assert (
        run_control_packet(
            [
                "--payload-file",
                str(payload_path),
                "--packet-type",
                "command",
                "--action",
                "replay-topology",
                "--trace-id",
                "trace:test",
                "--correlation-id",
                "correlation:test",
                "--workflow-id",
                "foundational-repository-intelligence",
                "--out",
                str(output),
            ]
        )
        == 0
    )
    packet = TransportPacket.model_validate_json(output.read_text(encoding="utf-8"))
    verify_transport_packet(
        packet,
        key=KEY.encode(),
        allowed_algorithms=("hmac-sha256",),
        allowed_key_ids=(KEY_ID,),
    )
    assert packet.payload["payload_schema"] == "l9.replay-request/1.0.0"

    monkeypatch.delenv("L9_DISPATCH_HMAC_KEY")
    with pytest.raises(ValueError, match="required"):
        run_control_packet(
            [
                "--payload-file",
                str(payload_path),
                "--action",
                "replay-topology",
                "--trace-id",
                "trace:test",
                "--correlation-id",
                "correlation:test",
                "--out",
                str(tmp_path / "missing-key.json"),
            ]
        )


def test_control_payload_loader_rejects_invalid_inputs(tmp_path: Path) -> None:
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot read"):
        _load_payload(invalid_json)

    non_object = tmp_path / "array.json"
    non_object.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        _load_payload(non_object)

    unsupported = tmp_path / "unsupported.json"
    unsupported.write_text('{"payload_schema":"unknown/1"}', encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        _load_payload(unsupported)
