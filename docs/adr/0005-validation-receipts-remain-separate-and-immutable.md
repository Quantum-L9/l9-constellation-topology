# ADR-0005: Validation Receipts remain separate and immutable

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Validation that mutates the subject obscures what was evaluated and makes independent verification impossible.

## Decision

- Produce a separate Validation Receipt referencing the exact subject packet semantic hash.
- Do not rewrite validation status into the packet after validation.
- Require a passed receipt alongside the packet for downstream use.

## Consequences

### Positive

- The validated bytes remain stable.
- Validators can be independently versioned and audited.

### Costs and constraints

- Consumers must resolve two linked artifacts.
- Receipt publication and packet publication must remain consistent.

## Alternatives considered

- **Rejected:** Mutate the packet with a validation field.
- **Rejected:** Treat successful serialization as validation.

## Compliance and validation

- Tests compare receipt subject hash with the packet semantic hash.
- Stage success requires both packet and passed receipt.

## Related artifacts

- `contracts/validation-receipt.schema.json`
- `src/l9_constellation_topology/validation/`
