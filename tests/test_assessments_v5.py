from pathlib import Path

from l9_constellation_topology.config import resolve_configuration
from l9_constellation_topology.domain import ConfidenceLevel, EdgeType
from l9_constellation_topology.stages.aggregate_capabilities import run as aggregate_capabilities
from l9_constellation_topology.stages.aggregate_repositories import run as aggregate_repositories
from l9_constellation_topology.stages.ingest_packets import adapt_packets, ingest_paths
from l9_constellation_topology.stages.normalize_models import run as normalize
from l9_constellation_topology.topology.capability_builder import build_capabilities
from l9_constellation_topology.topology.graph_builder import build_topology_graph
from l9_constellation_topology.topology.impact import assess_impact
from l9_constellation_topology.topology.maturity import assess_maturity
from l9_constellation_topology.topology.risk import assess_topology_risks

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "repository_model_packets"


def state_parts():
    config = resolve_configuration(ROOT)
    packets = ingest_paths((FIXTURES / "l9-gate-sdk", FIXTURES / "l9-mcp-server"))
    inputs = normalize(adapt_packets(packets))
    repositories, _, _ = aggregate_repositories(inputs.repositories)
    capabilities, _ = aggregate_capabilities(inputs.capabilities)
    capabilities = build_capabilities(repositories, inputs.artifacts, capabilities)
    _, edges = build_topology_graph(
        repositories, inputs.artifacts, capabilities, inputs.relationships
    )
    return config, repositories, inputs.evidence, edges


def test_downstream_impact_finds_mcp_server() -> None:
    _, _, _, edges = state_parts()
    impact = assess_impact(
        "repo:l9-gate-sdk",
        edges,
        direction="downstream",
        maximum_depth=3,
        edge_types={EdgeType.depends_on},
        minimum_confidence=ConfidenceLevel.low,
    )
    assert "repo:l9-mcp-server" in impact.affected_repository_ids


def test_profile_maturity_and_risk_are_emitted() -> None:
    config, repositories, evidence, _ = state_parts()
    maturity = assess_maturity(repositories, evidence, config.maturity_profile)
    risks = assess_topology_risks(repositories, config.risk_profile)
    assert len(maturity) == 2
    assert all(item.maximum_score == 100 for item in maturity)
    assert any(item.category == "governance_gap" for item in risks)
