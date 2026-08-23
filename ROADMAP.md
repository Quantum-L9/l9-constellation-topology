# Roadmap

The compiler implementation is locally complete for the v5 packet boundary. The
remaining work is integration proof, operational hardening, and controlled
adoption across the foundational chain.

## R1: Initial repository establishment

- Commit the consolidated repository as the canonical initial source tree.
- Enable branch protection and required validation checks.
- Confirm maintainer and review ownership in GitHub.
- Preserve the v5 build specification and accepted ADRs.

## R2: Real upstream packet integration

- Consume a Repository Model Packet emitted by `l9-meta-injector`.
- Validate producer, schema, source revision, payload hashes, and parent receipt.
- Resolve any version adaptation through an explicit adapter and compatibility test.

## R3: Immutable packet publication

- Execute a real GHCR/ORAS push and clean pull verification.
- Confirm least-privilege package permissions.
- Record packet digest, bundle manifest, Validation Receipt, and registry entry.

## R4: Model B orchestration proof

- Dispatch through the external Postgres control plane.
- Verify stage leases, retries, result callbacks, and atomic registry updates.
- Deliberately lose a callback and prove idempotent reconciliation.
- Exhaust a retryable failure and inspect the dead-letter record.

## R5: Downstream memory integration

- Plan publication from the validated Topology Packet with `plan-publication`.
- Verify candidate, evidence, and publication-plan lineage.
- Validate every eligible `memory.ingest` intent against the bound
  `l9-graphiti-memory` contract without dispatching it.
- Remaining: live Gate dispatch and durable admission, both owned downstream.

## R6: Operational maturity

- Add release signing and provenance at the organization level.
- Establish packet retention and supersession operations.
- Add production observability through the shared L9 platform boundary.
- Measure compiler performance and introduce optimization only from evidence.

## R7: Generated-artifact determinism — delivered

- Repository Model Packet fixture generation is deterministic: `created_at` is pinned and `source_revision` is derived from the sample tree's own content rather than the live repository HEAD. `make fixtures-check` is gate-eligible and runs inside `make validate` through `generated-check`, alongside the golden Topology Packet bundle and the hash-locality evaluation.

## R8: Corpus intelligence — delivered

- `l9.corpus-intelligence` 1.0.0 is accepted as an optional auxiliary input beside
  Repository Model Packets, with fail-closed referential integrity against exactly
  the packets it names (ADR-0026).
- Topology Packet 1.1.0 carries corpus, root, candidate, readiness, and reasoning
  domains. A 1.0.0 bundle still loads and a compile with no corpus input is
  unchanged.
- Evidence locators are generalized: PDF page/block, DOCX block, PPTX slide/shape,
  spreadsheet sheet/cell, notebook cell, CSV row, and HTML node, with a line number
  refused beside any of them.
- `adapt-meta-corpus` is compatibility ingress for current producer generations.
  It is intended to be retired once `l9-meta-injector` emits the canonical packet
  directly, which is also what would let it carry per-signal structured locators
  for binary documents — the one class of work signal the adapter currently
  declines rather than locates by invention.

## Explicitly deferred

- Full L9 Gate dependency for the foundational phase.
- Direct Neo4j or Graphiti writes.
- Kafka, Redis, Temporal, or self-hosted runners without measured need.
- Model-assisted topology inference without a separately approved profile and ADR.
