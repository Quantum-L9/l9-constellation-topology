# Architecture

## System position

`l9-constellation-topology` is a deterministic middle-end compiler. It transforms validated repository-semantic packets into a validated repository and constellation topology packet.

```text
TransportPacket stage dispatch
        ↓
Repository Model Packet resolver
        ↓
packet, hash, receipt, and lineage validation
        ↓
versioned packet adapters
        ↓
canonical internal records
        ↓
evidence reconciliation
        ↓
repository + capability aggregation
        ↓
pure graph construction
        ↓
impact + maturity + risk projections
        ↓
topology invariants
        ↓
Topology Packet candidate
        ↓
separate Validation Receipt
        ↓
OutputSink write plan + atomic commit
        ↓
Topology Packet bundle + Commit Receipt
```

## State ownership

| State | Owner |
|---|---|
| Human declarations | Source repository |
| Artifact semantics | Repository Model Packet |
| Repository and constellation semantics | Topology Packet |
| Workflow state, retries, leases, registry | Postgres control plane |
| Accepted graph relationships | Ingestion bridge and canonical graph |
| Temporal observations and rationale | Downstream memory boundary |
| Human reports | Projection cache or packet attachments |

## Dependency direction

Domain and topology modules do not depend on CLI, workers, filesystem sinks, network clients, Neo4j, or Graphiti. Packet adapters depend on domain models. Renderers depend on packet/domain models and return bytes. Only `io/` mutates the local filesystem. Worker code orchestrates adapters and external callbacks without leaking those dependencies into compiler logic.

## Security boundary

The stage workflow authenticates the dispatch with trusted `main` worker code before using its target revision. Only a signed exact Git object ID may select executable code. The worker then revalidates TransportPacket action, repository, payload schema, profile, signature, hashes, parent receipts, and source revision against the exact checkout. Stage success is emitted only after packet publication, re-fetch, and validation succeed.

## Compatibility boundary

Legacy scanners remain read-only observation providers. `RepoCard` and old commands are compatibility interfaces, not canonical stage contracts. Their data is adapted into canonical records before compilation.
