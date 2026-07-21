"""Pure risk-register projection."""

from __future__ import annotations

from l9_constellation_topology.io import RenderedArtifact
from l9_constellation_topology.packets import MaterializedTopology

from .common import make_rendered_artifact


def render_risk_markdown_artifact(materialized: MaterializedTopology) -> RenderedArtifact:
    lines = [
        "# Topology Risk Register",
        "",
        f"Source packet: `{materialized.packet.packet_id}`",
        "",
        "| Risk | Subject | Severity | Category | Status | Finding | Remediation |",
        "|---|---|---|---|---|---|---|",
    ]
    for risk in materialized.state.risks:
        lines.append(
            f"| `{risk.risk_id}` | `{risk.subject_id}` | {risk.severity} | {risk.category} | "
            f"{risk.status} | {risk.description} | {risk.remediation or 'Not specified'} |"
        )
    if not materialized.state.risks:
        lines.append(
            "| None | None | None | None | None | No configured risk rules fired. | None |"
        )
    content = ("\n".join(lines) + "\n").encode("utf-8")
    return make_rendered_artifact(
        logical_id="topology-risk-register",
        destination_path="risk-register.md",
        artifact_kind="risk-report",
        media_type="text/markdown",
        content=content,
        semantic_hash=materialized.packet.semantic_hash,
        source_refs=(materialized.packet.packet_id,),
    )
