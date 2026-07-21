# ADR-0010: Use decomposed confidence assessment

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

A single low, medium, or high label cannot explain evidence strength, derivation, authority, completeness, or conflict state.

## Decision

- Represent confidence as level, evidence strength, derivation method, authority, completeness, and conflict status.
- Retain the simple level only for compatibility and coarse routing.
- Base canonical decisions on the complete assessment.

## Consequences

### Positive

- Trust decisions become explainable and policy-addressable.
- Compatibility with legacy labels is preserved.

### Costs and constraints

- More fields require consistent producer behavior.
- Profiles must define how dimensions influence validation and risk.

## Alternatives considered

- **Rejected:** Keep only low, medium, and high.
- **Rejected:** Encode confidence reasoning in free-text evidence.

## Compliance and validation

- Schema validation requires every confidence dimension.
- Tests cover declared, deterministic, heuristic, candidate, and conflict states.

## Related artifacts

- `src/l9_constellation_topology/domain/confidence.py`
- `schemas/evidence-record.schema.json`
