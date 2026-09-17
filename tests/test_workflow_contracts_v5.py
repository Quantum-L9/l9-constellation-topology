from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_workflows.py"
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
_PINNED_USES = re.compile(r"^(?P<indent>\s*)uses: (?P<ref>\S+@[0-9a-f]{40})\s*(?:#.*)?$")


def _run(validator: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(validator)],
        cwd=validator.parent.parent,
        check=False,
        capture_output=True,
        text=True,
    )


def _clone_workflow_tree(destination: Path) -> Path:
    """Reproduce the real validator and workflow tree under a writable root."""

    scripts = destination / "scripts"
    workflows = destination / ".github" / "workflows"
    scripts.mkdir(parents=True)
    workflows.mkdir(parents=True)
    shutil.copy2(VALIDATOR, scripts / VALIDATOR.name)
    for workflow in WORKFLOW_ROOT.glob("*.yml"):
        shutil.copy2(workflow, workflows / workflow.name)
    return scripts / VALIDATOR.name


def _quote_first_pin_with_comment_suffix(workflow: Path) -> str:
    """Turn the first pinned ``uses`` into a quoted comment-suffixed scalar.

    A YAML comment after an unquoted value is removed by the parser. Quoting the
    value keeps ``# v4.2.2`` inside the loaded scalar, which is exactly the
    malformed action reference GitHub would refuse to resolve.
    """

    lines = workflow.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        match = _PINNED_USES.match(line.rstrip("\n"))
        if match is None:
            continue
        malformed = f"{match['ref']} # v4.2.2"
        lines[index] = f'{match["indent"]}uses: "{malformed}"\n'
        workflow.write_text("".join(lines), encoding="utf-8")
        return malformed
    raise AssertionError(f"no pinned uses reference found in {workflow}")


def test_github_workflow_contracts_pass() -> None:
    completed = _run(VALIDATOR)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_cloned_workflow_tree_is_a_faithful_positive_control(tmp_path: Path) -> None:
    validator = _clone_workflow_tree(tmp_path)
    completed = _run(validator)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_quoted_comment_suffixed_uses_is_rejected(tmp_path: Path) -> None:
    validator = _clone_workflow_tree(tmp_path)
    target = validator.parent.parent / ".github" / "workflows" / "l9-pr-validate.yml"
    malformed = _quote_first_pin_with_comment_suffix(target)

    completed = _run(validator)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "failed"
    assert any(
        error == f"l9-pr-validate.yml: action is not pinned to a full commit SHA: {malformed}"
        for error in result["errors"]
    ), result["errors"]
