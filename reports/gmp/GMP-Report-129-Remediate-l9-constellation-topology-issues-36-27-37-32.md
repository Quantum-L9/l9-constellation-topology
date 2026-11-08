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

## Follow-up in the same GMP (operator decisions, 2026-11-08)

- `evidence/`: left byte-exact (credential included, operator decision) and taken out of SonarQube Cloud analysis by `.sonarcloud.properties`, which lists source directories because automatic analysis allows no wildcard patterns.
- `tests/` is analysed as test code. Whether that clears the two findings in `tests/fixtures/sample_constellation/l9-gate-sdk/.github/workflows/ci.yml` is observable only after the main-branch re-analysis.
- `--treeish` (S8705) now resolves through `git rev-parse --verify --end-of-options`, and a value starting with `-` is refused. `--out` (S8707) must resolve inside the repository root. Both are covered by tests in `tests/test_git_integrity.py`.

## Residual

- `worker/control_packet.py` `--payload-file` and `worker/stage_runner.py` `--dispatch-file` (S8707) read operator-named input files, which is their contract. In the workflows these are `ingress-payload.json` in the checkout and `/tmp/l9-stage-dispatch.json`. Not changed.
- SonarCloud reads `.sonarcloud.properties` and re-rates `main` only after merge.
- The direct-compile drill (F001) still runs only for PRs into `main`, merge queue or dispatch, by design.
