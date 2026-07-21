# Governance

## Purpose

This file defines how repository authority, architectural decisions, releases,
and operational changes are governed.

## Authority order

1. Explicit maintainer decision recorded in the repository.
2. `BUILD_SPECIFICATION.md` and `SPECIFICATION.md`.
3. Accepted ADRs in `docs/adr/`.
4. Machine-readable contracts and schemas.
5. Versioned `.l9/` profiles.
6. Executable tests and validation scripts.
7. Operational documentation.
8. Historical v4 documents, which are non-authoritative.

A lower authority cannot silently contradict a higher authority. Conflicts must be
resolved by changing the lower artifact or by accepting a new ADR that supersedes
the prior decision.

## Change classes

### Contract change

Changes packet shapes, semantic identity, evidence authority, validation rules, or
stage boundaries. Requires:

- an ADR or an explicit amendment to an existing ADR;
- schema compatibility analysis;
- migration notes;
- contract and integration tests;
- a major or minor version decision under `RELEASING.md`.

### Behavioral change

Changes compiler output while preserving public packet contracts. Requires tests,
determinism verification, and documented effect on generated topology.

### Operational change

Changes workflows, packet storage, callbacks, credentials, retry behavior, or
release mechanics. Requires security review and runbook updates.

### Documentation-only change

Must remain consistent with executable behavior and cannot declare unverified
capabilities.

## ADR lifecycle

ADRs use the states `Proposed`, `Accepted`, `Superseded`, and `Rejected`.
Accepted ADRs are immutable except for clerical corrections and links. A changed
decision is recorded in a new ADR that names the superseded record.

## Approval policy

Repository maintainers approve changes through pull requests. Contract and
architecture changes require review from the maintainers responsible for the
compiler boundary and the affected upstream or downstream interface.

Exact GitHub team slugs are intentionally not embedded until the organization
confirms them. Ownership is therefore represented by repository permissions,
branch protection, and the role definitions in `MAINTAINERS.md`.

## Branch and release policy

- `main` represents the current accepted repository state.
- Direct writes to protected `main` are prohibited.
- Required checks are defined by `.github/workflows/l9-pr-validate.yml`.
- Releases must follow `RELEASING.md` and preserve captured validation evidence.
- Generated documentation changes use pull requests and expected-hash protection.

## Governance failures

Any change that bypasses packet validation, OutputSink, exact-revision execution,
or evidence lineage is a release blocker regardless of test count.
