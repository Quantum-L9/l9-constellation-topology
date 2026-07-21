# Maintainers

## Maintainer roles

### Repository maintainer

Owns repository administration, branch protection, releases, and final merge
authority.

### Compiler architecture maintainer

Owns packet boundaries, canonical domain records, evidence authority, graph
semantics, deterministic identity, and accepted ADRs.

### Runtime and operations maintainer

Owns GitHub Actions worker behavior, packet-store adapters, callback contracts,
replay, recovery documentation, and deployment validation.

### Contract maintainer

Owns JSON Schemas, version compatibility, fixture packets, and cross-repository
contract coordination.

## Current assignment

Assignments are controlled through the Quantum L9 GitHub organization and
repository permissions. No personal roster or team slug is embedded in source
until the organization confirms a stable ownership map.

## Required maintainer actions

- Review contract compatibility before merging schema changes.
- Require evidence for validation and deployment claims.
- Keep ADR status and supersession links current.
- Reject direct graph publication or source mutation from this repository.
- Preserve deterministic packet identity and OutputSink containment.
- Coordinate upstream and downstream interface changes before release.
