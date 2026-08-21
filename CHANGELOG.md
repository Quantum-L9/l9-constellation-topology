# Changelog

## Unreleased - semantic assertion activation and durable write identity

- Activated the repository-model 1.1.0 assertion domain end to end. Assertions
  survived the adapter and were then dropped by `normalize_models`, so every
  semantic claim a repository made about itself was discarded between ingress and
  topology. They are now carried, reconciled into `SemanticClaimRecord`s, and
  published as structured subject/predicate/object memory assertions.
- Bound every assertion to a topology `EvidenceRecord` keyed on the *source
  file's* digest rather than the repository snapshot's, preserving the producer's
  assertion id, extractor, exact span, and read excerpt.
- Added a versioned predicate registry declaring which predicates aggregate,
  which can contradict, which are auxiliary, and which have no rule at all. Its
  hash is bound into `TopologyPacket.policy_hashes`. An unsupported predicate is
  preserved with its evidence, a diagnostic, and a predicate-scoped unknown; it
  is never aggregated, contradicted, discarded, or projected.
- Projected only the predicates with an explicit mapping. External names become
  explicitly-labelled external identities, so a package dependency never becomes
  an observed constellation repository and a route observation never becomes a
  verdict about whether its handler works.
- Added the `cross-assertion-conservation` validation check: an assertion that
  reaches the compiler and leaves no trace now fails the compile, by identity
  rather than by count.
- Stopped `reconcile_evidence` adjudicating assertion predicates under the
  field-cardinality contract, which had reported multi-valued predicates as
  undeclared-cardinality unknowns and held nearly every claim in a plan for a
  doubt that did not exist.
- Replaced the `v2` effect identity with `v3`, which separates the identity of a
  *fact* from the identity of the exact durable *write* requested. Under `v2` a
  re-publication carrying revised evidence or confidence reused the previous key,
  and downstream — where the key names an operation — answered `DUPLICATE` and
  discarded the new epistemic state. Snapshot-level hashes remain excluded.
- Recorded `EFFECT_IDENTITY_MIGRATION_PREFLIGHT.json`, the checked evidence that
  no `v2` key ever reached durable memory, which is what makes adopting `v3`
  directly rather than migrating a safe decision.
- Extended `HASH_LOCALITY_EVALUATION.json` to seventeen cases covering both
  directions of the identity contract, with per-case verdicts asserted by tests.
- Added `scripts/qualify_repository_model_assertions.py` and `QUALIFICATION.json`,
  recording activation results against real repository-model packets produced by
  the bound `l9-meta-injector` from `cryptoxdog/golden-repo` and
  `Quantum-L9/L9-Ops-MCP`. Zero assertion loss, zero dispatches.
- Repository-model 1.0.0 inputs carry no assertion domain and compile exactly as
  before, inventing no claims.

## Unreleased - pre-deployment repair: scan semantics, conflict cardinality, and effect identity

- Repaired the bounded compatibility scan: staged packet bundles are now verified
  back with the loader that owns the packet type their manifest declares, so the
  synthetic `l9.repository-model` bundle is no longer judged against Topology
  Packet semantics. An unrecognized packet type fails closed.
- Replaced status-only commit failure reporting with a deterministic rendering of
  the receipt's own reasons: failure stage, packet type, affected member, and
  inner message, with a shared atomic-bundle cause printed once.
- Introduced versioned reconciliation cardinality. Set-valued facts such as
  languages, workflows, and governance references aggregate deterministically
  instead of becoming false conflicts that held sound publication candidates;
  single-valued incompatibility still conflicts; an undeclared field yields an
  explicit unknown. The policy hash is bound into `TopologyPacket.policy_hashes`.
- Replaced the snapshot-global `v1` publication idempotency key with the
  explicitly versioned `v2` fact-local effect identity. An unrelated change
  anywhere in a Topology Packet no longer re-keys every unchanged downstream
  write. The algorithm version is encoded in the key namespace.
- Added `HASH_LOCALITY_EVALUATION.json` and `make hash-locality`, recording where
  topology, candidate, and effect identity moves under eleven controlled
  perturbations, with per-case verdicts asserted by tests.
- Made fixture generation byte-reproducible by pinning `created_at` and deriving
  `source_revision` from sample content; `fixtures-check` and the generated golden
  Topology Packet bundle now run inside `make validate`.
- Reconciled the design specification with accepted ADR-0021: the external
  ingestion bridge is marked superseded historical architecture throughout.

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
- Added read-only generated-artifact drift gates for checked-in schemas and Repository Model Packet fixtures, with explicit `schemas-update`/`fixtures-update` regeneration commands.
- Wired the deterministic schema drift gate (`schemas-check`) into `make validate`; fixture drift was initially checked on demand via `make fixtures-check` pending deterministic fixture generation, and is now gated (see the pre-deployment repair entry above).
- Synchronized AGENTS, README, DEVELOPMENT, RUNBOOK, and VALIDATION with the generated-artifact workflow.

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
