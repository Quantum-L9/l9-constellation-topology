# GMP-129

**Task:** Remediate l9-constellation-topology issues #36 #27 #37 #32
**Tier:** RUNTIME

## TODOs

- T1:  REPLACE #36: replace `uv sync --frozen --no-build --no-dev --no-editable` with a locked deps sync (--no-install-project) followed by `uv pip install --no-deps .` in ingress, manual-replay and both stage-worker environments; every `uv pip install` names its target interpreter with --python so the stage-worker UV_PROJECT_ENVIRONMENT envs are hit, not .venv
- T2:  REPLACE #37: `uv run --no-sync` on every l9-pr-validate step, wheel smoke-install into a lock-synced env with --no-deps plus `uv pip check`, `npm ci --ignore-scripts` in compile.yml; follow the --no-deps wheel install with `uv pip check` so a dependency missing from the wheel metadata still fails the smoke
- T3:  REPLACE #27: drop the pull_request branches filter on l9-pr-validate; gate direct-compile-smoke to non-PR events or PRs into main
- T4:  REPLACE Guard T1-T3 in scripts/validate_workflows.py and add mutation tests in tests/test_workflow_contracts_v5.py; reuse the existing _clone_workflow_tree harness, one mutation test per guard
- T5:  REPLACE #32: render the stored UnknownRecord.reason once; update the renderer test to assert no doubled prefix; tests assert the stored sentence appears exactly once and the doubled backtick prefix is absent (assertion strengthened, not removed); compiler and unknown_id unchanged so determinism and lineage hold
- T6:  REPLACE CHANGELOG entry and GIT_TREE_MANIFEST.json regeneration
