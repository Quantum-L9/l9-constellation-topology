# ADR-0007: OutputSink is the only write boundary

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Scattered direct writes cannot enforce containment, collision policy, expected hashes, dry-run behavior, or truthful receipts.

## Decision

- Route every production filesystem effect through OutputSink.
- Renderers return RenderedArtifact values and stages emit WriteIntent values.
- Provide memory, filesystem, packet-bundle, and composite sinks.

## Consequences

### Positive

- One enforceable effect boundary.
- Dry-run, atomic replacement, unchanged skipping, and commit receipts are consistent.

### Costs and constraints

- All output paths must be modeled before commit.
- Filesystem atomicity remains per file rather than global.

## Alternatives considered

- **Rejected:** Allow renderers and CLI commands to write directly.
- **Rejected:** Use a general utility function without policy objects.

## Compliance and validation

- Architecture validation rejects write APIs outside `io/`.
- OutputSink tests cover containment, collisions, hashes, dry-run, and receipts.

## Related artifacts

- `src/l9_constellation_topology/io/`
- `docs/output-sink.md`
