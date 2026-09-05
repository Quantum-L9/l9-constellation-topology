"""Shared read-only drift detection and explicit update support for generated files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    """One deterministic generated file and its expected bytes."""

    path: Path
    content: bytes


@dataclass(frozen=True, slots=True)
class DriftFinding:
    """A generated file that is missing or differs from its expected bytes."""

    kind: Literal["missing", "stale"]
    path: Path


def find_drift(artifacts: tuple[GeneratedArtifact, ...]) -> tuple[DriftFinding, ...]:
    """Return deterministic drift findings without mutating the filesystem."""

    seen: set[Path] = set()
    findings: list[DriftFinding] = []
    for artifact in artifacts:
        if artifact.path in seen:
            raise ValueError(f"duplicate generated artifact path: {artifact.path}")
        seen.add(artifact.path)
        if not artifact.path.exists():
            findings.append(DriftFinding(kind="missing", path=artifact.path))
        elif artifact.path.read_bytes() != artifact.content:
            findings.append(DriftFinding(kind="stale", path=artifact.path))
    return tuple(findings)


def synchronize(
    artifacts: tuple[GeneratedArtifact, ...],
    *,
    check: bool,
) -> tuple[DriftFinding, ...]:
    """Check generated files, or explicitly update only missing and stale files."""

    findings = find_drift(artifacts)
    if check:
        return findings

    artifacts_by_path = {artifact.path: artifact for artifact in artifacts}
    for finding in findings:
        artifact = artifacts_by_path[finding.path]
        artifact.path.parent.mkdir(parents=True, exist_ok=True)
        artifact.path.write_bytes(artifact.content)
    # Return the artifacts this call wrote. A post-write re-scan is empty on
    # success and drops the written list that update commands report.
    return findings
