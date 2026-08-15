# Architecture

## Repository identity

`l9-constellation-topology` is the deterministic middle-end compiler in the
foundational L9 repository-intelligence pipeline. It transforms validated
Repository Model Packets into one validated immutable Topology Packet.

```text
source repositories
        ↓
l9-meta-injector
        ↓ Repository Model Packet(s)
l9-constellation-topology
        ├─ compiler    → Topology Packet + Validation Receipt
        └─ publication → publication plan + memory.ingest intents
                            ↓ (planned, never dispatched here)
                     l9-graphiti-memory
                            ↓ durable admission and execution
```

Per [ADR-0021](docs/adr/0021-internalize-publication-planning-and-memory-lowering.md),
publication planning is an internal boundary of this repository. Planning decides
which topology facts are eligible to become durable memory; it never performs the
write. Durable admission remains owned by `l9-graphiti-memory`.

## Architectural laws

1. `TransportPacket` is the only control-plane envelope.
2. Repository Model Packets are the canonical semantic inputs.
3. The Topology Packet is the sole canonical machine output.
4. Reports are optional projections and never stage contracts.
5. Evidence, conflicts, and unknowns remain explicit.
6. Semantic identity excludes timestamps and machine-local paths.
7. Graph construction and analytical stages are pure.
8. All filesystem effects pass through `OutputSink`.
9. Source repositories are read-only during topology compilation.
10. Neo4j and Graphiti writes remain outside this repository. Publication is
    planned here and executed downstream; a publication plan is a document, and
    producing one performs no durable effect.
11. Publication artifacts are derived from a validated Topology Packet and never
    become an alternate source of topology truth.

## Compiler pipeline

```text
resolve configuration
→ resolve and validate packet references
→ adapt supported packet versions
→ perform policy-authorized bounded observations
→ reconcile evidence
→ aggregate repositories and capabilities
→ construct stable graph records and flows
→ calculate impact
→ assess maturity and risk from versioned profiles
→ validate schemas, invariants, evidence, and lineage
→ render the packet bundle
→ plan and commit through OutputSink
→ emit stage result or execution failure
```

## Publication pipeline

```text
load validated Topology Packet bundle
→ resolve versioned publication policy
→ select eligible entities and relationships
→ lower topology facts to memory.ingest intents
→ decide eligibility (eligible, held, rejected) and record why
→ build a deterministic publication plan
→ validate against the publication plan schema
→ commit through OutputSink
```

## State ownership

| State | Authority |
|---|---|
| Human declarations | Source repository |
| Artifact semantics | Repository Model Packet |
| Repository and constellation semantics | Topology Packet |
| Validation decision | Separate Validation Receipt |
| Workflow state, retries, leases, registry | External Postgres control plane |
| Publication eligibility and memory lowering | `publication/` module in this repository |
| Publication policy | `.l9/publication-policy.yaml`, versioned independently of compiler profiles |
| Durable memory admission and execution | `l9-graphiti-memory` |
| Human reports | Projection cache or packet attachments |

## Dependency direction

Domain, topology, validation, and renderer modules do not depend on workers,
network clients, database SDKs, or direct filesystem mutation. Packet adapters
translate external versions into the canonical internal model. Worker code may
orchestrate packet stores and callbacks, but cannot redefine compiler semantics.

## Detailed references

- [Full build specification](BUILD_SPECIFICATION.md)
- [ADR index](ADR_INDEX.md)
- [Detailed architecture](docs/architecture.md)
- [Packet contracts](docs/packet-contracts.md)
- [Publication boundary](docs/publication-boundary.md)
- [Evidence model](docs/evidence-model.md)
- [Topology model](docs/topology-model.md)
- [OutputSink](docs/output-sink.md)
- [Worker contract](docs/worker-contract.md)
- [Deployment](docs/deployment.md)
- [Recovery](docs/recovery.md)
