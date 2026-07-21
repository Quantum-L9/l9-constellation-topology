# ADR-0017: Require signed exact-revision worker execution

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

A dispatch that selects code before authentication can execute attacker-controlled revisions. Branch names are mutable and insufficient for reproducible work.

## Decision

- Authenticate the signed dispatch with trusted main code before checkout.
- Require an exact Git object ID.
- Build a frozen environment from the selected revision and revalidate before execution.

## Consequences

### Positive

- Tampered packets cannot select executable code.
- Runs are reproducible at a precise revision.

### Costs and constraints

- The worker performs a two-checkout, two-environment sequence.
- Key custody and rotation remain external obligations.

## Alternatives considered

- **Rejected:** Check out the requested ref before validation.
- **Rejected:** Allow branch or tag names as execution authority.

## Compliance and validation

- Signature and revision tests cover tampering and invalid object IDs.
- Workflows pin actions and use least privilege.

## Related artifacts

- `.github/workflows/l9-stage-worker.yml`
- `docs/worker-contract.md`
