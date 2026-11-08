# GMP-129 — Remediate issues #36, #27, #37 (partial), #32

**Tier:** RUNTIME · **Base:** `origin/main` `9b431e5` · **Branch:** `claude/l9-issue-remediation-git3ig`
**Plan:** `/l9-plan-build` pipeline (PLAN_DOCUMENT, section receipt and kernel receipt PASS; plan artifacts are local under the gitignored `.cursor/plans/`).

## Phase 0 — scope lock

| TODO | Change | Files |
|---|---|---|
| T1 (#36) | Locked deps sync with `--no-build --no-install-project`, then `uv pip install --no-deps --python <env> .` | `l9-ingress.yml`, `l9-manual-replay.yml`, `l9-stage-worker.yml` |
| T2 (#37) | `uv run --no-sync` on every validation step; wheel smoke into a lock-synced env with `--no-deps` + `uv pip check`; `npm ci --ignore-scripts` | `l9-pr-validate.yml`, `compile.yml` |
| T3 (#27) | `pull_request` without a branch filter; `direct-compile-smoke` limited to PRs into `main` | `l9-pr-validate.yml` |
| T4 | One guard per change in the workflow contract validator, one mutation test per guard | `scripts/validate_workflows.py`, `tests/test_workflow_contracts_v5.py` |
| T5 (#32) | Renderer emits the stored not-run sentence once | `renderers/markdown_report.py`, `tests/test_corpus_topology_compilation.py` |
| T6 | Changelog, tree manifest | `CHANGELOG.md`, `GIT_TREE_MANIFEST.json` |

Out of scope: `tests/fixtures/**`, `evidence/**`, CLI path-taint findings, SonarCloud settings, the uv pin.

## Phase 1 — baseline (evidence)

- #36: run 128268498189 on `9b431e5`, step `uv sync --frozen --no-build --no-dev --no-editable`: `Distribution l9-constellation-topology==2.0.0 @ editable+. can't be installed because it is marked as --no-build`. Reproduced locally with uv 0.10.0 on a `git archive` of `9b431e5`.
- #27: `l9-pr-validate.yml` declared `pull_request: branches: [main]`.
- #37: SonarCloud `api/issues/search inNewCodePeriod=true`: 33 open VULNERABILITY; quality gate `new_security_rating` 3 (C).
- #32: rendered line was ``Corpus analysis domain `x` was not run: Corpus analysis domain 'x' was not run: <reason>``.

## Phase 4 — validation (evidence)

| Check | Result |
|---|---|
| uv 0.10.0 replay of each new install sequence on `git archive HEAD` | pass: config import, `l9-topology-control-packet`, `l9-topology-worker`, `l9-topology` entry points; `uv pip check`: all installed packages compatible |
| `scripts/validate_workflows.py` | passed |
| `tests/test_workflow_contracts_v5.py` | 16 passed (7 new mutation tests) |
| `tests/test_corpus_topology_compilation.py` | 57 passed; the two not-run tests fail against the previous renderer |
| `make check` (compile, lint, type) | pass |
| `make` contracts, workflows, architecture, generated-check | pass |
| `make` git-integrity, determinism | pass |
| release readiness on a clean export of HEAD | passed, 0 blocking findings |
| Full `pytest` suite (`make test`) | NOT RUN in session (governance reserves it for CI); runs in `l9-pr-validate` |

## Residual

- #37 is partial. Still open: `tests/fixtures/sample_constellation/l9-gate-sdk/.github/workflows/ci.yml` (S8541, S8544), CLI path/argument taint in `scripts/git_tree_manifest.py`, `scripts/validate_git_integrity.py`, `worker/control_packet.py`, `worker/stage_runner.py` (S8705, S8707), and `evidence/live-qualify-2026-08-02/` (Dockerfile S8541, `odoo.conf` S2068 credential). Owner decisions.
- Whether SonarCloud clears the workflow findings is observable only after merge to `main`.
- The direct-compile drill (F001) still runs only for PRs into `main`, merge queue or dispatch, by design.
