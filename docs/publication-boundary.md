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

## Effect identity

Three identities are separated, and conflating them is a correctness problem
rather than a naming one.

| Identity | Scope | Moves when |
|---|---|---|
| Snapshot | `topology_semantic_hash`, `publication_plan_semantic_hash` | anything in the compiled snapshot moves |
| Candidate | `candidate_id` | the logical fact's own meaning moves |
| Effect | `idempotency_key` | the requested durable write's own semantics move |

The effect key is computed by algorithm `v2`, and the algorithm version is encoded
in the key's namespace (`l9-topology-publication/v2:…`) so a `v1` key and a `v2`
key can never be confused downstream.

The `v1` algorithm bound every effect to the whole Topology Packet hash and the
whole publication policy hash. That made the key correct for exactly one question
— "did anything anywhere change?" — and wrong for the question idempotency
actually asks. Any commit to any file in a scanned repository re-keyed every
otherwise unchanged fact, which downstream would admit as a fresh durable record.

`v2` keys an effect on its own semantics:

**Included** — the operation, the destination namespace and memory class, the
canonical content, the structured assertion, the stable identity of the source
fact, the normalized confidence semantics, the normalized evidence semantics, and
the lowering contract version.

**Excluded** — the Topology Packet id and semantic hash, the Repository Model
Packet semantic hash, the publication plan id and semantic hash, the whole
publication policy hash, the repository-wide source revision when local evidence
is unchanged, every wall-clock stamp, checkout paths, and any container's artifact
hash. All of these remain on the candidate as provenance and in intent metadata;
they simply do not decide whether two requested writes are the same write.

Evidence is bound by *local* semantic identity — evidence kind, the exact digest
of the content it was read from, a bounded locator within that source, and the
derivation identity where the compiler derived the fact itself. Upstream evidence
identifiers are deliberately excluded because they embed the whole-repository
revision, which would reintroduce the global coupling this algorithm removes.

Two consequences follow, and both are intended:

- `candidate_id` can hold while the effect key moves. A materially changed
  confidence or evidence basis for the same logical fact is a different durable
  write.
- A repository entity's published content states what is true of the repository,
  not which commit it was read at. The revision is carried in provenance and in
  `metadata.source_revisions` instead, so a published record can still say which
  revision it was observed at without being re-keyed by unrelated churn.

`HASH_LOCALITY_EVALUATION.json` records the evaluated locality of every case
above and is regenerated by `make hash-locality-update`; `make hash-locality`
fails the build when recorded locality drifts.

### Migration from v1

No durable admission has ever been performed with a `v1` key. This repository has
never contained a dispatch path: `plan-publication` produces a document, and
ADR-0021 records the same constraint. Adopting `v2` therefore introduces no
duplicate durable records and requires no downstream migration. If a `v1` key had
reached durable storage, replacing the algorithm would have required a migration
design rather than a version bump.

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
