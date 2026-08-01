#!/usr/bin/env python3
"""Validate immutable action pins and L9 workflow boundary invariants."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
EXPECTED = {
    "l9-pr-validate.yml",
    "l9-ingress.yml",
    "l9-stage-worker.yml",
    "l9-manual-replay.yml",
    "l9-analysis.yml",
}
PINNED_ACTION = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def _load(path: Path) -> dict[str, object]:
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(data, dict):
        raise ValueError(f"workflow is not a mapping: {path}")
    return data


def _steps(data: dict[str, object]) -> list[dict[str, str]]:
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        raise ValueError("workflow jobs must be a mapping")
    output: list[dict[str, str]] = []
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            continue
        for step in steps:
            if isinstance(step, dict):
                output.append({str(key): str(value) for key, value in step.items()})
    return output


def main() -> int:
    errors: list[str] = []
    actual = {path.name for path in WORKFLOW_ROOT.glob("*.yml")}
    missing = sorted(EXPECTED - actual)
    unexpected = sorted(actual - EXPECTED)
    if missing:
        errors.append(f"missing workflows: {', '.join(missing)}")
    if unexpected:
        errors.append(f"unexpected workflows: {', '.join(unexpected)}")

    loaded: dict[str, tuple[dict[str, object], list[dict[str, str]], str]] = {}
    for name in sorted(EXPECTED & actual):
        path = WORKFLOW_ROOT / name
        try:
            data = _load(path)
            steps = _steps(data)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"{name}: cannot parse workflow: {exc}")
            continue
        text = path.read_text(encoding="utf-8")
        loaded[name] = (data, steps, text)
        for step in steps:
            action = step.get("uses")
            if action is not None and not PINNED_ACTION.fullmatch(action):
                errors.append(f"{name}: action is not pinned to a full commit SHA: {action}")

    if "l9-pr-validate.yml" in loaded:
        _, _, text = loaded["l9-pr-validate.yml"]
        required = (
            "uv sync --frozen --extra dev",
            "--cov=l9_constellation_topology",
            "uv run ruff check .",
            "uv run mypy src/l9_constellation_topology",
            "scripts/validate_contracts.py",
            "scripts/validate_workflows.py",
            "scripts/architecture_boundary_check.py",
            "scripts/validate_release_readiness.py",
            "scripts/verify_determinism.py",
            "uv build",
        )
        for value in required:
            if value not in text:
                errors.append(f"l9-pr-validate.yml: missing gate {value}")

    if "l9-ingress.yml" in loaded:
        _, _, text = loaded["l9-ingress.yml"]
        for forbidden in ("compile-packet", "l9-topology-worker"):
            if forbidden in text:
                errors.append(f"l9-ingress.yml: ingress may not compile topology: {forbidden}")

    if "l9-stage-worker.yml" in loaded:
        _, steps, text = loaded["l9-stage-worker.yml"]
        names = [step.get("name", "") for step in steps]
        ordered = (
            "Checkout trusted worker authority",
            "Verify signature and resolve exact revision",
            "Checkout exact signed target revision",
            "Execute exact validated stage",
        )
        positions: list[int] = []
        for name in ordered:
            try:
                positions.append(names.index(name))
            except ValueError:
                errors.append(f"l9-stage-worker.yml: missing step {name}")
        if positions and positions != sorted(positions):
            errors.append("l9-stage-worker.yml: dispatch is used before authenticated preflight")
        for required in (
            "--preflight",
            "uv sync --frozen --no-dev --no-editable",
            "ref: ${{ steps.dispatch.outputs.revision }}",
        ):
            if required not in text:
                errors.append(f"l9-stage-worker.yml: missing exact-revision control {required}")

    result = {
        "status": "failed" if errors else "passed",
        "checked_workflows": sorted(actual),
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
