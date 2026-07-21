# Validation

## Executive decision

**Status: APPROVED_REMEDIATION_CANDIDATE_WITH_EXTERNAL_GATES**

The prior `APPROVED_INITIAL_COMMIT_WITH_EXTERNAL_UNKNOWNS` conclusion is superseded. Its evidence described a delivery tree containing `.github` and `.l9`, while the public commit omitted those directories. This remediation restores the complete repository surface, fixes every confirmed P0/P1/P2 audit finding, and adds commit-bound Git-tree validation.

Local validation supports a pull request and review. Production deployment remains blocked until the exact remediation commit passes canonical Python 3.12 CI and the external OCI/Postgres pipeline drills in `UNKNOWN_REGISTER.md`.

## Confirmed findings remediated

- Git-tree and validation-package divergence
- Incomplete semantic idempotency fingerprint
- Packet-selected callback destination and worker secret
- Publication verification not bound to the expected packet
- Lost upstream diagnostics
- Per-file rather than per-bundle atomic publication
- Concurrent local registry update loss
- Validation receipt ambiguity between model construction and independent schema evaluation

## Local executable checks

| Check | Status | Evidence summary |
|---|---|---|
| Python syntax compilation | PASS | `src`, `tests`, and `scripts` compile on Python 3.13.5 |
| Full test suite | PASS | 97 tests passed |
| Branch coverage | PASS | 81.66%, above the configured 80% floor |
| Contract and schema validation | PASS | 31 checked-in schemas passed |
| GitHub workflow contract validation | PASS | four workflows passed |
| Architecture boundary validation | PASS | 111 source files, zero violations |
| Release-readiness validation | PASS | 335 tracked delivery files, zero findings |
| Deterministic semantic identity | PASS | semantic and payload hashes stable; `sha256:b3c3194984b8b2a8d2e14cfe4830436cc5f5cb01e97dbde4b43918c226317101` |
| Frozen lock consistency | PASS | `uv lock --check --offline --python 3.13` |
| Wheel build | PASS | wheel built locally without build isolation |
| Installed package and CLI smoke | PASS | wheel imported and both console entry points resolved using the validated runtime dependency set |
| Ruff | BLOCKED | tool environment could not be materialized offline because a locked wheel was absent from cache |
| Strict mypy | BLOCKED | tool environment could not be materialized offline because a locked wheel was absent from cache |
| Canonical Python 3.12 | BLOCKED | interpreter unavailable locally and managed download unavailable offline |
| Live GitHub Actions, OCI, Postgres, and three-repository chain | BLOCKED | external credentials and services unavailable locally |

Detailed structured evidence is in `validation/validation_checks.jsonl` and `validation/validation_report.yaml`. CI additionally emits `validation/commit-bound-validation.json` for the exact commit under review.

## Commit-bound integrity rule

The authoritative release check is:

```bash
git add -A
PYTHONPATH=src python scripts/validate_git_integrity.py
```

It verifies:

- exact commit SHA and tree SHA;
- clean worktree;
- `MANIFEST.md` SHA-256;
- exact equality between manifest paths and `git ls-tree HEAD`.

A release claim without this evidence is invalid.

## Release decision

The repository is suitable for a remediation pull request. It is not approved for production deployment until the external gates are attached to the exact release commit.
