"""Pure Markdown projections for canonical and legacy topology models."""

from __future__ import annotations

from collections.abc import Callable

from l9_constellation_topology.domain.edge import EdgeType
from l9_constellation_topology.domain.reasoning import TopologyReasoningCandidate
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
        *_table("Repository", "Role", "Revision", "Languages", "Confidence"),
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
        lines.extend(_table("Source", "Target", "Confidence"))
        for edge in dependency_edges:
            lines.append(
                f"| `{edge.source_id}` | `{edge.target_id}` | {edge.confidence.level.value} |"
            )
    else:
        lines.append("No repository dependency edges were accepted.")

    lines.extend(("", "## Risks", ""))
    if state.risks:
        lines.extend(_table("Subject", "Severity", "Category", "Finding"))
        for risk in state.risks:
            lines.append(
                f"| `{risk.subject_id}` | {risk.severity} | {risk.category} | {risk.description} |"
            )
    else:
        lines.append("No configured risk rules fired.")

    lines.extend(("", "## Maturity", ""))
    if state.maturity:
        lines.extend(_table("Subject", "Score", "Band", "Profile"))
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


def _table(*headers: str) -> tuple[str, str]:
    """Return a header row and the separator that must match its width.

    The separator is derived from the header rather than written beside it. Six
    copies of ``|---|---|---|---|`` were previously spelled out, and a table
    whose separator has a different column count from its header renders as
    plain text in most viewers — a failure that is invisible in the source.
    """
    return ("| " + " | ".join(headers) + " |", "|" + "---|" * len(headers))


def _row(*cells: str) -> str:
    """Return one table row."""
    return "| " + " | ".join(cells) + " |"


def _routing_movement(row: TopologyReasoningCandidate) -> str:
    """How topology's routing compares to the producer's, in one word."""
    if row.escalated:
        return "escalated"
    if row.deescalated:
        return "de-escalated"
    return "unchanged"


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
        *_table(
            "Candidate",
            "Members",
            "Confidence",
            "Structural support",
            "Ambiguity",
            "Readiness",
        ),
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


def _corpus_overview(state: TopologyState) -> list[str]:
    """The corpus and its roots. Empty when no corpus was compiled."""
    if not state.corpus_records:
        return ["No corpus intelligence was compiled into this topology."]
    lines = list(_table("Corpus", "Source snapshot", "Analysis", "Roots"))
    lines.extend(
        _row(
            f"`{corpus.corpus_id}`",
            f"`{corpus.corpus_source_snapshot_id}`",
            f"`{corpus.corpus_analysis_id}`",
            str(len(corpus.root_ids)),
        )
        for corpus in state.corpus_records
    )
    lines.extend(("", *_table("Root", "Identity", "Revision", "Repository")))
    lines.extend(
        _row(
            f"`{root.root_id}`",
            root.identity_class,
            f"`{root.source_revision}`",
            f"`{root.repository_id}`" if root.repository_id else "none observed",
        )
        for root in state.root_records
    )
    return lines


def _duplicate_section(state: TopologyState) -> list[str]:
    """Byte-identical artifacts, and the hash that decided each pair."""
    duplicates = [edge for edge in state.edge_records if edge.edge_type is EdgeType.duplicate_of]
    if not duplicates:
        return ["No byte-identical artifacts were observed."]
    lines = [
        "_Byte identity only. Every pair below carries the same content hash; "
        "no similarity score contributes to this table._",
        "",
        *_table("Artifact", "Duplicate of", "Cluster", "Content hash"),
    ]
    lines.extend(
        _row(
            f"`{edge.source_id}`",
            f"`{edge.target_id}`",
            f"`{edge.properties.get('duplicate_cluster_id', '')}`",
            f"`{str(edge.properties.get('content_hash', ''))[:23]}…`",
        )
        for edge in duplicates
    )
    return lines


def _work_relation_section(state: TopologyState) -> list[str]:
    """Explicitly declared work relations, with how each target resolved."""
    work_edges = [edge for edge in state.edge_records if "target_resolution" in edge.properties]
    if not work_edges:
        return ["No explicit work relationships were declared."]
    lines = list(_table("Source", "Relation", "Target", "Resolution"))
    lines.extend(
        _row(
            f"`{edge.source_id}`",
            edge.edge_type.value,
            f"`{edge.target_id}`",
            str(edge.properties.get("target_resolution")),
        )
        for edge in work_edges
    )
    return lines


def _readiness_section(state: TopologyState) -> list[str]:
    """Readiness counts. Never a score — see the disclaimer it carries."""
    if not state.readiness_evidence:
        return ["No readiness evidence was compiled."]
    lines = [
        READINESS_DISCLAIMER,
        "",
        *_table("Subject", "Source", "Tests", "CI", "Docs", "Open tasks", "Blocked", "Gaps"),
    ]
    lines.extend(
        _row(
            f"`{readiness.subject_id}`",
            str(readiness.source_artifact_count),
            str(readiness.test_artifact_count),
            str(readiness.ci_definition_count),
            str(readiness.documentation_count),
            str(readiness.open_task_count),
            str(readiness.blocked_count),
            str(readiness.coverage_gap_count),
        )
        for readiness in state.readiness_evidence
    )
    return lines


def _reasoning_section(state: TopologyState) -> list[str]:
    """The reasoning queue, with both routings and how they differ."""
    if not state.topology_reasoning_candidates:
        return ["No reasoning candidates were routed."]
    lines = [
        "_A deterministic handoff. No model was called to produce this queue, and "
        "nothing in it has been adjudicated._",
        "",
        *_table("Candidate", "Upstream", "Topology", "Movement", "Signals"),
    ]
    lines.extend(
        _row(
            f"`{row.candidate_id}`",
            row.upstream_recommended_reasoning_type or "none",
            row.topology_recommended_reasoning_type,
            _routing_movement(row),
            ", ".join(row.structural_signals) or "none",
        )
        for row in state.topology_reasoning_candidates
    )
    return lines


#: Each corpus-scoped section, in the order a reader meets them. A table rather
#: than a hundred-line function: adding a section is one entry, and each builder
#: is independently readable and independently testable.
_CORPUS_SECTIONS: tuple[tuple[str, Callable[[TopologyState], list[str]]], ...] = (
    ("Corpus Overview", _corpus_overview),
    ("Cross-Root Exact Duplicates", _duplicate_section),
    ("Explicit Work Relationships", _work_relation_section),
    ("Candidate Topics", lambda state: _candidate_table(state, "TOPIC_CANDIDATE")),
    ("Candidate Bodies of Work", lambda state: _candidate_table(state, "PROJECT_CANDIDATE")),
    (
        "Consolidation Candidates",
        lambda state: _candidate_table(state, "CONSOLIDATION_CANDIDATE"),
    ),
    ("Readiness Evidence", _readiness_section),
    ("Reasoning Queue", _reasoning_section),
)


def _corpus_sections(state: TopologyState) -> list[str]:
    """Render every corpus-scoped section, in the order a reader meets them."""
    lines: list[str] = []
    for heading, build in _CORPUS_SECTIONS:
        lines.extend(("", f"## {heading}", ""))
        lines.extend(build(state))
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
