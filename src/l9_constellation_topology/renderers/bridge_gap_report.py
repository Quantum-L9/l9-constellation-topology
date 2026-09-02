"""JSON and Markdown projections for bridge-gap decision support."""

from __future__ import annotations

from l9_constellation_topology.domain import BridgeGapProjection
from l9_constellation_topology.io import RenderedArtifact
from l9_constellation_topology.packets import MaterializedTopology
from l9_constellation_topology.run import canonical_bytes
from l9_constellation_topology.topology.bridge_gaps import project_bridge_gaps

from .common import make_rendered_artifact


def build_bridge_gap_projection(materialized: MaterializedTopology) -> BridgeGapProjection:
    return project_bridge_gaps(
        materialized.state,
        source_packet_id=materialized.packet.packet_id,
        source_semantic_hash=materialized.packet.semantic_hash,
    )


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_bridge_gap_markdown(projection: BridgeGapProjection) -> str:
    lines = [
        "# L9 Bridge Gaps",
        "",
        f"**Source Topology Packet:** `{projection.source_packet_id}`",
        f"**Source semantic hash:** `{projection.source_semantic_hash}`",
        f"**Policy:** `{projection.policy_id}/{projection.policy_version}`",
        f"**Projection semantic hash:** `{projection.semantic_hash}`",
        f"**Detected gaps:** {len(projection.gaps)}",
        f"**Unknown activation intent:** {projection.unknown_intent_count}",
        "",
        "> Decision-support projection only. It does not activate capabilities, dispatch effects,",
        "> mutate repositories, or treat every disconnected capability as a defect.",
        "",
        "## Summary",
        "",
    ]
    if projection.counts_by_type:
        lines.extend(("| Gap type | Count |", "|---|---:|"))
        lines.extend(
            f"| `{gap_type}` | {count} |"
            for gap_type, count in projection.counts_by_type.items()
        )
    else:
        lines.append("No bridge gaps were proven from the supplied topology.")

    lines.extend(("", "## Findings", ""))
    if not projection.gaps:
        lines.append("No findings.")
        return "\n".join(lines) + "\n"

    lines.extend(
        (
            "| Subject | Gap | Observed → expected | Intent | Disposition | Evidence |",
            "|---|---|---|---|---|---:|",
        )
    )
    for gap in projection.gaps:
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{_cell(gap.subject_id)}`",
                    f"`{gap.gap_type.value}`",
                    f"{gap.observed_state.value} → {gap.expected_state.value}",
                    gap.activation_intent.value,
                    gap.disposition.value,
                    str(len(gap.evidence_refs)),
                )
            )
            + " |"
        )
        lines.extend(
            (
                "",
                f"### `{gap.bridge_gap_id}`",
                "",
                f"- **Subject:** `{gap.subject_id}` ({gap.subject_kind})",
                f"- **Reason:** {_cell(gap.reason)}",
                f"- **Next action:** {_cell(gap.recommended_action)}",
                "- **Producers:** "
                + (", ".join(f"`{item}`" for item in gap.producer_ids) or "none observed"),
                "- **Consumers:** "
                + (", ".join(f"`{item}`" for item in gap.consumer_ids) or "none observed"),
            )
        )
    return "\n".join(lines) + "\n"


def render_bridge_gap_json_artifact(
    materialized: MaterializedTopology,
) -> RenderedArtifact:
    projection = build_bridge_gap_projection(materialized)
    return make_rendered_artifact(
        logical_id="bridge-gap-projection-json",
        destination_path="bridge-gaps.json",
        artifact_kind="human-report",
        media_type="application/json",
        content=canonical_bytes(projection) + b"\n",
        semantic_hash=projection.semantic_hash,
        source_refs=(materialized.packet.packet_id,),
    )


def render_bridge_gap_markdown_artifact(
    materialized: MaterializedTopology,
) -> RenderedArtifact:
    projection = build_bridge_gap_projection(materialized)
    return make_rendered_artifact(
        logical_id="bridge-gap-projection-markdown",
        destination_path="BRIDGE_GAPS.md",
        artifact_kind="human-report",
        media_type="text/markdown",
        content=render_bridge_gap_markdown(projection).encode("utf-8"),
        semantic_hash=projection.semantic_hash,
        source_refs=(materialized.packet.packet_id,),
    )
