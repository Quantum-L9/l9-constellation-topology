"""Lazy report projection lifecycle and cache identity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from l9_constellation_topology.io import RenderedArtifact
from l9_constellation_topology.packets import (
    MaterializedTopology,
    Producer,
    ReportManifest,
    ReportRef,
)
from l9_constellation_topology.packets.report_manifest import finalize_report_manifest
from l9_constellation_topology.run import canonical_bytes, semantic_hash, utc_now

from .common import make_rendered_artifact
from .csv_export import render_maturity_csv_artifact, render_repository_inventory_yaml_artifact
from .json_export import (
    render_graph_records_jsonl_artifact,
    render_neo4j_candidate_artifact,
    render_topology_json_artifact,
)
from .markdown_report import render_markdown_artifact
from .mermaid_export import render_mermaid_artifact
from .risk_report import render_risk_markdown_artifact

RENDERER_ID = "l9-topology-renderer"
RENDERER_VERSION = "2.0.0"
SUPPORTED_FORMATS = (
    "markdown",
    "mermaid",
    "maturity-csv",
    "repository-yaml",
    "json",
    "graph-jsonl",
    "neo4j-candidate",
    "risk-markdown",
)
DEFAULT_FORMATS = (
    "markdown",
    "mermaid",
    "maturity-csv",
    "repository-yaml",
    "json",
    "neo4j-candidate",
    "risk-markdown",
)


@dataclass(frozen=True)
class ReportProjection:
    manifest: ReportManifest
    artifacts: tuple[RenderedArtifact, ...]


def projection_cache_key(source_semantic_hash: str, report_profile_hash: str) -> str:
    return semantic_hash(
        {
            "source_semantic_hash": source_semantic_hash,
            "renderer_id": RENDERER_ID,
            "renderer_version": RENDERER_VERSION,
            "report_profile_hash": report_profile_hash,
        }
    )


def render_reports(
    materialized: MaterializedTopology,
    *,
    formats: tuple[str, ...] = DEFAULT_FORMATS,
    report_profile_hash: str,
    created_at: datetime | None = None,
) -> ReportProjection:
    requested = tuple(dict.fromkeys(formats))
    unsupported = tuple(sorted(set(requested) - set(SUPPORTED_FORMATS)))
    if unsupported:
        raise ValueError(f"unsupported report formats: {', '.join(unsupported)}")
    factories = {
        "markdown": render_markdown_artifact,
        "mermaid": render_mermaid_artifact,
        "maturity-csv": render_maturity_csv_artifact,
        "repository-yaml": render_repository_inventory_yaml_artifact,
        "json": render_topology_json_artifact,
        "graph-jsonl": render_graph_records_jsonl_artifact,
        "neo4j-candidate": render_neo4j_candidate_artifact,
        "risk-markdown": render_risk_markdown_artifact,
    }
    artifacts = tuple(factories[name](materialized) for name in requested)
    cache_key = projection_cache_key(materialized.packet.semantic_hash, report_profile_hash)
    candidate = ReportManifest(
        source_packet_id=materialized.packet.packet_id,
        source_semantic_hash=materialized.packet.semantic_hash,
        renderer=Producer(name=RENDERER_ID, version=RENDERER_VERSION),
        report_profile_hash=report_profile_hash,
        cache_key=cache_key,
        reports=tuple(
            ReportRef(
                report_type=name,
                uri=artifact.destination_path,
                content_hash=artifact.content_hash,
                media_type=artifact.media_type,
            )
            for name, artifact in zip(requested, artifacts, strict=True)
        ),
        semantic_hash="sha256:pending",
        created_at=created_at if created_at is not None else utc_now(),
    )
    manifest = finalize_report_manifest(candidate)
    manifest_artifact = make_rendered_artifact(
        logical_id="report-manifest",
        destination_path="report-manifest.json",
        artifact_kind="report-manifest",
        media_type="application/json",
        content=canonical_bytes(manifest) + b"\n",
        semantic_hash=manifest.semantic_hash,
        source_refs=(materialized.packet.packet_id,),
    )
    return ReportProjection(manifest=manifest, artifacts=(*artifacts, manifest_artifact))
