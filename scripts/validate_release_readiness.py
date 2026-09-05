#!/usr/bin/env python3
"""Validate repository completeness, no-stub policy, and release documentation."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ROOT_FILES = {
    "THREAT_MODEL.md",
    "SUPPORT.md",
    "ROADMAP.md",
    "RELEASING.md",
    "NOTICE.md",
    "MAINTAINERS.md",
    "LICENSE",
    "INITIAL_COMMIT.md",
    "GOVERNANCE.md",
    "GIT_TREE_MANIFEST.json",
    "DEVELOPMENT.md",
    "DEPENDENCY_POLICY.md",
    "CODE_OF_CONDUCT.md",
    "BUILD_SPECIFICATION.md",
    "ARCHITECTURE.md",
    "ADR_INDEX.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "CHANGE_SUMMARY.md",
    "CONTRIBUTING.md",
    "CONVERGENCE_REPORT.yaml",
    "FINAL_TREE.md",
    "FIX_MAP.md",
    "MANIFEST.md",
    "README.md",
    "REGRESSION_GUARD.md",
    "RUNBOOK.md",
    "SECURITY.md",
    "SPECIFICATION.md",
    "STUB_TODO_THIN_FILE_AUDIT.md",
    "ALIGNMENT_AUDIT.md",
    "TRACEABILITY_MAP.yaml",
    "UNKNOWN_REGISTER.md",
    "VALIDATION.md",
}
SCAN_ROOTS = (
    ROOT / "src",
    ROOT / "tests",
    ROOT / "scripts",
    ROOT / ".github",
    ROOT / ".l9",
    ROOT / "config",
    ROOT / "contracts",
    ROOT / "schemas",
    ROOT / "docs",
)
ROOT_DOC_SCAN_FILES = (
    "THREAT_MODEL.md",
    "SUPPORT.md",
    "ROADMAP.md",
    "RELEASING.md",
    "NOTICE.md",
    "MAINTAINERS.md",
    "INITIAL_COMMIT.md",
    "GOVERNANCE.md",
    "GIT_TREE_MANIFEST.json",
    "DEVELOPMENT.md",
    "DEPENDENCY_POLICY.md",
    "CODE_OF_CONDUCT.md",
    "BUILD_SPECIFICATION.md",
    "ARCHITECTURE.md",
    "ADR_INDEX.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "README.md",
    "RUNBOOK.md",
    "SECURITY.md",
    "SPECIFICATION.md",
)
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".wheel-smoke",
    "__pycache__",
    "build",
    "dist",
}
#: Repository-relative prefixes holding agent runtime state rather than
#: delivered files: L4 local-autonomy phase and release receipts, the PR
#: remediation handoff, and the agent adapter wiring the governance sessionStart
#: bootstrap writes into the worktree. They are written by the governance flow,
#: are git-ignored, and are never part of the delivery inventory, so a readiness
#: scan must not report them as manifest omissions.
EXCLUDED_RELATIVE_PREFIXES = (
    ".claude/",
    ".l9/autonomy/",
    ".l9/pr/",
)
#: Repository-relative files in the same category as the prefixes above. A whole
#: directory is not the right unit for the MCP server map, which is one file.
EXCLUDED_RELATIVE_FILES = frozenset({".mcp.json"})
ALLOWED_THIN_NAMES = {"__init__.py", "py.typed", ".gitkeep"}


def _is_excluded(path: Path) -> bool:
    if any(part in EXCLUDED_PARTS or part.endswith(".egg-info") for part in path.parts):
        return True
    relative = path.relative_to(ROOT).as_posix()
    if relative in EXCLUDED_RELATIVE_FILES:
        return True
    return relative.startswith(EXCLUDED_RELATIVE_PREFIXES)


THIN_FILE_EXEMPTIONS = {
    "src/l9_constellation_topology/models.py": "legacy compatibility re-export surface",
    "src/l9_constellation_topology/stages/resolve_config.py": "typed stage adapter",
    "scripts/build_control_packet.py": "console-script wrapper",
}
MARKER_RE = re.compile(
    r"\b(?:TODO|FIXME|XXX|HACK|placeholder|stub|scaffold)\b|not\s+implemented",
    re.IGNORECASE,
)
MARKER_EXEMPTIONS = {
    "scripts/validate_release_readiness.py": ("no-stub policy", "MARKER_RE ="),
    # Fixture input, not project source. The marker on this line is the thing the
    # repository-model producer observes to emit `http.handler_body_marker`, and
    # the compiler's contract is that observing it never becomes a verdict about
    # the handler. Removing the marker would remove the coverage that proves it.
    # Owner: the assertion-activation fixture; remove when that predicate is no
    # longer part of the interpretation profile.
    "tests/fixtures/semantic_assertion_repository/engine/main.py": ("route to the engine handler",),
    ".github/workflows/l9-pr-validate.yml": ("no-stub policy",),
    "CHANGELOG.md": ("no-stub", "placeholder bodies"),
    "RUNBOOK.md": ("no-stub gate",),
}
MANIFEST_ENTRY_RE = re.compile(r"^- `([^`]+)`\s+—\s+[^\r\n]+")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int | None
    finding_type: str
    severity: str
    evidence: str
    required_fix: str


def _repository_files() -> set[str]:
    files: set[str] = set()
    for path in ROOT.rglob("*"):
        if not path.is_file() or _is_excluded(path):
            continue
        if path.name in {".coverage", "coverage.xml"}:
            continue
        files.add(path.relative_to(ROOT).as_posix())
    return files


def _manifest_paths() -> set[str]:
    path = ROOT / "MANIFEST.md"
    if not path.is_file():
        return set()
    paths: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = MANIFEST_ENTRY_RE.match(line)
        if match:
            paths.add(match.group(1))
    return paths


def _scan_python(path: Path) -> list[Finding]:
    relative = path.relative_to(ROOT).as_posix()
    findings: list[Finding] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    except SyntaxError as exc:
        return [
            Finding(
                path=relative,
                line=exc.lineno,
                finding_type="syntax_error",
                severity="critical",
                evidence=str(exc),
                required_fix="Repair the Python syntax error.",
            )
        ]

    for node in ast.walk(tree):
        if isinstance(node, ast.Pass):
            findings.append(
                Finding(
                    path=relative,
                    line=node.lineno,
                    finding_type="pass_statement",
                    severity="major",
                    evidence="Executable pass statement found.",
                    required_fix="Implement explicit behavior or remove the dead branch.",
                )
            )
        elif isinstance(node, ast.Raise):
            call = node.exc
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "NotImplementedError"
            ):
                findings.append(
                    Finding(
                        path=relative,
                        line=node.lineno,
                        finding_type="not_implemented",
                        severity="critical",
                        evidence="NotImplementedError found in executable code.",
                        required_fix="Provide complete behavior or remove the unsupported path.",
                    )
                )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (
                len(body) == 1
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and body[0].value.value is Ellipsis
            ):
                findings.append(
                    Finding(
                        path=relative,
                        line=node.lineno,
                        finding_type="ellipsis_body",
                        severity="major",
                        evidence=f"Function {node.name} has an ellipsis-only body.",
                        required_fix="Use an explicit fail-closed contract body or implementation.",
                    )
                )
    return findings


def _scan_markers(path: Path) -> list[Finding]:
    relative = path.relative_to(ROOT).as_posix()
    findings: list[Finding] = []
    if relative == "scripts/validate_release_readiness.py":
        return findings
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return findings
    for line_number, line in enumerate(lines, 1):
        exemptions = MARKER_EXEMPTIONS.get(relative, ())
        if any(exemption in line for exemption in exemptions):
            continue
        if MARKER_RE.search(line):
            findings.append(
                Finding(
                    path=relative,
                    line=line_number,
                    finding_type="unfinished_marker",
                    severity="major",
                    evidence=line.strip()[:240],
                    required_fix=(
                        "Resolve the marker or record a structured Unknown outside "
                        "executable scope."
                    ),
                )
            )
    return findings


def _scan_thin_python(path: Path) -> list[Finding]:
    relative = path.relative_to(ROOT).as_posix()
    if path.name in ALLOWED_THIN_NAMES or relative in THIN_FILE_EXEMPTIONS:
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    substantive = [
        line
        for line in lines
        if line.strip() and not line.lstrip().startswith("#") and not line.strip().startswith('"""')
    ]
    if len(substantive) > 4:
        return []
    return [
        Finding(
            path=relative,
            line=None,
            finding_type="thin_file",
            severity="minor",
            evidence=f"Only {len(substantive)} substantive lines.",
            required_fix=(
                "Confirm the file is a necessary entrypoint or merge it into its owner module."
            ),
        )
    ]


def collect_findings() -> list[Finding]:
    findings: list[Finding] = []
    for scan_root in SCAN_ROOTS:
        if not scan_root.exists():
            findings.append(
                Finding(
                    path=scan_root.relative_to(ROOT).as_posix(),
                    line=None,
                    finding_type="missing_scan_root",
                    severity="critical",
                    evidence="Required repository area is missing.",
                    required_fix="Restore the required repository area.",
                )
            )
            continue
        for path in sorted(scan_root.rglob("*")):
            if not path.is_file() or _is_excluded(path):
                continue
            if path.is_relative_to(ROOT / "docs" / "archive"):
                continue
            if path.suffix == ".py":
                findings.extend(_scan_python(path))
                findings.extend(_scan_thin_python(path))
            if path.suffix in {".py", ".yml", ".yaml", ".toml"}:
                findings.extend(_scan_markers(path))

    for name in ROOT_DOC_SCAN_FILES:
        path = ROOT / name
        if path.is_file():
            findings.extend(_scan_markers(path))

    present_root_files = {path.name for path in ROOT.iterdir() if path.is_file()}
    missing_root_files = sorted(REQUIRED_ROOT_FILES - present_root_files)
    for name in missing_root_files:
        findings.append(
            Finding(
                path=name,
                line=None,
                finding_type="missing_release_artifact",
                severity="major",
                evidence="Required release-readiness artifact is absent.",
                required_fix=f"Create {name} with evidence-backed content.",
            )
        )

    actual_files = _repository_files()
    manifest_files = _manifest_paths()
    for path in sorted(actual_files - manifest_files):
        findings.append(
            Finding(
                path=path,
                line=None,
                finding_type="manifest_omission",
                severity="major",
                evidence="File exists but is absent from MANIFEST.md.",
                required_fix="Add the file and its responsibility to MANIFEST.md.",
            )
        )
    for path in sorted(manifest_files - actual_files):
        findings.append(
            Finding(
                path=path,
                line=None,
                finding_type="stale_manifest_entry",
                severity="major",
                evidence="MANIFEST.md references a file that does not exist.",
                required_fix="Remove or correct the stale manifest entry.",
            )
        )
    return findings


def main() -> int:
    findings = collect_findings()
    blocking = [finding for finding in findings if finding.severity in {"critical", "major"}]
    result = {
        "status": "failed" if blocking else "passed",
        "checked_file_count": len(_repository_files()),
        "finding_count": len(findings),
        "blocking_finding_count": len(blocking),
        "thin_file_exemptions": THIN_FILE_EXEMPTIONS,
        "findings": [asdict(finding) for finding in findings],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
