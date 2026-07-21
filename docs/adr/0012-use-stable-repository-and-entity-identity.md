# ADR-0012: Use stable repository and entity identity

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

The donor fixture collapsed sibling repositories into one parent-directory node and used local paths in identity. That breaks cross-machine determinism and constellation correctness.

## Decision

- Resolve repository identity from packet subject, registry, Git boundary, explicit manifest, then configured fallback.
- Use canonical entity IDs independent of local absolute paths.
- Represent unresolved repository boundaries explicitly.

## Consequences

### Positive

- Two repositories remain distinct across machines and checkouts.
- Edges and impact indexes remain stable.

### Costs and constraints

- Identity conflicts may block compilation.
- Registries and packet producers must coordinate IDs.

## Alternatives considered

- **Rejected:** Use containing directory names as repository identity.
- **Rejected:** Hash absolute paths.

## Compliance and validation

- Fixture integration asserts two sibling repositories produce two nodes.
- Determinism tests vary local roots.

## Related artifacts

- `src/l9_constellation_topology/stages/aggregate_repositories.py`
- `docs/topology-model.md`
