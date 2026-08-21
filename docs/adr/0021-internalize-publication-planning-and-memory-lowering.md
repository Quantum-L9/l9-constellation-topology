# ADR-0021: Internalize publication planning and memory lowering

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`
- **Supersedes:** [ADR-0020](0020-delegate-publication-planning-to-the-ingestion-bridge.md) with respect to repository placement only

## Context

ADR-0020 assigned promotion policy, destination lowering, effect planning, and
publication receipts to a separate repository, `l9-topology-ingestion-bridge`.
That repository was never built. The separation it described was therefore not a
boundary between two running components but a gap: validated topology truth had
nowhere to go, and the only downstream-facing surface in this repository was
`export-neo4j`, a neutral candidate projection shaped by a specific graph store.

Two facts changed the calculus.

`l9-meta-injector` now emits a real `l9.repository-model` bundle that this
repository's canonical loader and adapter consume without a translation shim, so
the upstream half of the vertical slice is live rather than hypothetical.

`l9-graphiti-memory` now exposes a typed `memory.ingest` intent carrying a
`MemoryWriteRequest` with structured assertions, provenance, evidence,
confidence, temporal fields, metadata, and idempotency keys, dispatched only
through Gate. The downstream contract is concrete enough to target directly.

The remaining question was where the planning step lives, not whether the safety
rule that motivated ADR-0020 still holds.

## Decision

Publication eligibility, destination-neutral memory lowering, deterministic
effect planning, and publication-plan contracts become an internal module of
this repository at `src/l9_constellation_topology/publication/`.

The authority split that ADR-0020 protected is preserved and restated as a split
between *planning* and *execution* rather than between two repositories:

- Compilation establishes topology truth.
- Publication planning determines eligible downstream memory effects.
- Durable admission and execution remain owned by `l9-graphiti-memory`.

The safety rule of ADR-0020 survives unchanged and unweakened: this repository
contains no Neo4j client, no Graphiti client, no memory service client, no
`RecordStore` access, and no Gate dispatch. A publication plan is a document.
Producing one performs no durable effect.

The publication plan is derived, never canonical. The Topology Packet remains the
sole canonical topology output, and a plan cites the topology entities, evidence,
and Repository Model Packets it was lowered from.

The new `plan-publication` command operates on the canonical Topology Packet, not
on the `export-neo4j` rendering. Publication is therefore independent of any
particular graph store.

## Consequences

### Positive

- The vertical slice is executable end to end inside two repositories that exist.
- Lowering is validated against the actual downstream contract rather than an
  assumed one, so producer and consumer cannot drift silently.
- Publication remains graph-store independent, which keeps the Graphiti and
  world-model work unconstrained by a Neo4j-shaped intermediate.
- Eligibility, conflicts, unknowns, and skipped facts are explicit and auditable.

### Costs and constraints

- This repository now carries the downstream memory contract as a structural
  mirror, and that mirror must track the bound downstream revision. A captured
  contract descriptor under `tests/fixtures/downstream_contracts/` fails the
  build when the mirror drifts.
- Publication policy becomes a versioned artifact with its own lifecycle.
- A plan is not an authorization. Anything that later dispatches these intents
  must apply its own admission rules.

## Alternatives considered

- **Rejected:** Build `l9-topology-ingestion-bridge` as specified by ADR-0020. It
  adds a repository, a release surface, and a contract hop before any consumer
  needs the seam to be separately deployable.
- **Rejected:** Lower from the `export-neo4j` projection. That projection is
  shaped by one graph store and reports that no Neo4j client is present; building
  durable-memory semantics on it would bind memory to a store choice.
- **Rejected:** Dispatch intents directly from this repository. That would
  reverse the safety rule of ADR-0020 rather than preserve it.
- **Rejected:** Fold publication policy into `ResolvedConfiguration`. That would
  make Topology Packet semantic identity depend on publication policy, breaking
  the canonicality invariant below.

## Invariants that must survive

- The Topology Packet remains canonical topology truth.
- Publication artifacts are derived from a validated Topology Packet.
- The topology compiler remains deterministic.
- Source repositories remain read-only.
- Neo4j clients remain forbidden.
- Graphiti clients remain forbidden.
- Direct `RecordStore` mutation remains forbidden.
- Direct memory service mutation remains forbidden.
- Gate dispatch remains forbidden in this repository.
- Evidence, conflicts, and unknowns remain explicit.
- Publication policy never changes Topology Packet semantic identity.

## Compliance and validation

- The publication plan schema lives in `schemas/`, not `contracts/`. Adding it to
  `contracts/` would change `schema_contract_hash` and therefore every Topology
  Packet's semantic identity, which the canonicality invariant forbids.
- Architecture checks reject graph-client imports across `src/`.
- Tests assert that the publication module imports no graph, memory, or network
  client and performs no dispatch or direct filesystem write.
- Tests assert plan, candidate, and idempotency determinism, and that publication
  planning leaves the source Topology Packet unchanged.
- Conformance to the bound downstream revision is checked offline against a
  captured contract descriptor, and against the real
  `GateMemoryBridge.validate_intent` when `L9_GRAPHITI_MEMORY_SRC` names a
  read-only checkout.

## Related artifacts

- `.l9/publication-policy.yaml`
- `schemas/topology-publication-plan.schema.json`
- `src/l9_constellation_topology/publication/`
- `tests/fixtures/downstream_contracts/l9-graphiti-memory-contract.json`
- [ADR-0004](0004-topology-packet-is-the-canonical-output.md)
- [ADR-0007](0007-outputsink-is-the-only-write-boundary.md)
- [ADR-0009](0009-preserve-evidence-authority-conflicts-and-unknowns.md)
- [ADR-0019](0019-use-idempotency-reuse-replay-and-reconciliation.md)
- [ADR-0020](0020-delegate-publication-planning-to-the-ingestion-bridge.md)
