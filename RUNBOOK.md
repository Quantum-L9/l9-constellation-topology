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
export L9_PACKET_REGISTRY_FILE='outputs/worker/packet-registry.json'

uv run l9-topology-worker \
  --dispatch-file signed-stage-dispatch.json \
  --repo-root . \
  --workspace outputs/worker
```

## Release-readiness validation

Run the repository completeness and no-stub gate before publishing changes:

```bash
uv run python scripts/validate_release_readiness.py
```

The gate rejects executable pass statements, ellipsis-only function bodies, unfinished implementation markers, missing release artifacts, and drift between the repository and `MANIFEST.md`. Necessary package markers and typed entrypoint wrappers are classified explicitly rather than treated as implementation gaps.

## Failure classes

| Class | Retry | Operator action |
|---|---:|---|
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
