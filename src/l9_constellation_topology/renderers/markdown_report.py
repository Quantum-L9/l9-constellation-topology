"""Pure Markdown projections for canonical and legacy topology models."""

from __future__ import annotations

from l9_constellation_topology.io import RenderedArtifact
from l9_constellation_topology.models import TopologyReport
from l9_constellation_topology.packets import MaterializedTopology

from .common import make_rendered_artifact


def render_topology_markdown(materialized: MaterializedTopology) -> str:
    packet = materialized.packet
    state = materialized.state
    lines = [
        "# L9 Constellation Topology",
        "",
        f"**Topology Packet:** `{packet.packet_id}`",
        f"**Semantic hash:** `{packet.semantic_hash}`",
        f"**Profile:** `{packet.profile.id}/{packet.profile.version}`",
        f"**Repositories:** {len(state.repository_records)}",
        f"**Artifacts:** {len(state.artifact_records)}",
        f"**Capabilities:** {len(state.capability_records)}",
        f"**Edges:** {len(state.edge_records)}",
        "",
        "## Repository Inventory",
        "",
        "| Repository | Role | Revision | Languages | Confidence |",
        "|---|---|---|---|---|",
    ]
    for repository in state.repository_records:
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{repository.repository_id}`",
                    repository.primary_role,
                    f"`{repository.source_revision}`",
                    ", ".join(repository.languages) or "Unknown",
                    repository.confidence.level.value,
                )
            )
            + " |"
        )

    lines.extend(("", "## Dependency Topology", ""))
    dependency_edges = [edge for edge in state.edge_records if edge.edge_type.value == "DEPENDS_ON"]
    if dependency_edges:
        lines.extend(("| Source | Target | Confidence |", "|---|---|---|"))
        for edge in dependency_edges:
            lines.append(
                f"| `{edge.source_id}` | `{edge.target_id}` | {edge.confidence.level.value} |"
            )
    else:
        lines.append("No repository dependency edges were accepted.")

    lines.extend(("", "## Risks", ""))
    if state.risks:
        lines.extend(("| Subject | Severity | Category | Finding |", "|---|---|---|---|"))
        for risk in state.risks:
            lines.append(
                f"| `{risk.subject_id}` | {risk.severity} | {risk.category} | {risk.description} |"
            )
    else:
        lines.append("No configured risk rules fired.")

    lines.extend(("", "## Maturity", ""))
    if state.maturity:
        lines.extend(("| Subject | Score | Band | Profile |", "|---|---|---|---|"))
        for assessment in state.maturity:
            lines.append(
                f"| `{assessment.subject_id}` | {assessment.score}/{assessment.maximum_score} | "
                f"{assessment.band} | `{assessment.profile_id}/{assessment.profile_version}` |"
            )
    else:
        lines.append("No maturity projections were computed.")

    lines.extend(("", "## Unknowns", ""))
    if state.unknowns:
        for unknown in state.unknowns:
            lines.append(f"- `{unknown.subject_id}`: {unknown.reason}")
    else:
        lines.append("No unknowns were recorded.")

    lines.extend(("", "## Conflicts", ""))
    if state.conflicts:
        for conflict in state.conflicts:
            disposition = (
                "BLOCKING" if conflict.blocking and not conflict.resolution else "preserved"
            )
            lines.append(
                f"- `{conflict.subject_id}.{conflict.field}` ({disposition}): "
                + ", ".join(conflict.values)
            )
    else:
        lines.append("No conflicts were recorded.")
    return "\n".join(lines) + "\n"


def render_markdown_artifact(materialized: MaterializedTopology) -> RenderedArtifact:
    content = render_topology_markdown(materialized).encode("utf-8")
    return make_rendered_artifact(
        logical_id="topology-report-markdown",
        destination_path="topology-report.md",
        artifact_kind="human-report",
        media_type="text/markdown",
        content=content,
        semantic_hash=materialized.packet.semantic_hash,
        source_refs=(materialized.packet.packet_id,),
    )


def render_markdown(report: TopologyReport) -> str:
    """Legacy v4 formatter retained for compatibility tests and migration tooling."""
    lines: list[str] = []
    lines.append("# L9 Constellation Topology Report")
    lines.append(f"\n**Constellation:** {report.constellation_name}")
    lines.append(f"**Generated:** {report.generated_at}")
    lines.append(f"**Repos scanned:** {len(report.repo_inventory)}")
    lines.extend(("\n---\n", "## Repo Inventory\n"))
    lines.append("| Repo ID | Name | Role | Languages | Confidence |")
    lines.append("|---|---|---|---|---|")
    for card in report.repo_inventory:
        langs = ", ".join(card.languages) or "UNKNOWN"
        lines.append(
            f"| {card.repo_id} | {card.name} | {card.primary_role} | {langs} | {card.confidence.value} |"
        )
    lines.extend(("\n---\n", "## Dependency Graph\n"))
    if report.dependency_graph:
        lines.append("| Source | Target | Type | Direction | Confidence |")
        lines.append("|---|---|---|---|---|")
        for edge in report.dependency_graph:
            lines.append(
                f"| {edge.source} | {edge.target} | {edge.edge_type.value} | "
                f"{edge.direction.value} | {edge.confidence.value} |"
            )
    else:
        lines.append("_No cross-repo dependency edges detected._")
    lines.extend(("\n---\n", "## Risk Register\n"))
    if report.risk_register:
        lines.append("| Risk ID | Repo | Severity | Category | Description |")
        lines.append("|---|---|---|---|---|")
        for risk in report.risk_register:
            lines.append(
                f"| {risk.risk_id} | {risk.repo_id} | {risk.severity} | "
                f"{risk.category} | {risk.description} |"
            )
    else:
        lines.append("_No risks detected._")
    lines.extend(("\n---\n", "## Maturity Scorecard\n"))
    if report.maturity_scorecard:
        lines.extend(("| Repo ID | Score | Band |", "|---|---|---|"))
        for score in report.maturity_scorecard:
            lines.append(f"| {score.repo_id} | {score.score} | {score.band} |")
    else:
        lines.append("_No maturity scores computed._")
    lines.extend(("\n---\n", "## Unknowns\n"))
    if report.unknowns:
        lines.extend(f"- `{unknown}`" for unknown in report.unknowns)
    else:
        lines.append("_No unknowns recorded._")
    return "\n".join(lines) + "\n"
