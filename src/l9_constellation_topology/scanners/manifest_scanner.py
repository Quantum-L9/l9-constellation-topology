"""Scan repo for language and package manager signals from manifest files."""

from __future__ import annotations

from pathlib import Path

from l9_constellation_topology.models import EvidenceItem, SourceType

_MANIFEST_MAP: list[tuple[str, str, str]] = [
    ("pyproject.toml", "Python", "uv/pip"),
    ("setup.py", "Python", "pip"),
    ("setup.cfg", "Python", "pip"),
    ("requirements.txt", "Python", "pip"),
    ("package.json", "TypeScript/JavaScript", "npm"),
    ("yarn.lock", "TypeScript/JavaScript", "yarn"),
    ("pnpm-lock.yaml", "TypeScript/JavaScript", "pnpm"),
    ("Cargo.toml", "Rust", "cargo"),
    ("go.mod", "Go", "go"),
    ("build.gradle", "Java/Kotlin", "gradle"),
    ("pom.xml", "Java", "maven"),
    ("Gemfile", "Ruby", "bundler"),
    ("composer.json", "PHP", "composer"),
]

_ENTRYPOINT_PATTERNS = [
    "main.py",
    "app.py",
    "server.py",
    "cli.py",
    "run.py",
    "__main__.py",
    "index.ts",
    "index.js",
    "main.ts",
    "server.ts",
]


def scan_manifests(
    repo_path: Path, repo_id: str
) -> tuple[list[str], list[str], list[str], list[EvidenceItem]]:
    """Return (languages, package_managers, entrypoints, evidence)."""
    languages: list[str] = []
    package_managers: list[str] = []
    entrypoints: list[str] = []
    evidence: list[EvidenceItem] = []

    for filename, lang, pm in _MANIFEST_MAP:
        matches = list(repo_path.rglob(filename))
        for m in matches:
            rel = str(m.relative_to(repo_path))
            if lang not in languages:
                languages.append(lang)
            if pm not in package_managers:
                package_managers.append(pm)
            evidence.append(
                EvidenceItem(
                    source_file=rel,
                    source_type=SourceType.file,
                    excerpt=f"manifest:{filename}",
                )
            )

    for ep_name in _ENTRYPOINT_PATTERNS:
        matches = list(repo_path.rglob(ep_name))
        for m in matches:
            rel = str(m.relative_to(repo_path))
            entrypoints.append(rel)
            evidence.append(
                EvidenceItem(
                    source_file=rel,
                    source_type=SourceType.file,
                    excerpt=f"entrypoint:{ep_name}",
                )
            )

    return languages, package_managers, entrypoints, evidence
