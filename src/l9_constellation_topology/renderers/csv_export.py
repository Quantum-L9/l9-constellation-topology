"""Pure CSV/YAML projections with sink-backed legacy wrappers."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import yaml

from l9_constellation_topology.io import RenderedArtifact
from l9_constellation_topology.models import TopologyReport
from l9_constellation_topology.packets import MaterializedTopology

from .common import make_rendered_artifact, write_compatibility_artifact


def render_maturity_csv_artifact(materialized: MaterializedTopology) -> RenderedArtifact:
    dimensions = sorted(
        {name for assessment in materialized.state.maturity for name in assessment.dimensions}
    )
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["subject_id", "score", "maximum_score", "band", *dimensions])
    for assessment in materialized.state.maturity:
        writer.writerow(
            [
                assessment.subject_id,
                assessment.score,
                assessment.maximum_score,
                assessment.band,
                *(assessment.dimensions.get(name, 0) for name in dimensions),
            ]
        )
    return make_rendered_artifact(
        logical_id="maturity-scorecard-csv",
        destination_path="maturity-scorecard.csv",
        artifact_kind="maturity-report",
        media_type="text/csv",
        content=buffer.getvalue().encode("utf-8"),
        semantic_hash=materialized.packet.semantic_hash,
        source_refs=(materialized.packet.packet_id,),
    )


def render_repository_inventory_yaml_artifact(
    materialized: MaterializedTopology,
) -> RenderedArtifact:
    payload = {
        "source_packet_id": materialized.packet.packet_id,
        "repositories": [
            record.model_dump(mode="json") for record in materialized.state.repository_records
        ],
    }
    content = yaml.safe_dump(payload, sort_keys=True, allow_unicode=True).encode("utf-8")
    return make_rendered_artifact(
        logical_id="repository-inventory-yaml",
        destination_path="repository-inventory.yaml",
        artifact_kind="human-report",
        media_type="application/yaml",
        content=content,
        semantic_hash=materialized.packet.semantic_hash,
        source_refs=(materialized.packet.packet_id,),
    )


def export_maturity_csv(report: TopologyReport, output_path: Path) -> None:
    dimensions = list(next((score.breakdown.keys() for score in report.maturity_scorecard), []))
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["repo_id", "score", "band", *dimensions])
    for score in report.maturity_scorecard:
        writer.writerow([score.repo_id, score.score, score.band, *score.breakdown.values()])
    write_compatibility_artifact(
        output_path,
        make_rendered_artifact(
            logical_id="legacy-maturity-csv",
            destination_path=output_path.name,
            artifact_kind="maturity-report",
            media_type="text/csv",
            content=buffer.getvalue().encode("utf-8"),
        ),
    )


def export_repo_inventory_yaml(report: TopologyReport, output_path: Path) -> str:
    lines = ["repo_inventory:"]
    for card in report.repo_inventory:
        lines.extend(
            (
                f"  - repo_id: {card.repo_id}",
                f"    name: {card.name}",
                f"    path: {card.path}",
                f"    primary_role: {card.primary_role}",
                f"    owner: {card.owner}",
                f"    confidence: {card.confidence.value}",
                f"    languages: [{', '.join(card.languages) if card.languages else 'UNKNOWN'}]",
            )
        )
    content = "\n".join(lines) + "\n"
    write_compatibility_artifact(
        output_path,
        make_rendered_artifact(
            logical_id="legacy-repository-inventory-yaml",
            destination_path=output_path.name,
            artifact_kind="human-report",
            media_type="application/yaml",
            content=content.encode("utf-8"),
        ),
    )
    return content


def export_edge_cards_yaml(report: TopologyReport, output_path: Path) -> None:
    lines = ["edge_cards:"]
    for edge in report.dependency_graph:
        lines.extend(
            (
                f"  - source: {edge.source}",
                f"    target: {edge.target}",
                f"    edge_type: {edge.edge_type.value}",
                f"    direction: {edge.direction.value}",
                f"    confidence: {edge.confidence.value}",
            )
        )
    content = ("\n".join(lines) + "\n").encode("utf-8")
    write_compatibility_artifact(
        output_path,
        make_rendered_artifact(
            logical_id="legacy-edge-cards-yaml",
            destination_path=output_path.name,
            artifact_kind="human-report",
            media_type="application/yaml",
            content=content,
        ),
    )


def export_flow_cards_yaml(report: TopologyReport, output_path: Path) -> None:
    lines = ["flow_cards:"]
    for flow in report.intelligence_flows:
        lines.extend(
            (
                f"  - flow_id: {flow.flow_id}",
                f"    name: {flow.name}",
                f"    source_repo: {flow.source_repo}",
                f"    target_repo: {flow.target_repo}",
                f"    flow_type: {flow.flow_type}",
                f"    confidence: {flow.confidence.value}",
            )
        )
    if not report.intelligence_flows:
        lines.append("  []")
    content = ("\n".join(lines) + "\n").encode("utf-8")
    write_compatibility_artifact(
        output_path,
        make_rendered_artifact(
            logical_id="legacy-flow-cards-yaml",
            destination_path=output_path.name,
            artifact_kind="human-report",
            media_type="application/yaml",
            content=content,
        ),
    )
