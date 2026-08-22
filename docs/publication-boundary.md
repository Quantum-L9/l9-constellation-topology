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
  candidate. A semantic claim consumes its own predicate, so a conflict or
  unknown recorded against that predicate holds exactly the claims that depend on
  it and no others.
- A claim whose predicate the predicate registry does not declare is held under
  `predicate.unsupported_by_registry`. It is preserved and evidenced; what is
  withheld is its meaning, and the reason is named rather than implied.
- A confidence method that requires evidence, with no resolved topology evidence
  behind it, holds the candidate.

Materiality is computed from the fields the lowering actually read, recorded as
`source_fields` on the lowering receipt, so it cannot drift from the lowering.

## Lowering

| Topology | Downstream |
|---|---|
| Repository and capability entities | `MemoryWriteRequest` with memory class `observation` |
| Eligible edges | `MemoryWriteRequest` with memory class `semantic` and a structured subject/predicate/object assertion |
| Semantic claims | `MemoryWriteRequest` with memory class `semantic` whose assertion is the claim verbatim |
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

Two identities are separated here, and confusing them in either direction has
already produced a real defect.

**The candidate identity names the fact.** It is derived from the effect's own
semantics — operation, namespace, memory class, normalized content, structured
assertion, and the topology entities it came from. Nothing about how strongly the
fact is known reaches it, so a fact keeps its identity while its evidence and
confidence are revised.

**The effect key names the exact durable write being requested.** Downstream,
`idempotency_key` is the retry identity of an operation: a request whose key
matches an existing record is answered `DUPLICATE` and its content is never
admitted. So the key is the candidate identity *plus* the lowering contract
version, the local evidence supporting this fact, and the confidence claimed for
it. It is prefixed `l9-topology-publication/v3:` so the algorithm that produced
it is explicit on the wire.

Local evidence contributes its kind, the digest of the source content it reads,
and a stable source locator — the path, never the packet id, the repository
revision, or the topology evidence id. Confidence contributes score, method,
evidence count, and confidence policy version.

Nothing that describes the *snapshot* participates. The Topology Packet id and
semantic hash, the Repository Model Packet ids, the publication plan identity,
the whole policy hash, the repository revision when local source bytes are
unchanged, the evidence of unrelated facts, and every timestamp are deliberately
excluded. They remain on every intent as provenance, in request metadata and in
`MemoryProvenance`, which is what they actually describe: where a fact was
observed, not which fact it is, and not how well it is known.

The consequences, all intended:

- A change elsewhere in the constellation moves the Repository Model, topology,
  and plan hashes while leaving untouched facts' keys alone, so downstream
  recognizes them as the duplicates they are.
- A change to what a fact asserts produces a new candidate identity and a new
  key, so downstream admits it as the new fact it is.
- A change to the evidence or confidence behind an unchanged fact keeps the
  candidate identity and produces a new key, so downstream admits the revised
  epistemic state instead of discarding it as a retry.
- A new commit that does not touch the bytes supporting a fact re-keys nothing,
  even though the topology evidence identities themselves change.

This is identity v3. v1 mixed the whole topology and policy hashes into every
key, so any change anywhere re-keyed everything. v2 removed them and keyed by the
fact alone, which made every revision of evidence or confidence look like a retry
of the previous write. [ADR-0025](adr/0025-separate-fact-identity-from-durable-write-identity.md)
records the decision, and `EFFECT_IDENTITY_MIGRATION_PREFLIGHT.json` records the
check that no v2 key ever reached durable memory.

Supersession stays downstream. Topology does not know downstream record
identifiers and never invents them, so `supersedes` is always empty; request
metadata carries `publication_candidate_id` instead, so a later execution layer
can correlate successive operations on one fact against durable state.

`HASH_LOCALITY_EVALUATION.json` records the full matrix — every case that must
move an identity and every case that must not — and its verdicts are asserted by
`tests/test_hash_locality.py` rather than merely regenerated.

Note that this is a different key from the stage-dispatch idempotency key
described in [recovery.md](recovery.md), which binds a whole compilation
fingerprint because it governs compilation reuse rather than fact identity.

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
