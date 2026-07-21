# ADR-0014: Drive maturity and risk from versioned profiles

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

Hard-coded scores and risk rules turn one team's assumptions into permanent product truth.

## Decision

- Define dimensions, weights, bands, evidence requirements, unknown handling, and rule versions in `.l9/` profiles.
- Treat maturity as a projection.
- Attach rule identity and evidence to every risk.

## Consequences

### Positive

- Policies can evolve without rewriting compiler stages.
- Legacy scoring remains available as an explicit profile.

### Costs and constraints

- Profile governance becomes essential.
- Different profiles may produce different assessments from the same topology.

## Alternatives considered

- **Rejected:** Hard-code one maturity scorecard.
- **Rejected:** Delegate all assessments downstream.

## Compliance and validation

- Profile hashes participate in packet identity.
- Assessment tests cover configured weights, bands, and rule versions.

## Related artifacts

- `.l9/maturity-profile.yaml`
- `.l9/risk-profile.yaml`
