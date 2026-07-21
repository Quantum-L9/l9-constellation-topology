"""Scan repo for governance files and ownership signals."""

from __future__ import annotations

from pathlib import Path

from l9_constellation_topology.models import EvidenceItem, SourceType

_GOVERNANCE_FILES = [
    "CODEOWNERS",
    ".github/CODEOWNERS",
    "OWNERS",
    "MAINTAINERS",
    "GOVERNANCE.md",
    "governance.md",
    "SECURITY.md",
    "LICENSE",
]

_OWNER_PATTERN_FILES = ["CODEOWNERS", ".github/CODEOWNERS", "OWNERS"]


def scan_governance(repo_path: Path, repo_id: str) -> tuple[list[str], str, list[EvidenceItem]]:
    """Return (governance_files, owner, evidence)."""
    found_files: list[str] = []
    evidence: list[EvidenceItem] = []
    owner = "UNKNOWN"

    for gf in _GOVERNANCE_FILES:
        p = repo_path / gf
        if p.exists():
            rel = str(p.relative_to(repo_path))
            found_files.append(rel)
            evidence.append(
                EvidenceItem(
                    source_file=rel,
                    source_type=SourceType.file,
                    excerpt=f"governance:{gf}",
                )
            )

    for of in _OWNER_PATTERN_FILES:
        p = repo_path / of
        if p.exists() and owner == "UNKNOWN":
            text = p.read_text(encoding="utf-8")
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split()
                    if len(parts) >= 2:
                        owner = parts[-1].lstrip("@")
                        break

    return found_files, owner, evidence
