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
        ↓ Topology Packet + Validation Receipt
l9-topology-ingestion-bridge
        ↓ candidate and publication plans
```

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
10. Neo4j and Graphiti publication remain outside this repository.

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

## State ownership

| State | Authority |
|---|---|
| Human declarations | Source repository |
| Artifact semantics | Repository Model Packet |
| Repository and constellation semantics | Topology Packet |
| Validation decision | Separate Validation Receipt |
| Workflow state, retries, leases, registry | External Postgres control plane |
| Publication eligibility and graph lowering | `l9-topology-ingestion-bridge` |
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
- [Evidence model](docs/evidence-model.md)
- [Topology model](docs/topology-model.md)
- [OutputSink](docs/output-sink.md)
- [Worker contract](docs/worker-contract.md)
- [Deployment](docs/deployment.md)
- [Recovery](docs/recovery.md)
