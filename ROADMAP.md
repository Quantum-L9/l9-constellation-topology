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

## R5: Downstream ingestion integration

- Pass the validated Topology Packet to `l9-topology-ingestion-bridge`.
- Prove the bridge does not depend on neighboring report files.
- Verify candidate and publication-plan lineage.

## R6: Operational maturity

- Add release signing and provenance at the organization level.
- Establish packet retention and supersession operations.
- Add production observability through the shared L9 platform boundary.
- Measure compiler performance and introduce optimization only from evidence.

## R7: Generated-artifact determinism

- Make Repository Model Packet fixture generation deterministic (stable `created_at` and a source-content-derived `source_revision` independent of the live repository HEAD) so `make fixtures-check` becomes gate-eligible and can join `schemas-check` inside `make validate`.

## Explicitly deferred

- Full L9 Gate dependency for the foundational phase.
- Direct Neo4j or Graphiti writes.
- Kafka, Redis, Temporal, or self-hosted runners without measured need.
- Model-assisted topology inference without a separately approved profile and ADR.
