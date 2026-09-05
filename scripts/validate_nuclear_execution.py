#!/usr/bin/env python3
"""Validate the archived v4 machine summary without promoting it to v5 authority."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = ("status", "milestones", "contract_id", "generated_at")
VALID_STATUSES = {"complete", "partial", "blocked"}
REQUIRED_MILESTONES = tuple(f"M{i}" for i in range(1, 9))
VALID_MILESTONE_STATES = {"complete", "partial", "blocked", "not_started"}


def validate(path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    # S8707: validate path is a real file to guard against LLM-supplied traversal
    resolved = path.resolve()
    if not resolved.is_file():
        return False, [f"Not a file: {resolved}"]
    try:
        data: dict[str, Any] = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"Invalid JSON: {exc}"]
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing: {field}")
    status = data.get("status", "")
    if status not in VALID_STATUSES:
        errors.append(f"Invalid status: {status}")
    milestones = data.get("milestones", {})
    if not isinstance(milestones, dict):
        errors.append("milestones must be an object")
        return False, errors
    for milestone_id in REQUIRED_MILESTONES:
        if milestone_id not in milestones:
            errors.append(f"Missing milestone: {milestone_id}")
            continue
        milestone = milestones[milestone_id]
        if not isinstance(milestone, dict):
            errors.append(f"{milestone_id} must be an object")
            continue
        if milestone.get("state", "") not in VALID_MILESTONE_STATES:
            errors.append(f"{milestone_id} invalid state")
        if not milestone.get("evidence", ""):
            errors.append(f"{milestone_id} no evidence - FAIL")
    return not errors, errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_nuclear_execution.py <machine-summary.json>")
        return 1
    ok, errors = validate(Path(sys.argv[1]))
    if ok:
        print("PASS")
        return 0
    print("FAIL")
    for error in errors:
        print(f"  ERROR: {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
