# ADR-0016: Use Postgres Model B orchestration with GitHub Actions workers

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

GitHub Actions alone is ephemeral and weak at durable dependencies, retries, reconciliation, and global packet registry state.

## Decision

- Use Postgres as durable workflow state and GitHub Actions as exact-revision execution workers.
- Activate stages from validated packet existence.
- Keep database schema and scheduler ownership outside this repository.

## Consequences

### Positive

- Durable workflow semantics and familiar repository-local workers.
- The compiler remains deployable without embedding the control plane.

### Costs and constraints

- Production operation depends on an external control API and database.
- End-to-end proof requires cross-repository staging.

## Alternatives considered

- **Rejected:** Use workflow completion events as dependencies.
- **Rejected:** Embed a scheduler in the topology repository.

## Compliance and validation

- Worker contracts and mock integration tests cover local behavior.
- External acceptance matrix items remain blocked until live drills run.

## Related artifacts

- `.l9/pipeline.yaml`
- `docs/deployment.md`
