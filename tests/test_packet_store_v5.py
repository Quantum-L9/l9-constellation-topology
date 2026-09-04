import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from l9_constellation_topology.compiler import commit_compilation, compile_topology
from l9_constellation_topology.io import PacketBundleOutputSink
from l9_constellation_topology.packets import PacketRef
from l9_constellation_topology.run import artifact_hash
from l9_constellation_topology.worker import WorkerError
from l9_constellation_topology.worker.packet_store import PacketStoreClient

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)


def test_oci_publish_returns_digest_qualified_uri(monkeypatch, tmp_path: Path) -> None:
    result = compile_topology(ROOT, INPUTS)
    bundle = tmp_path / "bundle"
    assert commit_compilation(result, PacketBundleOutputSink(bundle)).status == "passed"
    commands: list[list[str]] = []

    monkeypatch.setattr(PacketStoreClient, "_oras", lambda self: "/usr/bin/oras")

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(
            returncode=0,
            stdout='{"digest":"sha256:' + "a" * 64 + '"}',
            stderr="",
        )

    monkeypatch.setattr("subprocess.run", fake_run)
    client = PacketStoreClient()
    output = client.publish(bundle, "oci://ghcr.io/quantum-l9/topology:test")
    semantic_digest = result.materialized.packet.semantic_hash.removeprefix("sha256:")
    staging = f"ghcr.io/quantum-l9/topology:packet-{semantic_digest}"
    assert output.uri == "oci://ghcr.io/quantum-l9/topology@sha256:" + "a" * 64
    assert output.staging_uri == "oci://" + staging
    assert output.registry_manifest_digest == "sha256:" + "a" * 64
    assert output.bundle_manifest_digest == artifact_hash((bundle / "manifest.json").read_bytes())
    assert commands[0][2] == staging
    assert "--format" in commands[0]


def test_verify_published_binds_uri_to_expected_packet(tmp_path: Path) -> None:
    first_result = compile_topology(ROOT, INPUTS)
    first_bundle = tmp_path / "first"
    assert commit_compilation(first_result, PacketBundleOutputSink(first_bundle)).status == "passed"

    alternate_root = tmp_path / "alternate-root"
    shutil.copytree(ROOT / ".l9", alternate_root / ".l9")
    shutil.copytree(ROOT / "contracts", alternate_root / "contracts")
    shutil.copytree(ROOT / "schemas", alternate_root / "schemas")
    risk_path = alternate_root / ".l9/risk-profile.yaml"
    risk = yaml.safe_load(risk_path.read_text(encoding="utf-8"))
    risk["rules"][0]["severity"] = "critical"
    risk_path.write_text(yaml.safe_dump(risk, sort_keys=True), encoding="utf-8")
    second_result = compile_topology(alternate_root, INPUTS)
    second_bundle = tmp_path / "second"
    assert (
        commit_compilation(second_result, PacketBundleOutputSink(second_bundle)).status == "passed"
    )
    assert second_result.materialized.packet.packet_id != first_result.materialized.packet.packet_id

    first_packet = first_result.materialized.packet
    expected = PacketRef(
        packet_id=first_packet.packet_id,
        packet_type=first_packet.packet_type,
        packet_version=first_packet.packet_version,
        uri=second_bundle.resolve().as_uri(),
        semantic_hash=first_packet.semantic_hash,
        artifact_hash=first_packet.artifact_hash,
        validation_status="passed",
        subject_id="constellation:foundational-repository-intelligence",
        source_revision="git:" + "a" * 40,
    )
    # Compute arg before the raises block so only verify_published can raise (S5778)
    bundle_manifest_digest = artifact_hash((first_bundle / "manifest.json").read_bytes())
    with pytest.raises(WorkerError, match="published-packet-reference-mismatch"):
        PacketStoreClient().verify_published(
            expected.uri,
            expected=expected,
            expected_bundle_manifest_digest=bundle_manifest_digest,
            expected_registry_manifest_digest=None,
            workspace=tmp_path / "verify",
        )


def test_oci_verification_rejects_mutable_tag_before_pull(tmp_path: Path) -> None:
    expected = PacketRef(
        packet_id="packet:test",
        packet_type="l9.topology",
        packet_version="1.0.0",
        uri="oci://ghcr.io/quantum-l9/topology:latest",
        semantic_hash="sha256:" + "1" * 64,
        artifact_hash="sha256:" + "2" * 64,
        validation_status="passed",
    )
    _client = PacketStoreClient()  # S5778: construct outside raises block
    with pytest.raises(WorkerError, match="packet-uri-not-immutable"):
        _client.verify_published(
            expected.uri,
            expected=expected,
            expected_bundle_manifest_digest="sha256:" + "3" * 64,
            expected_registry_manifest_digest=None,
            workspace=tmp_path,
        )


def test_oci_verification_resolves_registry_descriptor_independently(
    monkeypatch, tmp_path: Path
) -> None:
    expected_digest = "sha256:" + "a" * 64
    expected = PacketRef(
        packet_id="packet:test",
        packet_type="l9.topology",
        packet_version="1.0.0",
        uri="oci://ghcr.io/quantum-l9/topology@" + expected_digest,
        semantic_hash="sha256:" + "1" * 64,
        artifact_hash="sha256:" + "2" * 64,
        validation_status="passed",
    )
    monkeypatch.setattr(PacketStoreClient, "_oras", lambda self: "/usr/bin/oras")
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(
            returncode=0,
            stdout='{"digest":"sha256:' + "b" * 64 + '"}',
            stderr="",
        )

    monkeypatch.setattr("subprocess.run", fake_run)
    _client2 = PacketStoreClient()  # S5778: construct outside raises block
    with pytest.raises(WorkerError, match="registry-descriptor-digest-mismatch"):
        _client2.verify_published(
            expected.uri,
            expected=expected,
            expected_bundle_manifest_digest="sha256:" + "3" * 64,
            expected_registry_manifest_digest=expected_digest,
            workspace=tmp_path,
        )
    assert commands[0][1:4] == ["manifest", "fetch", "--descriptor"]
