# Publication boundary

The publication boundary converts validated topology truth into a deterministic
plan of downstream `memory.ingest` intents. It is defined by
[ADR-0021](adr/0021-internalize-publication-planning-and-memory-lowering.md),
which supersedes [ADR-0020](adr/0020-delegate-publication-planning-to-the-ingestion-bridge.md)
on repository placement only.

Planning is not execution. This repository contains no Neo4j client, no Graphiti
client, no memory service client, and no Gate dispatch. Producing a publication
plan performs no durable effect.

## Position in the pipeline

```text
repository reality
  → l9-meta-injector            → l9.repository-model
  → l9-constellation-topology   → l9.topology (canonical)
  → publication/                → l9.topology-publication-plan (derived)
  → l9-graphiti-memory          → durable admission (downstream authority)
```

## Canonicality

The Topology Packet is canonical. The publication plan is derived. A plan adds no
facts: every candidate cites the topology entity identifiers, evidence
identifiers, and Repository Model Packet identifiers it was lowered from, and
publication policy is resolved and hashed independently of `ResolvedConfiguration`
so that it can never change Topology Packet semantic identity.

## Command

```bash
l9-topology plan-publication \
  --repo-root . \
  --input-bundle <topology-bundle> \
  --out <publication-plan-bundle>
```

The output bundle contains `publication-plan.json`, `intents/memory-ingest.json`
carrying only eligible intents, and `manifest.json` with content hashes.

## Policy

`.l9/publication-policy.yaml` is versioned and hashed into every plan. It selects
which entity kinds and edge types are eligible, maps topology confidence and
evidence to their downstream equivalents, and sets the fail-closed switches.

Facts the policy does not select are recorded in `skipped_candidates` with a
reason. Nothing is dropped silently.

## Eligibility

Every candidate carries a status and the reasons behind it.

| Status | Meaning |
|---|---|
| `eligible` | Admitted for downstream dispatch by some other component |
| `held` | Blocked by unresolved evidence, conflict, or unknown |
| `rejected` | Structurally inadmissible under the active policy |

Fail-closed rules:

- Topology whose validation status is not `passed` produces no plan at all.
- Missing Repository Model Packet lineage rejects every candidate.
- A relationship endpoint that resolves to no known topology entity is rejected.
- A conflict on a field the candidate actually consumed holds it. A conflict on
  any other field is preserved on the lowering receipt and in intent metadata but
  does not hold the candidate.
- An unknown on a consumed field, or on the subject as a whole, holds the
  candidate.
- A confidence method that requires evidence, with no resolved topology evidence
  behind it, holds the candidate.

Materiality is computed from the fields the lowering actually read, recorded as
`source_fields` on the lowering receipt, so it cannot drift from the lowering.

## Lowering

| Topology | Downstream |
|---|---|
| Repository and capability entities | `MemoryWriteRequest` with memory class `observation` |
| Eligible edges | `MemoryWriteRequest` with memory class `semantic` and a structured subject/predicate/object assertion |
| Evidence records | `EvidenceRef` with the kind mapped from evidence class |
| Confidence assessment | `Confidence` with an explicit score ceiling and method |
| Packet and repository identity | `Provenance` with source digest and transformation lineage |

Confidence is never upgraded. The score is the minimum of the level mapping and
the conflict-status ceiling.

When a mapped confidence method is `inferred` or `aggregated`, downstream
admission requires evidence of kind `inference`, `aggregation`, or
`source_excerpt`. Lowering attaches one additional reference describing the
derivation the compiler actually performed, alongside the lowered source
evidence. If there is no underlying topology evidence at all, the candidate is
held rather than given a manufactured basis.

## Determinism

The same Topology Packet and the same policy always produce the same plan
semantic hash, the same candidate identifiers, and the same idempotency keys.
Wall-clock time and checkout paths never participate in semantic identity;
timestamp-bearing fields are stripped before hashing. Candidate, skip, and
evidence order are stable.

An idempotency key binds the semantic fact to the topology semantic identity and
the policy identity. A fact republished from a newer Topology Packet therefore
carries a new key, and downstream treats it as a distinct admission rather than a
duplicate.

## Downstream conformance

Two layers guard the seam against drift:

- An offline structural check against
  `tests/fixtures/downstream_contracts/l9-graphiti-memory-contract.json`, a
  descriptor captured from the bound downstream revision. It runs in CI.
- A live check against the real `GateMemoryBridge.validate_intent`, enabled by
  pointing `L9_GRAPHITI_MEMORY_SRC` at a read-only checkout:

```bash
L9_GRAPHITI_MEMORY_SRC=/path/to/l9-graphiti-memory/src \
  uv run pytest tests/test_publication_downstream_conformance.py
```

The live check validates types. It never dispatches, never calls the memory
service, never writes a record store, and never projects to Graphiti.
