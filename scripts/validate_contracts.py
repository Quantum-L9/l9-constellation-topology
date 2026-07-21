#!/usr/bin/env python3
"""Validate checked-in JSON Schemas and representative packet fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    checked: list[str] = []
    for path in sorted((ROOT / "contracts").glob("*.json")) + sorted(
        (ROOT / "schemas").glob("*.json")
    ):
        try:
            schema = load(path)
            Draft202012Validator.check_schema(schema)
            if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                errors.append(f"{path.relative_to(ROOT)}: wrong or missing $schema")
            if not schema.get("$id"):
                errors.append(f"{path.relative_to(ROOT)}: missing $id")
            checked.append(path.relative_to(ROOT).as_posix())
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")

    repository_schema = load(ROOT / "contracts/repository-model-packet.schema.json")
    for name in ("l9-gate-sdk", "l9-mcp-server"):
        fixture = load(ROOT / "tests/fixtures/repository_model_packets" / name / "packet.json")
        failures = sorted(
            Draft202012Validator(repository_schema).iter_errors(fixture),
            key=lambda error: tuple(error.path),
        )
        errors.extend(
            f"repository fixture {name} at {list(error.path)}: {error.message}"
            for error in failures
        )

    result = {
        "status": "passed" if not errors else "failed",
        "checked_schema_count": len(checked),
        "checked_schemas": checked,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
