# ADR-0001: Packet-native middle-end compiler boundary

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

The donor implementation behaved primarily as a scanner that emitted a neighboring report directory. The foundational pipeline requires a semantic compiler boundary between artifact understanding and publication planning.

## Decision

- Define this repository as the repository- and constellation-level middle-end compiler.
- Accept validated Repository Model Packets and emit a validated Topology Packet.
- Keep source scanning and downstream publication outside the canonical compiler boundary.
- Preserve compatibility scanning only as an adapter into the canonical compiler.

## Consequences

### Positive

- Clear ownership between meta-injector, topology, and ingestion bridge.
- The compiler can evolve independently of report formats and graph products.

### Costs and constraints

- Existing report-directory consumers require migration.
- Compatibility paths add temporary maintenance cost.

## Alternatives considered

- **Rejected:** Keep the scanner/report generator as the product boundary.
- **Rejected:** Combine artifact scanning, topology, and graph publication in one repository.

## Compliance and validation

- Compiler integration tests require packet inputs and one canonical packet output.
- Architecture checks prohibit graph clients and source mutation.

## Related artifacts

- `BUILD_SPECIFICATION.md`
- `docs/architecture.md`
