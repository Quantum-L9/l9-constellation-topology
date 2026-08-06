# Validation

## Executive decision

**Status: APPROVED_PR1_REVIEW_FIX_CANDIDATE_WITH_EXTERNAL_GATES**

The earlier remediation candidate closed the original release-integrity, semantic-reuse,
callback-trust, publication-identity, diagnostics, atomicity, registry, and validation-layer
findings. The PR #1 architect review identified two additional merge blockers:

1. callback path allowlisting used a string prefix rather than a segment boundary; and
2. release integrity proved tracked-path equality but did not bind committed file content.

This review-fix pass closes both blockers. It also adds low-risk production hardening for
callback host and port policy, unique OCI staging targets, and independent registry descriptor
resolution. The packet-native architecture and public compiler contracts remain intact.

Local validation supports updating PR #1 and requesting re-review. Production deployment
remains blocked until the exact PR commit passes canonical Python 3.12 CI and the external
OCI/Postgres acceptance drills in `UNKNOWN_REGISTER.md`.

## Review findings closed

- Callback paths now require an exact allowed path or a descendant path separated by `/`.
- Encoded slash and backslash ambiguity is rejected before any callback request.
- Callback policy can bind an exact hostname set and port; the production entry is disabled
  until an approved hostname is committed.
- `GIT_TREE_MANIFEST.json` records Git mode, object type, and blob ID for every tracked entry
  except itself, avoiding self-reference while binding the rest of the tree exactly.
- `scripts/validate_git_integrity.py` verifies the human inventory and the Git-native content
  manifest against the exact committed tree.
- OCI publication uses a semantic-hash-derived staging tag, returns only a digest-qualified
  authority reference, and independently resolves the registry descriptor before acceptance.

## Local executable checks

| Check | Status | Evidence summary |
|---|---|---|
| Python syntax compilation | PASS | `src`, `tests`, and `scripts` compile on Python 3.13.5 |
| Full test suite | PASS | 112 tests passed |
| Branch coverage | PASS | 81.62%, above the configured 80% floor |
| Contract and schema validation | PASS | 31 checked-in schemas passed |
| GitHub workflow contract validation | PASS | four workflows passed |
| Architecture boundary validation | PASS | 111 production source files, zero violations |
| Release-readiness validation | PASS | 338 tracked delivery files, zero findings |
| Callback boundary regression | PASS | exact and descendant paths allowed; sibling-prefix and encoded-separator paths rejected |
| Git content-integrity regression | PASS | path, mode, object type, and blob substitutions are detected |
| OCI publication regression | PASS | unique staging target and independent descriptor mismatch rejection passed |
| Deterministic semantic identity | PASS | semantic and payload hashes stable; `sha256:b3c3194984b8b2a8d2e14cfe4830436cc5f5cb01e97dbde4b43918c226317101` |
| Frozen lock consistency | PASS | `uv lock --check --offline --python 3.13` |
| Wheel build | PASS | wheel built locally without build isolation |
| Installed package and CLI smoke | PASS | wheel imported and both primary console entry points resolved using the validated runtime dependency set |
| Ruff | BLOCKED | frozen tool environment could not be materialized from the available offline cache |
| Strict mypy | BLOCKED | frozen tool environment could not be materialized from the available offline cache |
| Canonical Python 3.12 | BLOCKED | interpreter unavailable locally and managed download unavailable offline |
| Live GitHub Actions, OCI, Postgres, and three-repository chain | BLOCKED | external credentials and services unavailable locally |

Detailed structured evidence is in `validation/validation_checks.jsonl` and
`validation/validation_report.yaml`.

## Commit-bound integrity model

The repository contains two complementary manifests:

- `MANIFEST.md` is the human-readable tracked-file inventory and responsibility map.
- `GIT_TREE_MANIFEST.json` is the machine-readable content manifest. It records the path,
  mode, object type, and Git object ID of every tracked entry except itself.

Generation and validation are intentionally separate:

```bash
git add -A
PYTHONPATH=src python scripts/git_tree_manifest.py
git add GIT_TREE_MANIFEST.json
git commit -m "fix: close architect review blockers"
PYTHONPATH=src python scripts/validate_git_integrity.py \
  --out /tmp/commit-bound-validation.json
```

The final command verifies:

- exact commit SHA and root tree SHA;
- clean worktree;
- human inventory paths equal committed paths;
- Git-native manifest paths, modes, object types, and blob IDs equal the committed tree;
- deterministic manifest-entry digest.

`GIT_TREE_MANIFEST.json` excludes itself because a file cannot contain its own final Git blob
ID. CI produces the exact commit-bound report as a workflow artifact. A release claim without
that report is invalid.

## Generated-artifact drift guard

Checked-in JSON Schemas and Repository Model Packet fixtures are derived outputs.
`scripts/generated_artifact_sync.py` provides read-only drift detection (`find_drift`)
and explicit mutation (`synchronize`) so validation never rewrites the worktree.

```bash
make schemas-check     # read-only: fail on missing/stale checked-in schemas
make fixtures-check     # read-only: fail on missing/stale fixture packets
make generated-check    # both of the above
make schemas-update     # explicit regeneration
make fixtures-update    # explicit regeneration
```

- `make validate` includes `schemas-check` (deterministic) and fails on schema drift.
- `fixtures-check` is retained as an on-demand diagnostic and is intentionally excluded
  from `make validate`: fixture packets embed a wall-clock `created_at` and the live
  repository revision as `source_revision`, so a byte-for-byte regeneration check cannot
  pass in steady state. It becomes gate-eligible once fixture generation is made
  deterministic (recorded as a follow-up in `ROADMAP.md`).
- `tests/test_generated_artifact_sync.py` covers missing, stale, explicit-update, and
  duplicate-destination (fail-closed) behavior of the drift helper.

## Release decision

The repository is suitable for an updated remediation pull request and architect re-review.
It is not approved for production deployment until the external gates are attached to the exact
release commit.
