"""Pure Markdown projections for canonical and legacy topology models."""

from __future__ import annotations

from l9_constellation_topology.domain.edge import EdgeType
from l9_constellation_topology.domain.topology import TopologyState
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

    lines.extend(_corpus_sections(state))

    # Renamed from "Unknowns": with a corpus in play, an unresolved reference and
    # an artifact whose bytes were never read are both things this compile could
    # not answer, and reporting them under one heading is what keeps a reader
    # from mistaking thin coverage for a thin corpus.
    lines.extend(("", "## Coverage and Unknowns", ""))
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


#: Restated in every candidate section, because a section is what gets copied
#: into a ticket or a message. A reader who sees only the table needs the
#: epistemic class beside it, not three sections away.
CANDIDATE_DISCLAIMER = (
    "_Candidate analysis. These groupings are proposals supported by the evidence "
    "shown; none is a decided fact, none is a canonical topology edge, and none "
    "enters dependency impact._"
)

#: Same, for readiness.
READINESS_DISCLAIMER = (
    "_Counts of artifacts and declarations observed. Not a score, not a "
    "completion estimate, and not a priority: a body of work with more test files "
    "is not thereby more ready._"
)


def _candidate_table(state: TopologyState, candidate_type: str) -> list[str]:
    """Render one candidate class, with the structure topology measured for it."""
    rows = [
        candidate
        for candidate in state.candidate_clusters
        if candidate.candidate_type == candidate_type
    ]
    if not rows:
        return ["No candidates of this class were carried."]
    lines = [
        CANDIDATE_DISCLAIMER,
        "",
        "| Candidate | Members | Confidence | Structural support | Ambiguity | Readiness |",
        "|---|---|---|---|---|---|",
    ]
    for candidate in rows:
        evidence = candidate.structural_evidence
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{candidate.candidate_id}`",
                    str(evidence.member_count),
                    candidate.confidence_class,
                    str(evidence.structural_support_count),
                    ", ".join(candidate.ambiguity_flags) or "none",
                    f"`{candidate.readiness_evidence_ref}`"
                    if candidate.readiness_evidence_ref
                    else "none",
                )
            )
            + " |"
        )
    return lines


def _corpus_sections(state: TopologyState) -> list[str]:
    """Render every corpus-scoped section, in the order a reader meets them."""
    lines: list[str] = []

    lines.extend(("", "## Corpus Overview", ""))
    if state.corpus_records:
        lines.extend(("| Corpus | Source snapshot | Analysis | Roots |", "|---|---|---|---|"))
        for corpus in state.corpus_records:
            lines.append(
                f"| `{corpus.corpus_id}` | `{corpus.corpus_source_snapshot_id}` | "
                f"`{corpus.corpus_analysis_id}` | {len(corpus.root_ids)} |"
            )
        lines.extend(("", "| Root | Identity | Revision | Repository |", "|---|---|---|---|"))
        for root in state.root_records:
            lines.append(
                f"| `{root.root_id}` | {root.identity_class} | "
                f"`{root.source_revision}` | "
                + (f"`{root.repository_id}`" if root.repository_id else "none observed")
                + " |"
            )
    else:
        lines.append("No corpus intelligence was compiled into this topology.")

    lines.extend(("", "## Cross-Root Exact Duplicates", ""))
    duplicates = [edge for edge in state.edge_records if edge.edge_type is EdgeType.duplicate_of]
    if duplicates:
        lines.append(
            "_Byte identity only. Every pair below carries the same content hash; "
            "no similarity score contributes to this table._"
        )
        lines.extend(
            ("", "| Artifact | Duplicate of | Cluster | Content hash |", "|---|---|---|---|")
        )
        for edge in duplicates:
            digest = str(edge.properties.get("content_hash", ""))
            lines.append(
                f"| `{edge.source_id}` | `{edge.target_id}` | "
                f"`{edge.properties.get('duplicate_cluster_id', '')}` | `{digest[:23]}…` |"
            )
    else:
        lines.append("No byte-identical artifacts were observed.")

    lines.extend(("", "## Explicit Work Relationships", ""))
    work_edges = [edge for edge in state.edge_records if "target_resolution" in edge.properties]
    if work_edges:
        lines.extend(("| Source | Relation | Target | Resolution |", "|---|---|---|---|"))
        for edge in work_edges:
            lines.append(
                f"| `{edge.source_id}` | {edge.edge_type.value} | `{edge.target_id}` | "
                f"{edge.properties.get('target_resolution')} |"
            )
    else:
        lines.append("No explicit work relationships were declared.")

    lines.extend(("", "## Candidate Topics", ""))
    lines.extend(_candidate_table(state, "TOPIC_CANDIDATE"))
    lines.extend(("", "## Candidate Bodies of Work", ""))
    lines.extend(_candidate_table(state, "PROJECT_CANDIDATE"))
    lines.extend(("", "## Consolidation Candidates", ""))
    lines.extend(_candidate_table(state, "CONSOLIDATION_CANDIDATE"))

    lines.extend(("", "## Readiness Evidence", ""))
    if state.readiness_evidence:
        lines.extend(
            (
                READINESS_DISCLAIMER,
                "",
                "| Subject | Source | Tests | CI | Docs | Open tasks | Blocked | Gaps |",
                "|---|---|---|---|---|---|---|---|",
            )
        )
        for readiness in state.readiness_evidence:
            lines.append(
                "| "
                + " | ".join(
                    (
                        f"`{readiness.subject_id}`",
                        str(readiness.source_artifact_count),
                        str(readiness.test_artifact_count),
                        str(readiness.ci_definition_count),
                        str(readiness.documentation_count),
                        str(readiness.open_task_count),
                        str(readiness.blocked_count),
                        str(readiness.coverage_gap_count),
                    )
                )
                + " |"
            )
    else:
        lines.append("No readiness evidence was compiled.")

    lines.extend(("", "## Reasoning Queue", ""))
    if state.topology_reasoning_candidates:
        lines.append(
            "_A deterministic handoff. No model was called to produce this queue, and "
            "nothing in it has been adjudicated._"
        )
        lines.extend(
            (
                "",
                "| Candidate | Upstream | Topology | Movement | Signals |",
                "|---|---|---|---|---|",
            )
        )
        for row in state.topology_reasoning_candidates:
            movement = (
                "escalated" if row.escalated else "de-escalated" if row.deescalated else "unchanged"
            )
            lines.append(
                "| "
                + " | ".join(
                    (
                        f"`{row.candidate_id}`",
                        row.upstream_recommended_reasoning_type or "none",
                        row.topology_recommended_reasoning_type,
                        movement,
                        ", ".join(row.structural_signals) or "none",
                    )
                )
                + " |"
            )
    else:
        lines.append("No reasoning candidates were routed.")
    return lines


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
