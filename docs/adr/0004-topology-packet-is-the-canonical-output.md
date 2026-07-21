# ADR-0004: Topology Packet is the canonical output

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

A loose set of JSON, YAML, CSV, Markdown, and graph files cannot provide one immutable semantic identity or reliable downstream lineage.

## Decision

- Emit one Topology Packet that contains or references every canonical topology payload.
- Bind payloads through a deterministic bundle manifest and semantic hash.
- Treat all human and graph exports as projections.

## Consequences

### Positive

- Downstream stages consume one versioned contract.
- Packet lineage and reuse become deterministic.

### Costs and constraints

- Packet construction is more structured than writing individual reports.
- Consumers must migrate away from neighboring files.

## Alternatives considered

- **Rejected:** Continue the report directory as an informal packet.
- **Rejected:** Use Neo4j JSONL as the canonical output.

## Compliance and validation

- Bundle round-trip tests verify manifest membership and hashes.
- Ingestion contracts reference the Topology Packet rather than reports.

## Related artifacts

- `contracts/topology-packet.schema.json`
- `docs/packet-contracts.md`
