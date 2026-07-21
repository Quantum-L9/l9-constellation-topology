"""Scan repo for declared upstream dependencies."""

from __future__ import annotations

import re
from pathlib import Path

from l9_constellation_topology.models import EvidenceItem, SourceType


def scan_dependencies(repo_path: Path, repo_id: str) -> tuple[list[str], list[EvidenceItem]]:
    """Return (upstream_dependency_names, evidence) from manifest files."""
    deps: list[str] = []
    evidence: list[EvidenceItem] = []

    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8")
        in_deps = False
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if re.match(r"^\[project\]", stripped):
                in_deps = False
            if re.match(r"^dependencies\s*=", stripped):
                in_deps = True
                continue
            if in_deps:
                if stripped.startswith("[") or stripped == "":
                    in_deps = False
                    continue
                name_match = re.match(r'^["\']?([A-Za-z0-9_\-\.]+)', stripped.strip("\"[] ',"))
                if name_match:
                    dep_name = name_match.group(1).strip().lower()
                    if dep_name and dep_name not in deps:
                        deps.append(dep_name)
                        evidence.append(
                            EvidenceItem(
                                source_file="pyproject.toml",
                                source_type=SourceType.file,
                                excerpt=f"dep:{dep_name}",
                                line_number=i,
                            )
                        )

    req_txt = repo_path / "requirements.txt"
    if req_txt.exists():
        for i, line in enumerate(req_txt.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if line and not line.startswith("#"):
                name_match = re.match(r"^([A-Za-z0-9_\-\.]+)", line)
                if name_match:
                    dep_name = name_match.group(1).lower()
                    if dep_name not in deps:
                        deps.append(dep_name)
                        evidence.append(
                            EvidenceItem(
                                source_file="requirements.txt",
                                source_type=SourceType.file,
                                excerpt=f"dep:{dep_name}",
                                line_number=i,
                            )
                        )

    package_json = repo_path / "package.json"
    if package_json.exists():
        import json

        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"{repo_id}: invalid package.json: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{repo_id}: package.json root must be an object")
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            declared = data.get(section, {})
            if not isinstance(declared, dict):
                raise ValueError(f"{repo_id}: package.json {section} must be an object")
            for dep_name in declared:
                if dep_name not in deps:
                    deps.append(dep_name)
                    evidence.append(
                        EvidenceItem(
                            source_file="package.json",
                            source_type=SourceType.file,
                            excerpt=f"dep:{dep_name}",
                        )
                    )

    return deps, evidence
