# ADR-0015: Treat reports as lazy projections

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Regenerating all reports on every compile wastes work and encourages consumers to treat presentation files as contracts.

## Decision

- Render reports only on request or according to a report profile.
- Key projection reuse by topology semantic hash, renderer version, and report profile hash.
- Represent projections in a Report Manifest.

## Consequences

### Positive

- Canonical compilation is smaller and faster.
- Reports can evolve without changing topology semantics.

### Costs and constraints

- Operators must explicitly request some reports.
- Projection caches require lifecycle management.

## Alternatives considered

- **Rejected:** Always emit the full report directory.
- **Rejected:** Remove report support entirely.

## Compliance and validation

- Renderer tests prove reports regenerate from packets.
- No canonical input loader accepts report files.

## Related artifacts

- `docs/report-lifecycle.md`
- `src/l9_constellation_topology/renderers/`
