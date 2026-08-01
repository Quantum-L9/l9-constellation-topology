# l9-constellation-topology

`l9-constellation-topology` is the packet-native middle-end compiler in the foundational L9 repository-intelligence pipeline.

```text
Source repositories
        ↓
l9-meta-injector
        ↓ validated Repository Model Packet(s)
l9-constellation-topology
        ↓ validated immutable Topology Packet
l9-topology-ingestion-bridge
        ↓ promotion plans, candidates, and publication receipts
```

The compiler aggregates artifact-level repository semantics into repository and constellation topology: capabilities, dependencies, governance, flows, impact, maturity, risk, conflicts, unknowns, and evidence lineage.

## Canonical boundaries

The repository **owns** topology compilation, fail-closed validation, deterministic packet construction, optional report projections, and the topology stage worker.

It **does not own** source metadata injection, Neo4j or Graphiti mutation, the Postgres control-plane schema, global promotion policy, or source-repository mutation.

Inter-stage communication uses versioned packets. Markdown, CSV, YAML, Mermaid, and graph exports are projections only.

## What was harvested

The v4 donor implementation supplied proven read-only scanners, canonical JSON and hash helpers, graph traversal, dependency analysis, maturity and risk rules, renderers, fixtures, and regression tests. Those parts were ported behind v5 adapters and pure domain boundaries.

The v4 `RepoCard -> report directory` transport, coarse trust model, timestamp-contaminated identity, scattered writes, mutable validation, and direct downstream graph handoffs were retired or rewritten.

## Install

Python 3.12 is canonical. `uv.lock` is committed and used by CI.

```bash
python -m pip install uv==0.10.0
uv sync --frozen --extra dev
```

A standard installation also works, but it does not provide lockfile-level reproducibility:

```bash
python -m pip install .
```

## Local packet vertical slice

Compile the fixture Repository Model Packet bundles into one validated Topology Packet bundle:

```bash
uv run l9-topology compile-packet \
  --repo-root . \
  --input-bundle tests/fixtures/repository_model_packets/l9-gate-sdk \
  --input-bundle tests/fixtures/repository_model_packets/l9-mcp-server \
  --out outputs/fixture-topology
```

Validate and inspect the result:

```bash
uv run l9-topology validate-packet --input-bundle outputs/fixture-topology
uv run l9-topology inspect-packet --input-bundle outputs/fixture-topology
uv run l9-topology verify-determinism \
  --repo-root . \
  --input-bundle tests/fixtures/repository_model_packets/l9-gate-sdk \
  --input-bundle tests/fixtures/repository_model_packets/l9-mcp-server
```

Render optional projections from the packet:

```bash
uv run l9-topology render-report \
  --repo-root . \
  --input-bundle outputs/fixture-topology \
  --out outputs/fixture-reports \
  --format markdown \
  --format mermaid \
  --format maturity-csv \
  --format neo4j-candidate
```

`neo4j-candidate` is a neutral candidate export. This repository contains no Neo4j or Graphiti write client.

## Compatibility ingress

Legacy scanner logic remains available only as a read-only observation provider:

```bash
uv run l9-topology scan \
  --repo-root . \
  --source-repo /path/to/repository \
  --repository-id repository-name \
  --out outputs/scanned-topology
```

The command creates a temporary Repository Model Packet adaptation and invokes the same v5 compiler. It does not restore the retired report-directory stage contract.

## Stage worker

The worker accepts a signed `TransportPacket` carrying `l9.stage-dispatch/1.0.0`.

```bash
L9_DISPATCH_HMAC_KEY='runtime-secret' \
uv run l9-topology-worker \
  --dispatch-file /path/to/signed-dispatch.json \
  --repo-root . \
  --workspace outputs/worker
```

GitHub Actions validates the signature with trusted `main` code before using the requested revision. It then checks out the signed exact Git object ID, creates the exact-revision environment from `uv.lock`, recompiles, publishes, reloads, verifies, and sends a signed callback.

## Generated artifact synchronization

Checked-in JSON Schemas and Repository Model Packet fixtures are deterministic outputs derived from canonical models and sample repositories. Validation detects drift without rewriting the worktree.

```bash
make generated-check
```

Use explicit update targets only when the source of a generated artifact intentionally changes:

```bash
make schemas-update
make fixtures-update
# or both
make generated-update
```

Review every generated diff, then rerun `make generated-check` and the full validation ladder. `make validate` includes the schema drift gate (`schemas-check`) and fails when a checked-in schema is missing or stale. Fixture packet drift is verified on demand with `make fixtures-check` (or `make generated-check`), which is kept out of `make validate` because fixture packets embed a wall-clock timestamp and the live repository revision; it becomes gate-eligible once fixture generation is deterministic.

## Validation ladder

```bash
uv run python -m compileall src tests scripts -q
uv run pytest --cov=l9_constellation_topology --cov-report=term-missing -q
uv run ruff check .
uv run mypy src/l9_constellation_topology
uv run python scripts/validate_contracts.py
uv run python scripts/validate_workflows.py
uv run python scripts/architecture_boundary_check.py
uv run python scripts/validate_release_readiness.py
uv run python scripts/generate_schemas.py --check
uv run python scripts/generate_fixture_packets.py --check
uv run python scripts/validate_git_integrity.py
uv run python scripts/verify_determinism.py
uv build
```

## Repository authority and decision memory

- [Full build specification](BUILD_SPECIFICATION.md)
- [Architecture](ARCHITECTURE.md)
- [ADR index](ADR_INDEX.md)
- [Governance](GOVERNANCE.md)
- [Security](SECURITY.md) and [threat model](THREAT_MODEL.md)
- [Development](DEVELOPMENT.md), [contributing](CONTRIBUTING.md), and [releasing](RELEASING.md)
- [Operator runbook](RUNBOOK.md) and [support](SUPPORT.md)
- [Initial commit handoff](INITIAL_COMMIT.md)

See also [VALIDATION.md](VALIDATION.md), [REGRESSION_GUARD.md](REGRESSION_GUARD.md), [SPECIFICATION.md](SPECIFICATION.md), [docs/architecture.md](docs/architecture.md), [docs/deployment.md](docs/deployment.md), and [docs/migration-v4-to-v5.md](docs/migration-v4-to-v5.md).
