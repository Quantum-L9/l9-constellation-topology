#!/usr/bin/env python3
"""Validate immutable action pins and L9 workflow boundary invariants."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
# Workflow name constants (S1192: avoid duplicating literals)
_WF_PR_VALIDATE = "l9-pr-validate.yml"
_WF_INGRESS = "l9-ingress.yml"
_WF_STAGE_WORKER = "l9-stage-worker.yml"
_WF_MANUAL_REPLAY = "l9-manual-replay.yml"
_WF_COMPILE = "compile.yml"

# Every workflow here is repository-owned. Organization L9 CI (Semgrep analysis,
# SDK admission, governed publication) is executed by the GitHub organization
# required-workflow ruleset from Quantum-L9/l9-ci-core main
# .github/workflows/org-ci.yml. The consumer selects neither a Core nor an SDK
# revision, so no copied caller may reappear here.
EXPECTED = {
    _WF_PR_VALIDATE,
    _WF_INGRESS,
    _WF_STAGE_WORKER,
    _WF_MANUAL_REPLAY,
    _WF_COMPILE,
}
PINNED_ACTION = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
# Consumer-owned organization CI ownership markers. Any of these in a workflow means
# the repository is again selecting a Core or SDK revision for organization CI.
ORG_CI_OWNERSHIP_MARKERS = (
    "Quantum-L9/l9-ci-core",
    "Quantum-L9/l9-ci-sdk",
    "L9_CORE_REF",
    "L9_SDK_REF",
)


def _load(path: Path) -> dict[str, object]:
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(data, dict):
        raise ValueError(f"workflow is not a mapping: {path}")
    return data


def _check_org_ci_ownership(name: str, text: str) -> list[str]:
    """Reject consumer-owned organization CI (Core/SDK revision selection).

    Organization L9 CI is centrally enforced from ``Quantum-L9/l9-ci-core`` ``main``
    ``.github/workflows/org-ci.yml`` by the GitHub organization ruleset. A workflow
    that pins or references Core or the SDK re-creates the consumer-owned revision
    the migration removed, so it fails the contract regardless of its filename.
    """

    return [
        f"{name}: consumer-owned organization CI reference is forbidden: {marker}"
        for marker in ORG_CI_OWNERSHIP_MARKERS
        if marker in text
    ]


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
        errors.extend(_check_org_ci_ownership(name, text))
        for step in steps:
            action = step.get("uses")
            if action is not None and not PINNED_ACTION.fullmatch(action.split(" #", 1)[0]):
                errors.append(f"{name}: action is not pinned to a full commit SHA: {action}")

    if _WF_PR_VALIDATE in loaded:
        _, _, text = loaded[_WF_PR_VALIDATE]
        required = (
            "uv sync --frozen --no-build --extra dev",
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
            "uv sync --frozen --no-build --no-dev --no-editable",
            "ref: ${{ steps.dispatch.outputs.revision }}",
        ):
            if required not in text:
                errors.append(f"{_WF_STAGE_WORKER}: missing exact-revision control {required}")

    if _WF_COMPILE in loaded:
        _, _, text = loaded[_WF_COMPILE]
        required = (
            "workflow_call:",
            "default: v4",
            "source_revision must be an exact 40-character commit SHA",
            "repository-model-cli.js",
            "compile-packet",
            "validate-packet",
            "verify-determinism",
            "docker buildx build",
            "packet_oci_ref",
            "docker pull",
        )
        for value in required:
            if value not in text:
                errors.append(f"{_WF_COMPILE}: missing direct-compile control {value}")

    result = {
        "status": "failed" if errors else "passed",
        "checked_workflows": sorted(actual),
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
