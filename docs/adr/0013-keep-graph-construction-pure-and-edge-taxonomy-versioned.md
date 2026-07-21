# ADR-0013: Keep graph construction pure and edge taxonomy versioned

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Graph logic must be testable independently of output systems, and edge meanings must remain stable for downstream consumers.

## Decision

- Graph builders accept canonical records and return graph records without side effects.
- Use an enumerated versioned edge taxonomy.
- Require schema and ADR updates for new canonical edge types.

## Consequences

### Positive

- Graph behavior is deterministic and portable.
- Downstream semantics are explicit.

### Costs and constraints

- Taxonomy changes require coordination.
- Experimental relationships must remain candidate or profile-specific until accepted.

## Alternatives considered

- **Rejected:** Build graph records while writing files.
- **Rejected:** Use arbitrary relationship strings.

## Compliance and validation

- Unit tests verify stable node and edge IDs.
- Architecture checks prohibit write and graph-client imports in topology modules.

## Related artifacts

- `src/l9_constellation_topology/topology/graph_builder.py`
- `schemas/edge-record.schema.json`
