# ADR-0003: Repository Model Packets are canonical inputs

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Artifact-level understanding belongs upstream. Rescanning every repository inside topology duplicates responsibility and weakens evidence lineage.

## Decision

- Require validated Repository Model Packets as canonical semantic inputs.
- Verify source revision, hashes, producer version, schema version, and parent Validation Receipt.
- Use versioned adapters for supported historical packet versions.

## Consequences

### Positive

- Topology compiles from immutable, evidence-linked semantics.
- Upstream and middle-end responsibilities remain distinct.

### Costs and constraints

- Topology execution depends on upstream packet availability.
- Version adapters must be maintained deliberately.

## Alternatives considered

- **Rejected:** Use local directories as the primary input.
- **Rejected:** Read neighboring reports emitted by meta-injector.

## Compliance and validation

- Packet loader tests cover hashes, receipts, version support, and identity conflicts.
- Unsupported versions fail closed.

## Related artifacts

- `contracts/repository-model-packet.schema.json`
- `src/l9_constellation_topology/packets/`
