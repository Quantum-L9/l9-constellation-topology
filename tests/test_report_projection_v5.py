from datetime import UTC, datetime
from pathlib import Path

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.renderers import render_reports
from l9_constellation_topology.run import semantic_hash

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)


def test_reports_are_lazy_pure_projections() -> None:
    result = compile_topology(ROOT, INPUTS)
    profile_hash = semantic_hash(result.configuration.report_profile)
    projection = render_reports(
        result.materialized,
        formats=("markdown", "mermaid", "json", "neo4j-candidate"),
        report_profile_hash=profile_hash,
    )
    assert projection.manifest.source_packet_id == result.materialized.packet.packet_id
    assert len(projection.manifest.reports) == 4
    assert len(projection.artifacts) == 5
    assert {artifact.destination_path for artifact in projection.artifacts} == {
        "topology-report.md",
        "topology.mmd",
        "topology.json",
        "neo4j-candidate.jsonl",
        "report-manifest.json",
    }
    assert b"candidate-only" in next(
        item.content
        for item in projection.artifacts
        if item.destination_path == "neo4j-candidate.jsonl"
    )


def test_projection_cache_key_ignores_render_time() -> None:
    result = compile_topology(ROOT, INPUTS)
    profile_hash = semantic_hash(result.configuration.report_profile)
    first = render_reports(
        result.materialized,
        formats=("markdown",),
        report_profile_hash=profile_hash,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = render_reports(
        result.materialized,
        formats=("markdown",),
        report_profile_hash=profile_hash,
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    assert first.manifest.cache_key == second.manifest.cache_key
    assert first.manifest.semantic_hash == second.manifest.semantic_hash
