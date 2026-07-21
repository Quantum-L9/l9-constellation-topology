# ADR-0002: TransportPacket is the only control-plane envelope

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Cross-repository orchestration needs one authenticated, versioned, traceable wire shape. Multiple envelopes create duplicate identity, governance, and signature semantics.

## Decision

- Use TransportPacket for dispatch, replay, validation, render, result, failure, and reuse control messages.
- Carry the payload contract in `payload_schema` until it becomes a first-class transport header.
- Reject unsupported transport versions and unsigned cross-repository dispatches.

## Consequences

### Positive

- One transport identity and lineage model across the foundational pipeline.
- Signature, tenancy, governance, and attachment behavior remain consistent.

### Costs and constraints

- The compiler depends on the shared TransportPacket contract.
- Transport evolution requires coordinated compatibility work.

## Alternatives considered

- **Rejected:** Introduce a topology-specific envelope.
- **Rejected:** Send naked JSON through workflow inputs.

## Compliance and validation

- Contract validation covers every accepted and emitted payload.
- Worker preflight verifies signature, action, repository, profile, and payload schema.

## Related artifacts

- `contracts/transport-packet.schema.json`
- `docs/worker-contract.md`
