# Architecture Decision Record Index

The following 21 ADRs define the highest-priority architectural decisions for this
repository. Accepted ADRs are immutable except for clerical fixes and links. A
changed decision requires a new ADR that explicitly supersedes the old record.

| ID | Decision | Status |
|---|---|---|
| ADR-0001 | [Packet-native middle-end compiler boundary](docs/adr/0001-packet-native-middle-end-compiler-boundary.md) | Accepted |
| ADR-0002 | [TransportPacket is the only control-plane envelope](docs/adr/0002-transportpacket-is-the-only-control-plane-envelope.md) | Accepted |
| ADR-0003 | [Repository Model Packets are canonical inputs](docs/adr/0003-repository-model-packets-are-canonical-inputs.md) | Accepted |
| ADR-0004 | [Topology Packet is the canonical output](docs/adr/0004-topology-packet-is-the-canonical-output.md) | Accepted |
| ADR-0005 | [Validation Receipts remain separate and immutable](docs/adr/0005-validation-receipts-remain-separate-and-immutable.md) | Accepted |
| ADR-0006 | [Use a run-scoped signal plane](docs/adr/0006-use-a-run-scoped-signal-plane.md) | Accepted |
| ADR-0007 | [OutputSink is the only write boundary](docs/adr/0007-outputsink-is-the-only-write-boundary.md) | Accepted |
| ADR-0008 | [Separate semantic hashes from artifact hashes](docs/adr/0008-separate-semantic-hashes-from-artifact-hashes.md) | Accepted |
| ADR-0009 | [Preserve evidence authority, conflicts, and unknowns](docs/adr/0009-preserve-evidence-authority-conflicts-and-unknowns.md) | Accepted |
| ADR-0010 | [Use decomposed confidence assessment](docs/adr/0010-use-decomposed-confidence-assessment.md) | Accepted |
| ADR-0011 | [Permit only bounded read-only fallback observation](docs/adr/0011-permit-only-bounded-read-only-fallback-observation.md) | Accepted |
| ADR-0012 | [Use stable repository and entity identity](docs/adr/0012-use-stable-repository-and-entity-identity.md) | Accepted |
| ADR-0013 | [Keep graph construction pure and edge taxonomy versioned](docs/adr/0013-keep-graph-construction-pure-and-edge-taxonomy-versioned.md) | Accepted |
| ADR-0014 | [Drive maturity and risk from versioned profiles](docs/adr/0014-drive-maturity-and-risk-from-versioned-profiles.md) | Accepted |
| ADR-0015 | [Treat reports as lazy projections](docs/adr/0015-treat-reports-as-lazy-projections.md) | Accepted |
| ADR-0016 | [Use Postgres Model B orchestration with GitHub Actions workers](docs/adr/0016-use-postgres-model-b-orchestration-with-github-actions-workers.md) | Accepted |
| ADR-0017 | [Require signed exact-revision worker execution](docs/adr/0017-require-signed-exact-revision-worker-execution.md) | Accepted |
| ADR-0018 | [Use immutable OCI packet storage and an external registry](docs/adr/0018-use-immutable-oci-packet-storage-and-an-external-registry.md) | Accepted |
| ADR-0019 | [Use idempotency, reuse, replay, and reconciliation](docs/adr/0019-use-idempotency-reuse-replay-and-reconciliation.md) | Accepted |
| ADR-0020 | [Delegate publication planning to the ingestion bridge](docs/adr/0020-delegate-publication-planning-to-the-ingestion-bridge.md) | Superseded in part by ADR-0021 |
| ADR-0021 | [Internalize publication planning and memory lowering](docs/adr/0021-internalize-publication-planning-and-memory-lowering.md) | Accepted |
| ADR-0022 | [Key memory effects by the fact, not the snapshot](docs/adr/0022-key-memory-effects-by-fact-not-snapshot.md) | Accepted |
| ADR-0023 | [Declare field cardinality before detecting conflicts](docs/adr/0023-declare-field-cardinality-before-detecting-conflicts.md) | Accepted |

## Decision order

When ADRs interact, packet and authority boundaries take precedence over deployment
mechanics. The practical order is:

1. repository role and transport;
2. canonical input and output packets;
3. evidence, identity, validation, and determinism;
4. topology algorithms and projections;
5. effect containment;
6. orchestration, storage, recovery, and downstream publication.

## Process

See `GOVERNANCE.md` for proposal, acceptance, supersession, and approval rules.
