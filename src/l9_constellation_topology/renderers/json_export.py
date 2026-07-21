"""Pure canonical JSON/JSONL projections with sink-backed compatibility wrappers."""

from __future__ import annotations

from pathlib import Path

from l9_constellation_topology.io import RenderedArtifact
from l9_constellation_topology.models import TopologyReport
from l9_constellation_topology.packets import MaterializedTopology
from l9_constellation_topology.run import canonical_bytes, canonical_json

from .common import make_rendered_artifact, write_compatibility_artifact


def render_topology_json_artifact(materialized: MaterializedTopology) -> RenderedArtifact:
    content = (
        canonical_bytes(
            {
                "packet": materialized.packet,
                "topology": materialized.state,
            }
        )
        + b"\n"
    )
    return make_rendered_artifact(
        logical_id="topology-json-projection",
        destination_path="topology.json",
        artifact_kind="human-report",
        media_type="application/json",
        content=content,
        semantic_hash=materialized.packet.semantic_hash,
        source_refs=(materialized.packet.packet_id,),
    )


def render_graph_records_jsonl_artifact(materialized: MaterializedTopology) -> RenderedArtifact:
    lines = [canonical_json(record) for record in materialized.state.graph_records]
    content = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    return make_rendered_artifact(
        logical_id="topology-graph-jsonl",
        destination_path="graph-records.jsonl",
        artifact_kind="graph-export",
        media_type="application/x-ndjson",
        content=content,
        semantic_hash=materialized.packet.semantic_hash,
        source_refs=(materialized.packet.packet_id,),
    )


def render_neo4j_candidate_artifact(materialized: MaterializedTopology) -> RenderedArtifact:
    lines: list[str] = []
    for record in materialized.state.graph_records:
        candidate = {
            "record_type": record.record_type,
            "label": record.label,
            "entity_id": record.entity_id,
            "properties": record.properties,
            "evidence_refs": record.evidence_refs,
            "confidence": record.confidence,
            "source_packet_id": materialized.packet.packet_id,
            "publication_status": "candidate-only",
        }
        lines.append(canonical_json(candidate))
    content = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    return make_rendered_artifact(
        logical_id="neo4j-candidate-jsonl",
        destination_path="neo4j-candidate.jsonl",
        artifact_kind="graph-export",
        media_type="application/x-ndjson",
        content=content,
        semantic_hash=materialized.packet.semantic_hash,
        source_refs=(materialized.packet.packet_id,),
    )


def export_json(report: TopologyReport, output_path: Path) -> None:
    content = canonical_bytes(report.model_dump(mode="json"))
    write_compatibility_artifact(
        output_path,
        make_rendered_artifact(
            logical_id="legacy-topology-report-json",
            destination_path=output_path.name,
            artifact_kind="human-report",
            media_type="application/json",
            content=content,
        ),
    )


def export_graph_records_jsonl(report: TopologyReport, output_path: Path) -> None:
    lines = [canonical_json(record.model_dump(mode="json")) for record in report.graph_records]
    content = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    write_compatibility_artifact(
        output_path,
        make_rendered_artifact(
            logical_id="legacy-graph-records-jsonl",
            destination_path=output_path.name,
            artifact_kind="graph-export",
            media_type="application/x-ndjson",
            content=content,
        ),
    )


def export_neo4j_jsonl(report: TopologyReport, output_path: Path) -> None:
    lines = []
    for record in report.graph_records:
        lines.append(
            canonical_json(
                {
                    "type": record.record_type.value,
                    "label": record.label,
                    "id": record.id,
                    "properties": record.properties,
                    "confidence": record.confidence.value,
                    "source_file": record.source_file,
                    "_note": "neo4j_candidate_export_only_not_written_to_graph",
                }
            )
        )
    content = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    write_compatibility_artifact(
        output_path,
        make_rendered_artifact(
            logical_id="legacy-neo4j-candidate",
            destination_path=output_path.name,
            artifact_kind="graph-export",
            media_type="application/x-ndjson",
            content=content,
        ),
    )
