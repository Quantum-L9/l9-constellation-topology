from pathlib import Path
from types import SimpleNamespace

from l9_constellation_topology.worker.packet_store import PacketStoreClient


def test_oci_publish_normalizes_uri_for_oras(monkeypatch, tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "packet.json").write_text("{}", encoding="utf-8")
    commands: list[list[str]] = []

    monkeypatch.setattr(PacketStoreClient, "_oras", lambda self: "/usr/bin/oras")

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    client = PacketStoreClient()
    output = client.publish(bundle, "oci://ghcr.io/quantum-l9/topology:sha256-test")
    assert output == "oci://ghcr.io/quantum-l9/topology:sha256-test"
    assert commands[0][2] == "ghcr.io/quantum-l9/topology:sha256-test"
