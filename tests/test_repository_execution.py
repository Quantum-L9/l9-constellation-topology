"""Core repository execution V2 contract (ADR-0032).

Central Core admits this repository only when `.l9/repo-workflow.json` is the
exact v2 declaration, the root Makefile is the byte-identical `make-v1` facade,
and `Repo.mk` implements the four phase leaves without redefining the facade's
own targets. These tests pin all three so a local edit cannot drift from what
Core verifies, and they prove the phases still run the whole former gate.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: sha256 of Quantum-L9/l9-ci-core `tools/l9_repo/facades/make-v1.mk`, which is
#: also the root Makefile of l9-ci-core, l9-meta-injector and Quantum-L9/.github.
MAKE_V1_FACADE_SHA256 = "59d75892d7c8af83916187c5af612d2c9697741a68017265059567e4ea33cba6"

PHASES = ("setup", "validate", "check", "test")
FACADE_OWNED_TARGETS = ("help", *PHASES)

#: Every step the former all-in-one `make validate` ran, by the command it ran.
FORMER_GATE_COMMANDS = (
    "python -m compileall src tests scripts -q",
    "pytest --cov=l9_constellation_topology",
    "ruff check .",
    "ruff format --check .",
    "mypy src/l9_constellation_topology",
    "scripts/validate_contracts.py",
    "scripts/validate_workflows.py",
    "scripts/architecture_boundary_check.py",
    "scripts/validate_release_readiness.py",
    "scripts/generate_schemas.py --check",
    "scripts/generate_fixture_packets.py --check",
    "scripts/evaluate_hash_locality.py --check",
    "scripts/validate_git_integrity.py",
    "scripts/verify_determinism.py",
    "uv build",
)


def test_contract_is_the_exact_v2_declaration() -> None:
    data = json.loads((ROOT / ".l9" / "repo-workflow.json").read_text(encoding="utf-8"))
    assert data == {
        "schema": "l9.repo-execution/v2",
        "facade": "make-v1",
        "required_phases": list(PHASES),
    }


def test_root_makefile_is_the_byte_identical_make_v1_facade() -> None:
    makefile = ROOT / "Makefile"
    assert makefile.is_file()
    assert not makefile.is_symlink()
    assert hashlib.sha256(makefile.read_bytes()).hexdigest() == MAKE_V1_FACADE_SHA256


def test_repo_mk_implements_every_leaf_and_none_of_the_facade_targets() -> None:
    text = (ROOT / "Repo.mk").read_text(encoding="utf-8")
    defined = set(re.findall(r"^([A-Za-z0-9_.-]+):(?!=)", text, flags=re.MULTILINE))
    phony = set(" ".join(re.findall(r"^\.PHONY:(.*)$", text, flags=re.MULTILINE)).split())
    for phase in PHASES:
        assert f"repo-{phase}" in defined
        assert f"repo-{phase}" in phony
    for reserved in FACADE_OWNED_TARGETS:
        assert reserved not in defined
        assert reserved not in phony


def test_core_runtime_staging_directory_is_ignored() -> None:
    assert ".l9/runtime/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_the_four_phases_together_run_the_whole_former_gate() -> None:
    # make is a hard dependency of the facade Core runs, so its absence fails
    # here rather than skipping.
    make = shutil.which("make")
    assert make is not None, "GNU make is required: the make-v1 facade is the execution entrypoint"
    planned: dict[str, str] = {}
    for phase in PHASES:
        result = subprocess.run(
            [make, "-n", "-C", str(ROOT), f"repo-{phase}"],
            check=True,
            capture_output=True,
            text=True,
        )
        planned[phase] = result.stdout
    combined = "\n".join(planned.values())
    for command in FORMER_GATE_COMMANDS:
        assert command in combined, command
    # Setup reproduces the PR validation workflow's environment exactly.
    assert "uv==0.10.0" in planned["setup"]
    assert "uv sync --frozen --no-build --extra dev --no-install-project" in planned["setup"]
    assert "uv pip install --no-deps --editable ." in planned["setup"]
    # git-integrity runs before build, while the tree it checks is still clean.
    assert planned["test"].index("validate_git_integrity.py") < planned["test"].index("uv build")
