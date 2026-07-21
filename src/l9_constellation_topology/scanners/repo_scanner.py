"""Orchestrates all sub-scanners to produce a RepoCard from a local path."""

from __future__ import annotations

from pathlib import Path

from l9_constellation_topology.models import (
    Confidence,
    EvidenceItem,
    RepoCard,
    RepoSource,
    SourceType,
)
from l9_constellation_topology.scanners.adr_scanner import scan_adrs
from l9_constellation_topology.scanners.ci_scanner import scan_ci
from l9_constellation_topology.scanners.dependency_scanner import scan_dependencies
from l9_constellation_topology.scanners.governance_scanner import scan_governance
from l9_constellation_topology.scanners.graphiti_scanner import scan_graphiti
from l9_constellation_topology.scanners.manifest_scanner import scan_manifests
from l9_constellation_topology.topology.classifier import classify_repo

_README_NAMES = {"readme.md", "readme.rst", "readme.txt", "readme"}


def scan_repo(source: RepoSource) -> RepoCard:
    """Scan a single repo from its local path and return a RepoCard."""
    repo_path = Path(source.local_path)
    evidence: list[EvidenceItem] = []
    unknowns: list[str] = []

    if not repo_path.exists():
        return RepoCard(
            repo_id=source.repo_id,
            name=source.name,
            path=source.local_path,
            primary_role="UNKNOWN",
            confidence=Confidence.low,
            evidence=[
                EvidenceItem(
                    source_file=source.local_path,
                    source_type=SourceType.unknown,
                    excerpt="path_does_not_exist",
                )
            ],
        )

    for item in repo_path.iterdir():
        if item.name.lower() in _README_NAMES:
            evidence.append(
                EvidenceItem(
                    source_file=str(item.relative_to(repo_path)),
                    source_type=SourceType.file,
                    excerpt="readme_present",
                )
            )

    languages, package_managers, entrypoints, manifest_ev = scan_manifests(
        repo_path, source.repo_id
    )
    evidence.extend(manifest_ev)

    ci_workflows, ci_ev = scan_ci(repo_path, source.repo_id)
    evidence.extend(ci_ev)

    adr_files, adr_ev = scan_adrs(repo_path, source.repo_id)
    evidence.extend(adr_ev)

    upstream_deps, dep_ev = scan_dependencies(repo_path, source.repo_id)
    evidence.extend(dep_ev)

    governance_files, owner, gov_ev = scan_governance(repo_path, source.repo_id)
    evidence.extend(gov_ev)

    _graphiti_entries, gph_ev = scan_graphiti(repo_path, source.repo_id)
    evidence.extend(gph_ev)

    if source.remote_url == "UNKNOWN":
        unknowns.append(f"{source.repo_id}:remote_url_unknown")
    if source.group_id == "UNKNOWN":
        unknowns.append(f"{source.repo_id}:group_id_unknown")

    signal_count = (
        len(languages)
        + len(ci_workflows)
        + len(governance_files)
        + len(adr_files)
        + len(upstream_deps)
    )
    if signal_count >= 4:
        confidence = Confidence.high
    elif signal_count >= 2:
        confidence = Confidence.medium
    else:
        confidence = Confidence.low

    primary_role = source.expected_role if source.expected_role != "UNKNOWN" else "UNKNOWN"

    card = RepoCard(
        repo_id=source.repo_id,
        name=source.name,
        path=source.local_path,
        primary_role=primary_role,
        languages=languages,
        package_managers=package_managers,
        entrypoints=entrypoints,
        ci_workflows=ci_workflows,
        adr_files=adr_files,
        governance_files=governance_files,
        upstream_dependencies=upstream_deps,
        owner=owner,
        evidence=evidence,
        confidence=confidence,
    )

    card = classify_repo(card)
    return card


def scan_many(sources: list[RepoSource]) -> list[RepoCard]:
    """Scan multiple repos and return all RepoCards."""
    return [scan_repo(s) for s in sources]
