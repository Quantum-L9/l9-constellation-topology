# ADR-0019: Use idempotency, reuse, replay, and reconciliation

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Retries, callback loss, and duplicate events are normal distributed-system conditions. Recompiling or republishing blindly can diverge state.

## Decision

- Derive idempotency from a complete semantic compilation fingerprint: parent semantic hashes, compiler build identity, aggregate output-affecting configuration, schema contracts, active contract versions, adapter mode, and output packet type/version.
- Reuse prior validated packets.
- Reconcile published results after callback loss and preserve dead letters after exhaustion.

## Consequences

### Positive

- Repeated work is safe and cheaper.
- Recovery preserves lineage and avoids duplicate publication.

### Costs and constraints

- The control plane must atomically coordinate registry and stage state.
- Operators need explicit retry classifications.

## Alternatives considered

- **Rejected:** Use random run IDs as idempotency.
- **Rejected:** Treat every retry as a new semantic result.

## Compliance and validation

- Mutation tests prove that every output-affecting profile, schema, adapter mode, and compiler build identity changes the key.
- Local SQLite WAL registry tests prove reuse and concurrent-writer behavior.
- External staging must prove dropped-callback repair and dead-letter visibility.

## Related artifacts

- `src/l9_constellation_topology/worker/registry.py`
- `docs/recovery.md`
