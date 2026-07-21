"""Tests for maturity scoring."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample_constellation"


from l9_constellation_topology.models import Confidence, EvidenceItem, RepoCard, SourceType
from l9_constellation_topology.topology.maturity import score_repo


def _full_card() -> RepoCard:
    return RepoCard(
        repo_id="full-repo",
        name="full-repo",
        path="/fake/full-repo",
        primary_role="service",
        package_managers=["pip"],
        ci_workflows=[".github/workflows/ci.yml"],
        adr_files=["docs/adr/adr-001.md"],
        governance_files=["CODEOWNERS"],
        upstream_dependencies=["pydantic"],
        evidence=[
            EvidenceItem(source_file="README.md", source_type=SourceType.file, excerpt="readme")
        ],
        confidence=Confidence.high,
    )


def test_full_card_scores_high():
    ms = score_repo(_full_card())
    assert ms.score >= 70
    assert ms.band in ("mature", "exemplary")


def test_empty_card_scores_nascent():
    card = RepoCard(
        repo_id="empty",
        name="empty",
        path="/fake/empty",
        confidence=Confidence.low,
    )
    ms = score_repo(card)
    assert ms.band == "nascent"
    assert ms.score < 40


def test_score_breakdown_keys_present():
    ms = score_repo(_full_card())
    expected_keys = {
        "has_package_manifest",
        "has_ci_workflow",
        "has_adr",
        "has_governance",
        "has_readme",
        "has_dependencies",
        "high_confidence",
    }
    assert expected_keys.issubset(ms.breakdown.keys())


def test_gate_sdk_fixture_scores_emerging_or_better():
    from l9_constellation_topology.models import RepoSource
    from l9_constellation_topology.scanners.repo_scanner import scan_repo

    source = RepoSource(
        repo_id="l9-gate-sdk",
        name="l9-gate-sdk",
        local_path=str(FIXTURE / "l9-gate-sdk"),
    )
    card = scan_repo(source)
    ms = score_repo(card)
    assert ms.band in ("emerging", "mature", "exemplary")
