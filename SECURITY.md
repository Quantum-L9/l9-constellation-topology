# Security

## Trust boundaries

- Source repositories are read-only during compilation.
- Cross-repository control and result packets are signed under the active packet profile.
- Packet and attachment hashes are verified before use.
- Repository, workflow, action, payload-schema, profile, and key-ID allowlists fail closed.
- Human personal access tokens, database owner credentials, GitHub App private keys, and static cloud keys are prohibited in this repository.

## Dispatch-before-checkout rule

A dispatch-provided revision is untrusted until the packet signature and payload contract pass.

The stage workflow first installs trusted worker code from `main`, validates the signed dispatch, and accepts only a 40- or 64-character lowercase hexadecimal Git object ID. It does not use a packet field as a checkout ref before authentication. The exact signed revision is then checked out, installed from its frozen lockfile, and validated again before execution.

## Credential handling

GitHub OIDC, GitHub App installation tokens, and job-scoped `GITHUB_TOKEN` are preferred. Callback and signing secrets are supplied at runtime and never serialized into packets, logs, reports, or commit receipts.

The foundational implementation supports `hmac-sha256` with allowlisted key IDs. Production key custody, rotation, and eventual asymmetric signing remain external control-plane decisions. Key material must be stored in GitHub encrypted secrets or a dedicated secret manager, never in `.env`, repository files, workflow artifacts, or packet bundles.

## Least privilege

- PR validation: `contents: read`.
- Ingress and replay: `contents: read`, `id-token: write`.
- Stage worker: `contents: read`, `packages: write`, `id-token: write`.
- No workflow receives organization-administration permissions.

## External effects

Production Python source outside `io/` is prohibited from direct filesystem mutation. The architecture check enforces this boundary. Network calls are isolated to worker callback and packet-store adapters. The compiler domain does not import Neo4j or Graphiti clients.

## Reporting

Report suspected vulnerabilities privately to the repository owners. Do not open a public issue containing secrets, exploit details, or sensitive packet contents.

## Threat and dependency governance

The trust boundaries, protected assets, primary threats, and residual risks are
documented in `THREAT_MODEL.md`. Dependency and GitHub Action controls are defined
in `DEPENDENCY_POLICY.md`. Changes to signing, storage, tenancy, or worker trust
require security review and an ADR.
