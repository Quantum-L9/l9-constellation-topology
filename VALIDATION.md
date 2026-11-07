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
| GitHub workflow contract validation | PASS | five workflows passed |
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

Checked-in JSON Schemas, packet fixtures, and the hash-locality evaluation are derived
outputs. `scripts/generated_artifact_sync.py` provides read-only drift detection
(`find_drift`) and explicit mutation (`synchronize`) so validation never rewrites the
worktree.

```bash
make schemas-check          # read-only: fail on missing/stale checked-in schemas
make fixtures-check         # read-only: fail on missing/stale fixture packets
make hash-locality          # read-only: fail on drifted identity-locality evidence
make generated-check        # all of the above
make schemas-update         # explicit regeneration
make fixtures-update        # explicit regeneration
make hash-locality-update   # explicit regeneration
```

- The `validate` phase (`make validate`) includes `generated-check` and fails on any
  generated drift. The full gate is `make setup validate check test` (ADR-0032).
- `fixtures-check` is gate-eligible. Fixture generation pins `created_at` to a fixed
  instant and derives `source_revision` from the sample tree's own content hash rather
  than from this repository's live `HEAD`, so regeneration is byte-for-byte reproducible
  at any commit. Both injected inputs are volatile rather than semantic: every semantic
  hash strips timestamps, so pinning them changes emitted bytes only. The golden Topology
  Packet bundle is generated from the Repository Model fixtures for the same reason, so a
  change in compiler meaning appears as a reviewable fixture diff instead of a
  hand-edited packet drifting from the code.
- `hash-locality` regenerates `HASH_LOCALITY_EVALUATION.json` and fails when recorded
  identity locality drifts. `tests/test_hash_locality.py` additionally asserts the
  expected verdict of every case, so regeneration cannot bless a wrong answer.
- `tests/test_generated_artifact_sync.py` covers missing, stale, explicit-update, and
  duplicate-destination (fail-closed) behavior of the drift helper.

## Repository metadata

`.l9/metadata-index.jsonl` is generated by `l9-meta-injector` (ADR-0031) and is
outside the validation ladder: no `make` target or CI job checks it, by
operator decision, so the full gate passing says nothing about its
freshness. Its own drift check is `l9-meta-injector check` with the flags in
`DEVELOPMENT.md`, which reported `drift=0` on the commit that added it.
`GIT_TREE_MANIFEST.json` is omitted from the index, so the commit-bound
integrity model above is unaffected.

## Claim read model and qualified impact

This section separates what the code on `main` does from the status of the
decisions behind it. A merged change is implemented; it is not thereby frozen
or admitted.

| Item | Status |
|---|---|
| Claim read model, `query-claims`, pagination, categorized differential (ADR-0034 and its amendment) | Implemented. Freeze candidate `L9-SEMANTIC-LEVERAGE-FREEZE/1.0` decision D2. |
| Claim-level projection eligibility; policy 1.4.0 hash binding (ADR-0035) | Implemented. Freeze candidate decision D5a and invariant F12. |
| Resolution-aware dependency impact (ADR-0035) | Implemented as an opt-in mode. Freeze candidate decision D5b. |
| Freeze candidate `L9-SEMANTIC-LEVERAGE-FREEZE/1.0` as a whole | Architecture-converged, authority-resolution-pending. Not formally frozen. |
| 13 producer-managed header predicates (`meta.managed.*`, policy 1.3.0+) | Implemented on `main`. Semantically compatible subject to field-level review. **Not formally admitted** by a domain authority (freeze decision D3 is held). |
| Semantic Foundation v3.27.0 admission (`l9.artifact-header-model/global@1`, bound `admission: candidate`) | **Unresolved.** Producer-local managed meanings confer no Foundation authority. |
| Subject identity for packages and document titles (freeze decision D4) | Held; not implemented. |

Two further distinctions hold everywhere:

- **Derived records versus admitted topology.** Every record these commands
  return is a derived Topology record compiled from source declarations. None
  is an admitted product topology record, and this repository admits none.
- **Reachability versus dependency impact.** `impact` answers generic
  reachability; `impact --resolution-aware` answers qualified dependency
  impact. They are different questions and stay distinguishable: the
  resolution-aware output carries `"interpretation":
  "resolution-aware-dependency-impact"`, and the default output stays the
  bare `ImpactIndex` with no such key. The label is presentation only; it is
  not in `ImpactIndex`, the stored `impact_indexes` or the packet identity.

Behavioral evidence: `tests/test_claim_view.py`,
`tests/test_qualified_projection.py` and `tests/test_header_predicates.py`.
Generated artifacts are covered by the existing drift guard: `make
generated-check` reads the `foundational-two-repo` golden and
`HASH_LOCALITY_EVALUATION.json`, which move only in the predicate policy hash
and its derived identities. The run of record for each change is the
`validate` CI job on its pull request head; this section records no result of
its own.

## Evidence-qualified relation publication

| Item | Status |
|---|---|
| Graph builder stops promoting artifact classification to `GOVERNED_BY` / `DOCUMENTED_BY` / `VALIDATED_BY` (ADR-0037) | Pending owner decision. Canonical Topology Packet identity change; retained edge identities pinned in `tests/test_topology_graph_v5.py`. |
| `qualify_relation` and publication policy 2.0.0 (`strict`, `selective`) (ADR-0036) | Pending owner decision. Implemented on its pull request; activation requires a repository-owner decision because the version bump re-keys every retained effect (ADR-0025) and current downstream durable state is Unknown. |

Behavioral evidence: `tests/test_publication_qualification.py` compares plans
built under the checked-in policy and under
`tests/fixtures/publication_policies/legacy-v1` from identical pinned packets.
The legacy policy reproduces the pre-ADR-0036 plan byte for byte; the Topology
Packet is unchanged under both. `HASH_LOCALITY_EVALUATION.json` keeps every
verdict and moves only its candidate counts and policy identity. This section
records no result of its own.

## Direct compile seam

`.github/workflows/compile.yml` is authorized by ADR-0029 as a bounded, stateless compile
seam. ADR-0016 Model B remains the durable scheduler, retry/lease owner, and packet-registry
authority; the seam carries none of that state.

Proven locally:

| Check | Status | Evidence summary |
|---|---|---|
| Workflow contract, five workflows | PASS | `scripts/validate_workflows.py` exits 0 |
| Exact `uses` pin enforcement | PASS | a quoted comment-suffixed pin is rejected; reintroducing the strip makes the validator report `passed` and the regression test fail |
| Compile job holds no package authority | PASS | adding `packages:` to the compile job is rejected by the contract gate |
| Publication gated on `inputs.publish` | PASS | removing the condition is rejected by the contract gate |
| ADR-0018 acceptance drill, every control | PASS | `tests/test_oci_acceptance_drill_v5.py` executes the drill source extracted from `compile.yml` against a fake registry; removing the expected-registry-digest control makes both tests fail |

Captured from GitHub Actions run `35451617285`:

| Check | Status | Evidence |
|---|---|---|
| `l9-pr-validate / validate` | PASS | job `105919650979` executed environment sync, compile, tests with coverage, format, lint, typing, contracts, workflow validation, architecture, readiness, commit-bound integrity, determinism, build, and wheel smoke |
| `direct-compile-smoke / compile` | PASS | job `105919651169` |
| `direct-compile-smoke / publish` | FAIL, then repaired | job `105919770043` reported `FAIL valid-object substitution: acceptance did not fail closed`. Root cause and repair below. |

### The substitution control's first real execution failed

The drill's negative control did not discriminate. `accept()` compared the
independently resolved descriptor against the reference's own digest — internal
consistency — and then compared packet id, semantic hash, and bundle manifest
digest. It never compared the reference against the digest publication actually
returned. The substitute carries the same `manifest.json` plus one extra file,
so every one of those checks matched and a different registry object was
accepted.

This is the same omission ADR-0018 and finding F001 name: reproducing part of
the canonical acceptance contract rather than all of it.
`worker/packet_store.py::verify_published` binds
`expected_registry_manifest_digest`; the seam did not. That binding is now
present, and `tests/test_oci_acceptance_drill_v5.py` executes the real drill
source so the control cannot regress unobserved again.

Still not provable locally — requires a GitHub Actions run with GHCR credentials:

| Check | Status | What would discharge it |
|---|---|---|
| ADR-0018 acceptance drill against a real registry | UNKNOWN | A `direct-compile-smoke` run on the repaired seam in which every control reports PASS |
| `publish: false` permission boundary | UNKNOWN | A run with `publish: false` whose job log shows no `Packages: write` grant |

No deployment or publication success is claimed from the workflow source or from
the fake-registry tests alone.

## Release decision

The repository is suitable for an updated remediation pull request and architect re-review.
It is not approved for production deployment until the external gates are attached to the exact
release commit.
