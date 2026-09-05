#!/usr/bin/env python3
"""Validate immutable action pins and L9 workflow boundary invariants."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
GOVERNANCE_ROOT = ROOT / ".github" / "governance"
# Workflow name constants (S1192: avoid duplicating literals)
_WF_ANALYSIS = "l9-analysis.yml"
_WF_PR_VALIDATE = "l9-pr-validate.yml"
_WF_INGRESS = "l9-ingress.yml"
_WF_STAGE_WORKER = "l9-stage-worker.yml"
_WF_MANUAL_REPLAY = "l9-manual-replay.yml"

EXPECTED = {
    _WF_PR_VALIDATE,
    _WF_INGRESS,
    _WF_STAGE_WORKER,
    _WF_MANUAL_REPLAY,
    _WF_ANALYSIS,
}
PINNED_ACTION = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def _load(path: Path) -> dict[str, object]:
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(data, dict):
        raise ValueError(f"workflow is not a mapping: {path}")
    return data


def _trigger_events(data: dict[str, object]) -> list[str]:
    # YAML 1.1 can fold the `on` key to boolean True; BaseLoader keeps it as the string
    # "on". Accept either so the trigger set is discovered regardless of loader behavior.
    triggers = data.get("on")
    if triggers is None:
        triggers = data.get("True")
    if isinstance(triggers, str):
        return [triggers]
    if isinstance(triggers, dict):
        return sorted(str(key) for key in triggers)
    if isinstance(triggers, list):
        return sorted(str(item) for item in triggers)
    return []


def _check_analysis_profile_events(data: dict[str, object], text: str) -> list[str]:
    """Verify every trigger event maps to a profile that permits it (audit F-06 / R-06)."""

    errors: list[str] = []
    events = _trigger_events(data)
    if not events:
        return [f"{_WF_ANALYSIS}: cannot determine trigger events"]
    mapping = dict(re.findall(r"(\w+)\)\s+profile=(\w+)", text))
    try:
        profiles_doc = yaml.safe_load(
            (GOVERNANCE_ROOT / "execution-profiles.yaml").read_text(encoding="utf-8")
        )
        profiles = profiles_doc["profiles"]
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        return [f"{_WF_ANALYSIS}: cannot load execution profiles: {exc}"]
    for event in events:
        selected = mapping.get(event)
        if selected is None:
            errors.append(f"{_WF_ANALYSIS}: no governed profile is selected for event {event}")
            continue
        profile = profiles.get(selected)
        if not isinstance(profile, dict):
            errors.append(f"{_WF_ANALYSIS}: selected profile is undefined: {selected}")
            continue
        if event not in profile.get("allowed_events", []):
            errors.append(f"{_WF_ANALYSIS}: profile {selected} does not permit event {event}")
    return errors


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

    if _WF_PR_VALIDATE in loaded:
        _, _, text = loaded[_WF_PR_VALIDATE]
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
                errors.append(f"{_WF_PR_VALIDATE}: missing gate {value}")

    if _WF_INGRESS in loaded:
        _, _, text = loaded[_WF_INGRESS]
        for forbidden in ("compile-packet", "l9-topology-worker"):
            if forbidden in text:
                errors.append(f"{_WF_INGRESS}: ingress may not compile topology: {forbidden}")

    if _WF_STAGE_WORKER in loaded:
        _, steps, text = loaded[_WF_STAGE_WORKER]
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
                errors.append(f"{_WF_STAGE_WORKER}: missing step {name}")
        if positions and positions != sorted(positions):
            errors.append(f"{_WF_STAGE_WORKER}: dispatch is used before authenticated preflight")
        for required in (
            "--preflight",
            "uv sync --frozen --no-dev --no-editable",
            "ref: ${{ steps.dispatch.outputs.revision }}",
        ):
            if required not in text:
                errors.append(f"{_WF_STAGE_WORKER}: missing exact-revision control {required}")

    if _WF_ANALYSIS in loaded:
        data, _, text = loaded[_WF_ANALYSIS]
        errors.extend(_check_analysis_profile_events(data, text))

    result = {
        "status": "failed" if errors else "passed",
        "checked_workflows": sorted(actual),
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
