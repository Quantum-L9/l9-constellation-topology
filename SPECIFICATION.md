# L9 Constellation Topology Specification

- **Specification ID:** `l9.constellation-topology.spec`
- **Version:** `5.0.0`
- **Implementation version:** `2.0.0`
- **Authority:** superseding packet-first contract
- **GitHub source:** `Quantum-L9/l9-constellation-topology`
- **Source commit:** `bbca641a0380f66c10dc83ff5be86669d3c94172`
- **Source blob:** `58e8d062ecbb74fe8a007f4601f82bd27631596d`


## Full build authority

The complete source-aligned build specification used for this consolidated initial
repository is preserved in [BUILD_SPECIFICATION.md](BUILD_SPECIFICATION.md).
Accepted implementation decisions are indexed in [ADR_INDEX.md](ADR_INDEX.md).
When the concise summary and full build specification differ, the full build
specification and accepted ADRs govern.

This repository implements the live GitHub design whose governing principle is:

> evidence over inference; packets over reports; planned effects over direct writes

## Required role

The compiler consumes one or more validated Repository Model Packets and, optionally, one or more Corpus Intelligence Packets analysing exactly those roots; optionally performs policy-authorized read-only observations for missing topology evidence; builds canonical repository and constellation topology plus explicitly-classed candidate topology; validates the result; and emits one immutable Topology Packet plus a separate Validation Receipt.

Corpus intelligence is auxiliary and optional. A compile given none behaves exactly as it did before the domain existed. Per [ADR-0026](docs/adr/0026-accept-corpus-intelligence-as-an-auxiliary-packet.md), it is a second input rather than a widening of the Repository Model Packet, because source observation and derived candidate analysis are different kinds of statement and the boundary is the only point at which that distinction can be made.

## Authority boundaries

### Owns

- Repository and constellation aggregation
- Capability, dependency, governance, documentation, CI, runtime, and memory topology
- Stable graph identities and edge construction
- Impact, maturity, and risk projections
- Evidence reconciliation, conflict preservation, and explicit unknowns
- Corpus and root scope above repositories
- Exact byte-identity (`DUPLICATE_OF`) and explicit work-relation compilation
- Candidate relation and cluster preservation, with deterministic structural enrichment
- Readiness measurement carried as counts, never as a score
- Deterministic reasoning routing, performing no reasoning
- Topology Packet construction and validation
- Pure report projections
- Worker-side stage execution and callback contracts
- Publication eligibility, destination-neutral memory lowering, and deterministic
  effect planning (ADR-0021)

### Does not own

- Artifact-level source understanding owned by `l9-meta-injector`
- Durable memory admission and execution owned by `l9-graphiti-memory`
- Neo4j or Graphiti writes
- Gate dispatch of the intents this repository plans
- Postgres scheduler schema or state machine
- Source-repository mutation
- Full L9 Gate availability during the foundational phase

## Canonical contracts

### Accepted control-plane payloads

- `l9.stage-dispatch/1.0.0`
- `l9.repository-model-ref/1.0.0`
- `l9.replay-request/1.0.0`
- `l9.render-request/1.0.0`
- `l9.validation-request/1.0.0`

### Emitted payloads

- `l9.topology-ref/1.0.0`
- `l9.stage-result/1.0.0`
- `l9.execution-failure/1.0.0`
- `l9.validation-receipt/1.0.0`
- `l9.render-result/1.0.0`
- `l9.reuse-receipt/1.0.0`

### Canonical stage artifacts

- Repository Model Packet input
- Topology Packet output
- Validation Receipt
- Commit Receipt
- Stage Result or Execution Failure

Reports are optional projections. They are prohibited as stage-to-stage compiler contracts.

## Compilation stages

```text
resolve configuration
→ ingest packet references
→ validate input packets
→ normalize repository models
→ perform bounded direct observation
→ reconcile evidence
→ aggregate repositories
→ classify roles
→ aggregate capabilities
→ build graph
→ calculate impact
→ assess maturity
→ assess risk
→ validate topology
→ render packet bundle
→ plan outputs
→ commit outputs
→ emit stage result
```

## Determinism

The semantic hash is derived from semantic inputs, compiler version, profile hash, schema contract hash, canonical records, and deterministic ordering. It excludes timestamps, machine-local absolute paths, transient execution IDs, and presentation ordering. Artifact hashes cover exact emitted bytes.

## Output safety

All production filesystem effects pass through `OutputSink`. Renderers return `RenderedArtifact` values. Invalid topology commits no canonical packet bundle. Every successful commit emits a `CommitReceipt`.

## Foundational deployment

Postgres owns durable workflow state and dependencies. GitHub Actions runs exact-revision workers. The topology stage is activated by the existence of a validated Repository Model Packet, not merely by upstream workflow completion.

The full Gate is not required initially. The gate-less profile requires trusted workflows, GitHub App or OIDC identity, signed control packets, exact repository and action allowlists, schema validation, and validated parent packets.

## Acceptance

The executable acceptance matrix is maintained in [docs/acceptance-matrix.md](docs/acceptance-matrix.md). External control-plane and live OCI/graph publication checks are represented as integration contracts and are not falsely reported as locally executed.
