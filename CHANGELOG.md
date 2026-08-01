# Changelog

## Unreleased - release-integrity and trust-boundary remediation

- Restored the complete `.github` and `.l9` surfaces to the deliverable and added a Git-index integrity gate.
- Replaced topology-only reuse identity with a complete compilation fingerprint covering all semantic profiles, schemas, adapters, inputs, and compiler build identity.
- Replaced packet-selected callback URLs and environment-variable names with a worker-local callback registry and network destination policy.
- Bound publication and reuse verification to digest-qualified immutable packet references and exact expected packet identities.
- Preserved upstream diagnostics as typed, lineage-bearing Topology Packet payload records with a conservation invariant.
- Made packet-bundle publication atomic at directory scope and replaced the local JSON recovery index with transactional SQLite WAL storage.
- Separated runtime-model construction checks from independent checked-in JSON Schema validation in Validation Receipts.
- Added adversarial regression tests for policy mutation, callback trust, packet substitution, diagnostics conservation, bundle atomicity, registry concurrency, and Git-tree evidence drift.
- Enforced callback path segment boundaries, rejected encoded slash and backslash ambiguity, and added explicit host and port policy.
- Added `GIT_TREE_MANIFEST.json`, which binds every tracked entry except itself to its Git mode, object type, and blob ID.
- Published OCI bundles through semantic-hash-derived staging tags and independently resolved the immutable registry descriptor before accepting publication.

## Unreleased - initial repository enrichment

- Added the complete source-aligned v5 build specification.
- Added root architecture, governance, maintainer, development, release, support,
  threat, dependency, conduct, notice, license, and initial-commit files.
- Added 20 accepted high-priority ADRs with an authoritative index.
- Added GitHub pull-request and issue templates aligned with packet and evidence laws.
- Added deterministic repository-governance tests and expanded release-readiness gates.
- Regenerated the manifest, final tree, traceability, validation, and convergence evidence.

## Unreleased - hardening

- Added executable no-stub, thin-file, release-artifact, and manifest-drift validation.
- Made malformed `package.json` dependency declarations fail closed instead of disappearing silently.
- Replaced protocol and exception placeholder bodies with explicit structural contracts.
- Added traceability, regression, validation, Unknown, manifest, and final-tree release artifacts.
- Wired release-readiness validation into the pull-request workflow and workflow contract tests.

## 2.0.0 - 2026-07-21

- Replaced the v4 report-directory generator architecture with the v5 packet-native topology compiler.
- Added canonical Repository Model Packet ingestion and Topology Packet bundles.
- Added decomposed confidence, evidence, conflicts, unknowns, capabilities, flows, impact, risk, and maturity records.
- Added immutable validation receipts, deterministic semantic hashing, OutputSink planning, atomic commits, and commit receipts.
- Preserved legacy scanners and commands behind compatibility adapters.
- Added GitHub Actions worker, ingress, replay, validation, recovery, and idempotency contracts.
- Added signed dispatch preflight before checkout, exact-revision frozen environments, local and OCI packet stores, authenticated callbacks, and strict typing/lint gates.
