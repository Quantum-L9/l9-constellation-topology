# ADR-0008: Separate semantic hashes from artifact hashes

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Timestamps, local paths, and presentation order can change bytes without changing topology meaning. One hash cannot represent both semantics and exact artifacts.

## Decision

- Compute semantic hashes from normalized semantic content only.
- Exclude timestamps, machine-local paths, execution IDs, and presentation order.
- Compute artifact hashes over exact emitted bytes.

## Consequences

### Positive

- Equivalent runs reuse prior semantic results.
- Byte integrity remains independently verifiable.

### Costs and constraints

- Every record and projection must define what is semantic.
- Canonicalization rules become part of the contract.

## Alternatives considered

- **Rejected:** Use one byte hash for everything.
- **Rejected:** Remove timestamps from every human artifact.

## Compliance and validation

- Determinism tests compare runs from different local roots.
- Bundle validation verifies exact artifact hashes.

## Related artifacts

- `src/l9_constellation_topology/run/evidence.py`
- `scripts/verify_determinism.py`
