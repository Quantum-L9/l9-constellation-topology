"""Scan repo for CI workflow files."""

from __future__ import annotations

from pathlib import Path

from l9_constellation_topology.models import EvidenceItem, SourceType

_CI_DIRS = [".github/workflows", ".gitlab-ci.yml", ".circleci", ".drone.yml", "Jenkinsfile"]


def scan_ci(repo_path: Path, repo_id: str) -> tuple[list[str], list[EvidenceItem]]:
    """Return (ci_workflow_paths, evidence)."""
    ci_workflows: list[str] = []
    evidence: list[EvidenceItem] = []

    gh_workflows = repo_path / ".github" / "workflows"
    if gh_workflows.is_dir():
        for wf in gh_workflows.rglob("*.yml"):
            rel = str(wf.relative_to(repo_path))
            ci_workflows.append(rel)
            evidence.append(
                EvidenceItem(
                    source_file=rel,
                    source_type=SourceType.file,
                    excerpt=f"github_action:{wf.name}",
                )
            )
        for wf in gh_workflows.rglob("*.yaml"):
            rel = str(wf.relative_to(repo_path))
            ci_workflows.append(rel)
            evidence.append(
                EvidenceItem(
                    source_file=rel,
                    source_type=SourceType.file,
                    excerpt=f"github_action:{wf.name}",
                )
            )

    for ci_file in [".gitlab-ci.yml", ".circleci/config.yml", "Jenkinsfile", ".drone.yml"]:
        p = repo_path / ci_file
        if p.exists():
            ci_workflows.append(ci_file)
            evidence.append(
                EvidenceItem(
                    source_file=ci_file,
                    source_type=SourceType.file,
                    excerpt=f"ci_file:{ci_file}",
                )
            )

    return ci_workflows, evidence
