"""Pure Mermaid projections with sink-backed compatibility wrapper."""

from __future__ import annotations

import re
from pathlib import Path

from l9_constellation_topology.io import RenderedArtifact
from l9_constellation_topology.models import TopologyReport
from l9_constellation_topology.packets import MaterializedTopology

from .common import make_rendered_artifact, write_compatibility_artifact


def _safe(value: str) -> str:
    return re.sub(r"\W", "_", value)


def render_mermaid_artifact(materialized: MaterializedTopology) -> RenderedArtifact:
    lines = ["graph TD"]
    for repository in materialized.state.repository_records:
        lines.append(
            f'  {_safe(repository.repository_id)}["{repository.name}\\n[{repository.primary_role}]"]'
        )
    for edge in materialized.state.edge_records:
        lines.append(
            f"  {_safe(edge.source_id)} -->|{edge.edge_type.value}| {_safe(edge.target_id)}"
        )
    content = ("\n".join(lines) + "\n").encode("utf-8")
    return make_rendered_artifact(
        logical_id="topology-mermaid",
        destination_path="topology.mmd",
        artifact_kind="diagram",
        media_type="text/vnd.mermaid",
        content=content,
        semantic_hash=materialized.packet.semantic_hash,
        source_refs=(materialized.packet.packet_id,),
    )


def export_mermaid(report: TopologyReport, output_path: Path) -> None:
    lines = ["graph TD", f'  subgraph "{report.constellation_name}"']
    for card in report.repo_inventory:
        lines.append(f'    {_safe(card.repo_id)}["{card.name}\\n[{card.primary_role}]"]')
    lines.append("  end")
    for edge in report.dependency_graph:
        lines.append(f"  {_safe(edge.source)} -->|{edge.edge_type.value}| {_safe(edge.target)}")
    content = ("\n".join(lines) + "\n").encode("utf-8")
    write_compatibility_artifact(
        output_path,
        make_rendered_artifact(
            logical_id="legacy-topology-mermaid",
            destination_path=output_path.name,
            artifact_kind="diagram",
            media_type="text/vnd.mermaid",
            content=content,
        ),
    )
