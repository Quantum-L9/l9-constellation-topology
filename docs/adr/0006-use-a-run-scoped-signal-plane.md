# ADR-0006: Use a run-scoped signal plane

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Compilation requires evidence, diagnostics, conflicts, unknowns, stage outputs, and receipts. Hidden module state would make replay and testing unreliable.

## Decision

- Represent run state with explicit typed objects passed between stages.
- Record inputs, policies, evidence, derivations, diagnostics, outputs, and lineage in the RunContext.
- Prohibit global mutable compiler state.

## Consequences

### Positive

- Runs are replayable and testable.
- Stage boundaries and evidence provenance are observable.

### Costs and constraints

- Typed context objects require deliberate evolution.
- Large runs may require memory profiling.

## Alternatives considered

- **Rejected:** Use module globals or ambient filesystem state.
- **Rejected:** Store all signals only in logs.

## Compliance and validation

- Unit tests instantiate independent RunContext objects.
- No compiler module relies on prior-run state.

## Related artifacts

- `src/l9_constellation_topology/run/`
- `docs/evidence-model.md`
