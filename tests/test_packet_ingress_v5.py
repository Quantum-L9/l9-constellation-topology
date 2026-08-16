from pathlib import Path

from l9_constellation_topology.config import resolve_configuration
from l9_constellation_topology.packets.adapters.repository_model_v1 import (
    RepositoryModelV1Adapter,
)
from l9_constellation_topology.packets.validator import SUPPORTED_REPOSITORY_MODEL_VERSIONS
from l9_constellation_topology.stages.ingest_packets import adapt_packets, ingest_paths
from l9_constellation_topology.stages.normalize_models import run as normalize

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "repository_model_packets"


def test_ingress_admits_every_version_the_contract_supports() -> None:
    """The dispatch table must not narrow what the adapter and validator already allow.

    It previously hardcoded 1.0.0 while the adapter and validator both accepted 1.1.0, so
    every assertion-bearing packet was rejected as unsupported before an adapter saw it.
    """
    assert set(RepositoryModelV1Adapter().supported_versions) == set(
        SUPPORTED_REPOSITORY_MODEL_VERSIONS
    )

    packet = ingest_paths((FIXTURES / "l9-gate-sdk",))[0]
    for version in sorted(SUPPORTED_REPOSITORY_MODEL_VERSIONS):
        candidate = packet.model_copy(update={"packet_version": version})
        try:
            adapt_packets((candidate,))
        except ValueError as error:  # a payload complaint is fine; a version refusal is not
            assert "unsupported Repository Model Packet version" not in str(error), (
                f"ingress refused {version}, which the contract declares supported"
            )


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
