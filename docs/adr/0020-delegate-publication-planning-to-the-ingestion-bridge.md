# ADR-0020: Delegate publication planning to the ingestion bridge

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Topology compilation and canonical graph promotion require different authority. Combining them would let analytical output mutate durable knowledge directly.

## Decision

- Emit evidence-linked topology and neutral graph candidates only.
- Delegate promotion policy, destination lowering, effect planning, and publication receipts to `l9-topology-ingestion-bridge`.
- Prohibit Neo4j and Graphiti write clients in this repository.

## Consequences

### Positive

- The compiler remains read-only and evidence-focused.
- Publication policy can evolve independently.

### Costs and constraints

- A downstream component is required for live graph updates.
- Candidate formats require coordinated contracts.

## Alternatives considered

- **Rejected:** Write directly to graph stores after validation.
- **Rejected:** Move all topology logic into the bridge.

## Compliance and validation

- Architecture checks reject graph-client imports.
- End-to-end tests require the bridge to consume the Topology Packet without report files.

## Related artifacts

- `contracts/topology-packet.schema.json`
- `docs/architecture.md`
