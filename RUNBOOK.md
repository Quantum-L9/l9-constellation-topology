# Operator Runbook

## Purpose

Run, validate, inspect, replay, and diagnose the topology compiler without bypassing packet, evidence, or output boundaries.

## Prerequisites

- Python 3.12
- `uv` 0.10.0 recommended
- read access to validated Repository Model Packet bundles
- write access only to the selected output root
- signing and callback credentials only for stage-worker execution

## Bootstrap

```bash
python -m pip install uv==0.10.0
uv sync --frozen --extra dev
```

## Local compile

```bash
uv run l9-topology compile-packet \
  --repo-root . \
  --input-bundle tests/fixtures/repository_model_packets/l9-gate-sdk \
  --input-bundle tests/fixtures/repository_model_packets/l9-mcp-server \
  --out outputs/local-run
```

The command exits non-zero if packet loading, parent receipt verification, topology validation, output planning, or commit fails.

## Dry run

```bash
uv run l9-topology compile-packet \
  --repo-root . \
  --input-bundle tests/fixtures/repository_model_packets/l9-gate-sdk \
  --out outputs/dry-run \
  --dry-run
```

Dry-run emits a write plan and receipt while performing no filesystem mutation.

## Validate an existing bundle

```bash
uv run l9-topology validate-packet --input-bundle outputs/local-run
```

Rerun cross-packet validation against the exact parents:

```bash
uv run l9-topology validate-packet \
  --input-bundle outputs/local-run \
  --repository-bundle tests/fixtures/repository_model_packets/l9-gate-sdk \
  --repository-bundle tests/fixtures/repository_model_packets/l9-mcp-server
```

A valid bundle requires matching packet, payload, manifest, and Validation Receipt hashes with `status=passed`.

## Render projections

```bash
uv run l9-topology render-report \
  --repo-root . \
  --input-bundle outputs/local-run \
  --out outputs/local-reports
```

Reports are cacheable projections. They are never compiler-stage inputs.

## Inspect and impact

```bash
uv run l9-topology inspect-packet --input-bundle outputs/local-run
uv run l9-topology impact \
  --input-bundle outputs/local-run \
  --entity repo:l9-gate-sdk \
  --direction downstream \
  --maximum-depth 5
```

## Build a signed control packet

Prepare a typed payload JSON, then:

```bash
export L9_DISPATCH_HMAC_KEY='runtime-secret'
export L9_DISPATCH_HMAC_KEY_ID='foundational-hmac-v1'

uv run l9-topology-control-packet \
  --payload-file stage-dispatch-payload.json \
  --packet-type command \
  --action compile-topology \
  --trace-id trace:example \
  --correlation-id run:example \
  --workflow-id foundational-repository-intelligence \
  --out signed-stage-dispatch.json
```

## Worker preflight

Use trusted worker code to authenticate the dispatch before using its target revision:

```bash
L9_DISPATCH_HMAC_KEY='runtime-secret' \
uv run l9-topology-worker \
  --dispatch-file signed-stage-dispatch.json \
  --repo-root . \
  --workspace outputs/preflight \
  --preflight
```

The output contains only validated control metadata. A non-object revision, invalid signature, forbidden repository, bad profile, missing callback, or failed parent status blocks before checkout.

## Execute a local worker stage

The dispatch must reference local `file://` parent bundles and a local output URI.

```bash
export L9_DISPATCH_HMAC_KEY='runtime-secret'
export L9_PACKET_REGISTRY_FILE='outputs/worker/packet-registry.sqlite3'

uv run l9-topology-worker \
  --dispatch-file signed-stage-dispatch.json \
  --repo-root . \
  --workspace outputs/worker
```

## Generated artifact drift

Detect schema and fixture drift without modifying tracked files:

```bash
make generated-check
```

The command exits non-zero and reports each missing or stale generated artifact. It covers checked-in JSON Schemas and the deterministic Repository Model Packet fixtures.

When drift is intentional, regenerate the narrowest affected surface:

```bash
make schemas-update
make fixtures-update
# or both
make generated-update
```

Then review the diff before proceeding:

```bash
git status --short
git diff -- contracts schemas tests/fixtures/repository_model_packets
make generated-check
make validate
```

Do not accept unexplained generated changes. If output changes unexpectedly, stop and inspect the canonical model, generator inputs, dependency lock, and runtime version.

Before committing, synchronize repository evidence:

```bash
# Update MANIFEST.md and FINAL_TREE.md for added or removed paths.
# Refresh traceability and validation records for the new drift gate.
git add -A
PYTHONPATH=src python scripts/git_tree_manifest.py
git add GIT_TREE_MANIFEST.json
PYTHONPATH=src python scripts/validate_git_integrity.py
```

The Git tree manifest must be generated from the final staged tree. Any later tracked-file edit invalidates it.

## Release-readiness validation

Run the repository completeness and no-stub gate before publishing changes:

```bash
uv run python scripts/validate_release_readiness.py
```

The gate rejects executable pass statements, ellipsis-only function bodies, unfinished implementation markers, missing release artifacts, and drift between the repository and `MANIFEST.md`. Necessary package markers and typed entrypoint wrappers are classified explicitly rather than treated as implementation gaps.

## Failure classes

| Class | Retry | Operator action |
|---|---:|---|
| generated artifact missing or stale | no | inspect source change, run the explicit update target, review the diff, and rerun validation |
| packet download timeout | yes | verify store availability |
| packet publication timeout | yes | verify registry and ORAS/GHCR availability |
| callback timeout | yes | allow control-plane reconciliation or retry |
| invalid schema, signature, hash, or object ID | no | replace the dispatch or parent packet |
| failed parent validation | no | repair upstream stage |
| unsupported contract version | no | add a versioned adapter |
| topology invariant failure | no | inspect the Validation Receipt |
| output collision or expected-hash mismatch | no | review write policy and destination |

## Recovery law

A stage is not successful until its bundle is committed, published, reloaded, hash-verified, accompanied by a passed Validation Receipt, and acknowledged by the control plane. A published packet with a failed callback must be reconciled by idempotency key rather than republished blindly.

See [docs/recovery.md](docs/recovery.md) and [docs/deployment.md](docs/deployment.md).

## Commit-bound integrity validation

Run after staging every intended file, including dot-directories:

```bash
git add -A
PYTHONPATH=src python scripts/git_tree_manifest.py
git add GIT_TREE_MANIFEST.json
git commit -m "your bounded change"
PYTHONPATH=src python scripts/validate_git_integrity.py
```

`MANIFEST.md` is the human responsibility inventory. `GIT_TREE_MANIFEST.json` records every other tracked entry's Git mode, object type, and blob ID. The check fails when either inventory differs from `git ls-tree HEAD`, any recorded blob identity changes, or the worktree is dirty. CI emits the exact commit SHA, tree SHA, and both manifest digests.

## Callback policy

Dispatch packets use an approved `callback_id`. Configure destinations and credentials only through variables referenced by `.l9/callback-policy.yaml`. Production entries must bind exact hosts and ports, use segment-bound path prefixes, and reject encoded slash or backslash ambiguity. The checked-in production entry is disabled until an approved hostname is committed. Never add packet-selected URLs or secret variable names.

## Publication verification

Production OCI publication uses a semantic-hash-derived staging tag and accepts only the returned `@sha256:<digest>` reference. Verification independently resolves the registry descriptor, then checks the retrieved bundle against the exact expected packet and manifest identities.
