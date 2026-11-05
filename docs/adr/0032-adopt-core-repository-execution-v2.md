# ADR-0032: Adopt Core repository execution V2 through the make-v1 facade

**Status:** Accepted (operator decision, 2026-11-05: unblock PRs held by `Analyze (central Core)`)

- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology` build entrypoint (`Makefile`, `Repo.mk`, `.l9/repo-workflow.json`)
- **Relates to:** l9-meta-injector ADR-083 and Quantum-L9/.github #206 (the same adoption in sibling repositories)

## Context

The organization-required check `Analyze (central Core)` runs `Quantum-L9/l9-ci-core` `org-ci.yml` on every pull request. Core lists this repository under `required_repositories` (`run-repository-verification/contract-policy.json`), so repository verification runs in **required** mode. Without a contract it fails: `repository verification: FAIL (contract; required mode and .l9/repo-workflow.json absent)`. That has blocked every pull request here, including #39 (issue #40).

In required mode Core admits only the V2 contract (`tools/l9_repo/contract.py`):

- `.l9/repo-workflow.json` must have exactly three keys: `schema` `l9.repo-execution/v2`, `facade` `make-v1`, and `required_phases` `[setup, validate, check, test]`.
- The root `Makefile` must be byte-identical to `tools/l9_repo/facades/make-v1.mk` (sha256 `59d75892d7c8af83916187c5af612d2c9697741a68017265059567e4ea33cba6`).
- `Repo.mk` must declare `repo-setup`, `repo-validate`, `repo-check` and `repo-test` as phony targets with recipes, and must not define `help`, `setup`, `validate`, `check` or `test`.

Core then **executes** `make setup`, `make validate`, `make check` and `make test` on `ubuntu-24.04` with Python 3.12 and no uv, under a 30-minute job limit. It stops at the first failure. Before that, it stages its SDK and evidence under `.l9/runtime/`.

The former root Makefile defined `test` (plain pytest) and an all-in-one `validate` gate. Both names now belong to the facade.

## Decision

1. **Contract.** Add `.l9/repo-workflow.json`, byte-identical to l9-meta-injector's.
2. **Facade.** The root `Makefile` becomes the unmodified `make-v1` facade, regenerated only by Core's reconcile command.
3. **Implementation.** `Repo.mk` holds every former target unchanged, except that `test` is renamed `unit` and the all-in-one `validate` is removed. It adds the four leaves:
   - `repo-setup` installs `uv==0.10.0` unless `$(UV)` already reports exactly that version, fails closed if it still does not, then runs `uv sync --frozen --no-build --extra dev --no-install-project` and `uv pip install --no-deps --editable .`. This is exactly the environment `.github/workflows/l9-pr-validate.yml` builds, which Core's runner can reproduce.
   - `repo-validate` runs contracts, workflows, architecture, readiness and generated-check (schemas, fixtures, hash-locality).
   - `repo-check` runs compile, lint (`ruff check` and `ruff format --check`) and type.
   - `repo-test` runs coverage, git-integrity, determinism and build. git-integrity runs before build, while the tree is still clean.

   Together the four phases are exactly the command set the former `make validate` ran, so the full local gate is now `make setup validate check test`.
4. **Runtime staging.** `.l9/runtime/` is gitignored. Core writes there before verification, and git-integrity requires a clean tree. `scripts/validate_release_readiness.py` also excludes it, because Core stages its SDK source and venv there before `make validate` and the scan would otherwise report them as blocking findings. Nothing else in `.l9/` changes status.

5. **Core's Semgrep gate.** Once repository verification passes, Core's SDK technical gate blocks on Semgrep findings. Its one blocking finding here, `AST-ROUTING-004` (raw `/execute` bypassing GateClient), is in `evidence/live-qualify-2026-08-02/run_gate_qualify.py`. That file is a sealed evidence harness: it is never packaged or run by CI, and it posts to Gate itself as the external originator. It carries an inline `nosemgrep: gateclient-bypass-execute` with that rationale instead of being rewritten, because rewriting it would break the provenance of the evidence it produced.

## Consequences

- `Analyze (central Core)` repository verification can pass here, which unblocks every pull request held by it, including #39.
- `make validate` now means the validate phase, not the whole gate, and `make test` means the test phase, not plain pytest (`make unit`). The five operating documents and `CONTRIBUTING.md` say so.
- The Makefile is no longer edited by hand. A change to an execution step goes in `Repo.mk`.
- CI is unchanged: `l9-pr-validate.yml` never invoked `make` and keeps running its own steps.

## Alternatives considered

- **Keep the former Makefile and add only the contract.** Rejected: Core verification requires the byte-identical facade and fails on drift.
- **Map all four phases to the former all-in-one gate.** Rejected: it would run the full gate four times inside one 30-minute job, and it would make the phases meaningless.
- **Wait for Core to place this repository in migration mode.** Rejected: required mode is Core's policy, not this repository's, and it holds every pull request now.

## Compliance and validation

- `tests/test_repository_execution.py` checks:
  - the exact contract;
  - the facade's sha256;
  - that `Repo.mk` declares the four phony leaves and defines none of the facade-owned targets;
  - the `.l9/runtime/` ignore rule (with `tests/test_release_readiness.py` proving the readiness scan skips it while still scanning delivered `.l9/` files);
  - through `make -n`, that the four phases together run every command of the former gate, with git-integrity before build.
- Core's own validator (`tools.l9_repo.contract.RepositoryExecution(root).validate()` at l9-ci-core `c16cc32`) passes on this tree.
- With Core's pinned Semgrep 1.171.0, the `nosemgrep` annotation suppresses the `/execute` finding on the harness, including under the path-prefixed check id Core's staged ruleset produces. Without it the finding fires.
- Remote `Analyze (central Core)` on this pull request is the authoritative proof that the phases run green on Core's runner. A local pass is not that proof.

## Related artifacts

- `.l9/repo-workflow.json`, `Makefile`, `Repo.mk`, `.gitignore`
- `tests/test_repository_execution.py`
- `scripts/validate_release_readiness.py`, `tests/test_release_readiness.py`
- `evidence/live-qualify-2026-08-02/run_gate_qualify.py`
- `Quantum-L9/l9-ci-core` `.github/actions/run-repository-verification/`, `tools/l9_repo/contract.py`, `tools/l9_repo/facades/make-v1.mk`
- Issue #40
