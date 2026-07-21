# ADR-0011: Permit only bounded read-only fallback observation

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Some required topology evidence may be absent from an otherwise valid Repository Model Packet. A complete prohibition would block useful compilation; unrestricted rescanning would duplicate upstream ownership.

## Decision

- Allow direct observation only when enabled by profile and tied to the exact source revision.
- Require deterministic, read-only providers.
- Classify new observations separately and prohibit silent override of stronger authority.

## Consequences

### Positive

- The compiler can fill narrow topology gaps.
- Upstream ownership remains intact.

### Costs and constraints

- Source checkout may be required for some profiles.
- Observation providers require strict scope and tests.

## Alternatives considered

- **Rejected:** Never inspect source repositories.
- **Rejected:** Always rescan the full repository.

## Compliance and validation

- Observation tests verify read-only behavior and evidence classification.
- Profiles default to bounded behavior.

## Related artifacts

- `src/l9_constellation_topology/scanners/`
- `.l9/topology-profile.yaml`
