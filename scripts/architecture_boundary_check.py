#!/usr/bin/env python3
"""Enforce packet, effect, and destination boundaries from the v5 specification."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/l9_constellation_topology"
ALLOWED_WRITE_PREFIX = SOURCE / "io"
FORBIDDEN_IMPORT_ROOTS = {"neo4j", "graphiti"}
FORBIDDEN_PATH_MUTATION_ATTRIBUTES = {"write_text", "write_bytes", "rename", "unlink"}


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def inspect_file(path: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    relative = path.relative_to(ROOT).as_posix()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    findings.append(
                        {
                            "path": relative,
                            "line": node.lineno,
                            "rule": "no-direct-graph-client-import",
                            "detail": alias.name,
                        }
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".", 1)[0]
            if root in FORBIDDEN_IMPORT_ROOTS:
                findings.append(
                    {
                        "path": relative,
                        "line": node.lineno,
                        "rule": "no-direct-graph-client-import",
                        "detail": node.module,
                    }
                )
        elif isinstance(node, ast.Name) and node.id == "PacketEnvelope":
            findings.append(
                {
                    "path": relative,
                    "line": node.lineno,
                    "rule": "packet-envelope-forbidden",
                    "detail": node.id,
                }
            )
        elif isinstance(node, ast.Call) and not _is_under(path, ALLOWED_WRITE_PREFIX):
            if isinstance(node.func, ast.Attribute):
                base_name = node.func.value.id if isinstance(node.func.value, ast.Name) else None
                forbidden = (
                    node.func.attr in FORBIDDEN_PATH_MUTATION_ATTRIBUTES
                    or (base_name == "os" and node.func.attr in {"replace", "rename", "remove"})
                    or (base_name == "shutil" and node.func.attr == "rmtree")
                )
                if forbidden:
                    findings.append(
                        {
                            "path": relative,
                            "line": node.lineno,
                            "rule": "writes-only-through-io",
                            "detail": (
                                f"{base_name}.{node.func.attr}" if base_name else node.func.attr
                            ),
                        }
                    )
            elif isinstance(node.func, ast.Name) and node.func.id == "open":
                mode = None
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                for keyword in node.keywords:
                    if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                        mode = keyword.value.value
                if isinstance(mode, str) and any(marker in mode for marker in ("w", "a", "x", "+")):
                    findings.append(
                        {
                            "path": relative,
                            "line": node.lineno,
                            "rule": "writes-only-through-io",
                            "detail": f"open mode={mode}",
                        }
                    )
    return findings


def main() -> int:
    findings = [finding for path in sorted(SOURCE.rglob("*.py")) for finding in inspect_file(path)]
    result = {
        "status": "passed" if not findings else "failed",
        "checked_files": len(tuple(SOURCE.rglob("*.py"))),
        "findings": findings,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
