from pathlib import Path

from l9_constellation_topology.compatibility.v4_models import RepoSource
from l9_constellation_topology.packets.validator import validate_repository_model_packet
from l9_constellation_topology.scanners.repository_model_scanner import scan_repository_model

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures" / "sample_constellation" / "l9-gate-sdk"


def test_direct_observation_produces_valid_packet() -> None:
    bundle = scan_repository_model(
        RepoSource(repo_id="l9-gate-sdk", name="l9-gate-sdk", local_path=str(FIXTURE))
    )
    validate_repository_model_packet(bundle.packet)
    assert bundle.receipt.status == "passed"
    assert bundle.packet.payload is not None
    assert bundle.packet.payload.repositories[0].repository_id == "repo:l9-gate-sdk"
    assert all(
        not artifact.source_path.startswith("/") for artifact in bundle.packet.payload.artifacts
    )
