"""Scan repo for Graphiti memory integration signals. Read-only. No writes."""

from __future__ import annotations

from pathlib import Path

from l9_constellation_topology.models import EvidenceItem, SourceType

_GRAPHITI_SIGNALS = ["graphiti", "graphiti_client", "graphiti_core", "episode_id"]


def scan_graphiti(
    repo_path: Path, repo_id: str
) -> tuple[list[dict[str, object]], list[EvidenceItem]]:
    """Return (graphiti_topology_entries, evidence). No Graphiti API calls."""
    entries: list[dict[str, object]] = []
    evidence: list[EvidenceItem] = []

    text_files = (
        list(repo_path.rglob("*.py"))
        + list(repo_path.rglob("*.toml"))
        + list(repo_path.rglob("*.yaml"))
    )

    for tf in text_files:
        try:
            text = tf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for signal in _GRAPHITI_SIGNALS:
            if signal in text:
                rel = str(tf.relative_to(repo_path))
                line_num = next(
                    (i + 1 for i, line in enumerate(text.splitlines()) if signal in line),
                    None,
                )
                entry: dict[str, object] = {
                    "repo_id": repo_id,
                    "signal": signal,
                    "source_file": rel,
                    "episode_id": "UNKNOWN",
                    "note": "graphiti_memory_boundary_read_only",
                }
                entries.append(entry)
                evidence.append(
                    EvidenceItem(
                        source_file=rel,
                        source_type=SourceType.file,
                        excerpt=f"graphiti_signal:{signal}",
                        line_number=line_num,
                    )
                )
                break

    return entries, evidence
