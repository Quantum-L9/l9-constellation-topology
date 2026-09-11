from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_workflows", ROOT / "scripts" / "validate_workflows.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workflow_discovery_is_extension_complete(tmp_path: Path) -> None:
    """A `.yaml` workflow must not be invisible to the contract validator."""

    validator = _load_validator()
    (tmp_path / "a.yml").write_text("name: a\n", encoding="utf-8")
    (tmp_path / "b.yaml").write_text("name: b\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("ignored\n", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "c.yml").write_text("name: c\n", encoding="utf-8")
    assert [path.name for path in validator.workflow_files(tmp_path)] == ["a.yml", "b.yaml"]


def test_consumer_owned_core_reference_is_rejected() -> None:
    validator = _load_validator()
    text = "jobs:\n  a:\n    uses: Quantum-L9/l9-ci-core/.github/workflows/x.yml@" + "0" * 40 + "\n"
    errors = validator._check_org_ci_ownership("probe.yaml", text)
    assert errors
    assert "Quantum-L9/l9-ci-core" in errors[0]
    assert validator._check_org_ci_ownership("clean.yml", "jobs: {}\n") == []


def test_uv_hardening_requires_pin_floor_and_frozen_no_build() -> None:
    validator = _load_validator()
    stale = "run: pip install uv==0.10.0\nrun: uv run pytest\n"
    errors = validator._check_uv_hardening("probe.yml", stale)
    assert any("predates first-party --no-build" in error for error in errors)
    assert any("`uv run` must pass --frozen --no-build" in error for error in errors)
    hardened = "run: pip install uv==0.12.10\nrun: uv run --frozen --no-build pytest\n"
    assert validator._check_uv_hardening("ok.yml", hardened) == []


def test_github_workflow_contracts_pass() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate_workflows.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
