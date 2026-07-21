from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_initial_root_authority_files_exist() -> None:
    required = {
        ".editorconfig",
        ".gitattributes",
        "ADR_INDEX.md",
        "ARCHITECTURE.md",
        "BUILD_SPECIFICATION.md",
        "CODE_OF_CONDUCT.md",
        "DEPENDENCY_POLICY.md",
        "DEVELOPMENT.md",
        "GOVERNANCE.md",
        "INITIAL_COMMIT.md",
        "LICENSE",
        "MAINTAINERS.md",
        "Makefile",
        "NOTICE.md",
        "RELEASING.md",
        "ROADMAP.md",
        "SUPPORT.md",
        "THREAT_MODEL.md",
    }
    present = {path.name for path in ROOT.iterdir() if path.is_file()}
    assert required <= present


def test_twenty_initial_adrs_are_complete_and_indexed() -> None:
    adr_dir = ROOT / "docs" / "adr"
    adr_paths = sorted(path for path in adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md"))
    assert len(adr_paths) == 20
    index = (ROOT / "ADR_INDEX.md").read_text(encoding="utf-8")
    required_sections = (
        "## Context",
        "## Decision",
        "## Consequences",
        "## Alternatives considered",
        "## Compliance and validation",
        "## Related artifacts",
    )
    for path in adr_paths:
        text = path.read_text(encoding="utf-8")
        assert "**Status:** Accepted" in text
        assert all(section in text for section in required_sections)
        assert f"docs/adr/{path.name}" in index


def test_build_spec_preserves_source_lineage_and_core_laws() -> None:
    text = (ROOT / "BUILD_SPECIFICATION.md").read_text(encoding="utf-8")
    assert "bbca641a0380f66c10dc83ff5be86669d3c94172" in text
    assert "evidence over inference; packets over reports; planned effects over direct writes" in text
    assert "## 34. Convergence and stop conditions" in text


def test_github_issue_templates_are_valid_yaml() -> None:
    template_dir = ROOT / ".github" / "ISSUE_TEMPLATE"
    for path in sorted(template_dir.glob("*.yml")):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(value, dict)
