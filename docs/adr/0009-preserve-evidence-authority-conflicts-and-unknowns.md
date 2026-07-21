# ADR-0009: Preserve evidence authority, conflicts, and unknowns

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Topology compilation combines declarations, validated packets, direct observations, and derivations. Silent precedence or last-write-wins would manufacture certainty.

## Decision

- Apply the documented evidence authority order.
- Create explicit ConflictRecord and UnknownRecord values.
- Never promote inferred claims as source declarations.

## Consequences

### Positive

- Disagreement and missing evidence remain visible.
- Downstream policy can make evidence-aware decisions.

### Costs and constraints

- Packets carry more diagnostic material.
- Operators must handle unresolved records explicitly.

## Alternatives considered

- **Rejected:** Resolve conflicts by latest timestamp.
- **Rejected:** Drop unsupported claims silently.

## Compliance and validation

- Invariant validation requires evidence for canonical claims.
- Reconciliation tests preserve conflicting values and unknowns.

## Related artifacts

- `docs/evidence-model.md`
- `schemas/evidence-record.schema.json`
