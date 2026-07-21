from pathlib import Path

from l9_constellation_topology.config import resolve_configuration
from l9_constellation_topology.stages.ingest_packets import adapt_packets, ingest_paths
from l9_constellation_topology.stages.normalize_models import run as normalize

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "repository_model_packets"


def test_fixture_packets_ingest_and_normalize() -> None:
    packets = ingest_paths((FIXTURES / "l9-gate-sdk", FIXTURES / "l9-mcp-server"))
    models = adapt_packets(packets)
    combined = normalize(models)
    assert {repo.repository_id for repo in combined.repositories} == {
        "repo:l9-gate-sdk",
        "repo:l9-mcp-server",
    }
    assert len(combined.evidence) > 0


def test_configuration_resolves_and_hashes_contracts() -> None:
    config = resolve_configuration(ROOT)
    assert config.profile_id == "foundational-topology"
    assert config.profile_hash.startswith("sha256:")
    assert config.schema_contract_hash.startswith("sha256:")
