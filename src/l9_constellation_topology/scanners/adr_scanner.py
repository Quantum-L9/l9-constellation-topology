"""Scan repo for Architecture Decision Records."""

from __future__ import annotations

from pathlib import Path

from l9_constellation_topology.models import EvidenceItem, SourceType

_ADR_DIRS = ["docs/adr", "doc/adr", "adr", "docs/decisions", "decisions", "docs/architecture"]
_ADR_PREFIXES = ("adr-", "adr_", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9")


def scan_adrs(repo_path: Path, repo_id: str) -> tuple[list[str], list[EvidenceItem]]:
    """Return (adr_file_paths, evidence)."""
    adr_files: list[str] = []
    evidence: list[EvidenceItem] = []

    for adr_dir in _ADR_DIRS:
        candidate = repo_path / adr_dir
        if candidate.is_dir():
            for f in candidate.rglob("*.md"):
                rel = str(f.relative_to(repo_path))
                adr_files.append(rel)
                evidence.append(
                    EvidenceItem(
                        source_file=rel,
                        source_type=SourceType.file,
                        excerpt=f"adr_candidate:{f.name}",
                    )
                )

    for md in repo_path.rglob("*.md"):
        name_lower = md.stem.lower()
        if name_lower.startswith(_ADR_PREFIXES) and "adr" in str(md.parent).lower():
            rel = str(md.relative_to(repo_path))
            if rel not in adr_files:
                adr_files.append(rel)
                evidence.append(
                    EvidenceItem(
                        source_file=rel,
                        source_type=SourceType.file,
                        excerpt=f"adr_pattern:{md.name}",
                    )
                )

    return adr_files, evidence
