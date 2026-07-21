# ADR-0018: Use immutable OCI packet storage and an external registry

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Large packet bundles do not belong in dispatch payloads, and ephemeral runners cannot own durable packet state.

## Decision

- Publish immutable bundles to GHCR-compatible OCI storage through ORAS.
- Carry only packet references, hashes, versions, and validation status in control messages.
- Keep durable registry state in the external Postgres control plane.

## Consequences

### Positive

- Content-addressed, cross-repository packet distribution.
- Runner and database responsibilities remain separate.

### Costs and constraints

- OCI permissions and retention require operational governance.
- Local file storage remains limited to tests and controlled single-host use.

## Alternatives considered

- **Rejected:** Store packet bodies in workflow inputs.
- **Rejected:** Use runner-local files as the production registry.

## Compliance and validation

- Worker publication re-fetches and validates the bundle.
- Deployment gates require real GHCR permission and digest drills.

## Related artifacts

- `src/l9_constellation_topology/worker/packet_store.py`
- `docs/deployment.md`
