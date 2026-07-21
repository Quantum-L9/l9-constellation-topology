# Dependency Policy

## Principles

Dependencies must reduce implementation risk more than they add supply-chain,
operational, or compatibility risk. The compiler domain remains deliberately small.

## Runtime dependencies

Runtime packages must be required for packet modeling, schema validation, or profile
loading. New runtime dependencies require:

- a documented need that cannot be met cleanly by the standard library or an
  existing dependency;
- license and maintenance review;
- bounded import ownership;
- lockfile update;
- tests covering the integration boundary;
- an ADR when the dependency changes architecture or execution authority.

## Development dependencies

Development tools may support testing, coverage, linting, typing, and packaging.
They must remain pinned through `uv.lock` and cannot become implicit runtime
requirements.

## GitHub Actions

Actions must be pinned to immutable commit SHAs. Version tags alone are not accepted
for execution-sensitive workflows. Permissions remain explicit and least-privilege.

## Network and service dependencies

The compiler domain performs no network calls. Worker-side network access is limited
to packet retrieval and publication plus authenticated callbacks. A new service
integration requires an adapter boundary, failure policy, tests, runbook updates,
and security review.

## Update process

1. Update dependency declarations and `uv.lock` together.
2. Review transitive changes and package metadata.
3. Run the full validation ladder and isolated installation smoke.
4. Record behavior or compatibility impact in `CHANGELOG.md`.
5. Do not merge a lockfile change that cannot be reproduced from declared inputs.

## Prohibited dependencies

- Neo4j or Graphiti write clients in this repository;
- database drivers used to embed the Postgres control plane;
- alternative control-plane envelope frameworks;
- major orchestration infrastructure without measured need;
- packages that require secrets at import time.
