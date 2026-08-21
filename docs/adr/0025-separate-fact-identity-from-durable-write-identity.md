# ADR-0025: Separate fact identity from durable write identity

- **Status:** Accepted
- **Date:** 2026-08-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`
- **Supersedes the effect-identity algorithm of:**
  [ADR-0022](0022-key-memory-effects-by-fact-not-snapshot.md)
- **Relates to:** [ADR-0021](0021-internalize-publication-planning-and-memory-lowering.md),
  [ADR-0024](0024-compile-repository-model-assertions-into-semantic-claims.md)

## Context

ADR-0022 removed the whole topology semantic hash and the whole publication
policy hash from the memory-effect idempotency key, and it was right to. Under
v1, a semantic change anywhere in the constellation re-keyed every effect in the
plan and downstream re-admitted unchanged facts as new ones.

v2 then made the mirror mistake.

Downstream, `idempotency_key` names an **operation**, not a fact.
`MemoryService._operation_identity` treats a supplied key as the retry identity
of a write; a request whose key matches an existing record is answered
`WriteStatus.DUPLICATE` and its content is never admitted. The key is the
question "is this the same write you already performed?"

v2 answered that question with the fact alone. So a re-publication of an
unchanged fact with materially stronger evidence, or weaker evidence, or a
recalibrated confidence score, carried the *previous* key — and downstream read a
genuinely new epistemic state as a retry of the old one and discarded it. The
result is a durable record that keeps claiming a confidence and an evidence basis
the pipeline has since revised, with no error anywhere to show for it.

Both failures are the same category error in opposite directions: treating one
identity as if it were the other. v1 made the fact identity too global; v2 made
the write identity too narrow.

## Decision

Two identities, named separately, each answering its own question.

**`candidate_id` names the logical fact.** Operation, candidate kind, namespace,
memory class, canonical content, structured assertion, and the stable topology
entity identifiers it was lowered from. Evidence strength, confidence strength,
packet hashes, repository revisions, and timestamps are all excluded, so the fact
keeps its identity while what is known *about* it changes.

**The effect key names the exact durable admission requested.** It is
`H("l9.memory-effect-id/v3", candidate_id, local_evidence_semantics,
confidence_semantics, lowering_contract_version)`, where:

- *local evidence semantics* is, per supporting record, its evidence kind, the
  digest of the source content it reads, and a stable source locator — the path,
  never the packet id, the repository revision, or the topology evidence id, each
  of which moves when the surrounding snapshot moves while the bytes supporting
  the fact stay identical. The set is sorted, so resolution order cannot re-key.
- *confidence semantics* is the score, method, evidence count, and confidence
  policy version — every field of `MemoryConfidence` the request actually asks
  downstream to store, minus `calibrated_at`.

Explicitly excluded from the key: `observed_at`, `calibrated_at`,
`published_at`, the topology packet id and semantic hash, the publication plan id
and hash, the whole repository-model hash, the repository revision when the local
source bytes are unchanged, the evidence of unrelated facts, and the checkout
path. These stay on the intent as provenance, which is what they describe.

**Supersession stays downstream.** Topology does not know downstream record
UUIDs and must not invent them, so `MemoryWriteRequest.supersedes` stays empty. A
new effect key means "a new operation", not "replace record X". Request metadata
carries `publication_candidate_id` so a later execution layer can correlate
successive operations on one fact and resolve supersession against durable state.

## Consequences

- A re-publication carrying revised evidence or confidence is admitted as the new
  epistemic state it is, instead of being collapsed onto the previous write.
- A new commit that does not touch the bytes supporting a fact does not re-key
  the write, even though the topology evidence identities genuinely change.
- A publication policy *version* bump now re-keys every effect, because
  `Confidence.policy_version` is a field of the request. This is a deliberate
  reversal of one v2 property: relabelling the rules that produced a stored
  confidence is a different request, and reusing the key would leave the
  superseded version stamped on the record.
- The recorded hash-locality matrix carries every case in both directions, so a
  future change cannot satisfy the "must move" rows by re-keying on something
  global again — the failure v1 was, wearing v3's number.

## Migration

Changing the algorithm rewrites every key this repository emits, so adoption
depended on a claim that had to be checked rather than assumed: no v2 key has
reached durable memory.

`EFFECT_IDENTITY_MIGRATION_PREFLIGHT.json` records that check and its evidence —
no dispatch surface exists here, no committed artifact carries a v2 key, the
bound downstream revision holds no trace of this repository's idempotency
namespace, and no automation invokes the publication planner.
`tests/test_effect_identity_migration_preflight.py` re-checks the structural half
against the current tree, so the claim stays true rather than being true once.

Had durable v2 dispatch been found, the correct outcome was to halt and produce a
migration plan; live inspection and migration of durable memory are outside this
repository's authority either way.

## Alternatives considered

**Keep v2 and let downstream detect the revision.** Rejected: downstream cannot.
A duplicate key short-circuits admission before content is examined, so the new
evidence and confidence are never seen. Detection would have to happen before the
key is compared, which is where this repository already is.

**Mix the whole topology or plan hash back in.** Rejected: that is v1. It moves
the key when the epistemic state changes, but it also moves it for every
unrelated change anywhere, which re-admits the entire corpus as new facts.

**Key on the topology evidence identities.** Rejected: `evidence_id` incorporates
`source_ref.source_revision`, so an ordinary commit that never touched the
supporting file would re-key the write. The digest of the source content and its
path carry the same information without the coupling, which the
`source_repository_revision_only_with_same_local_content` case demonstrates.

**Have topology populate `supersedes`.** Rejected: it would require fabricating
downstream record UUIDs. Correlation is carried instead, and resolution stays
where the durable state is.

## Compliance and validation

- `HASH_LOCALITY_EVALUATION.json` records seventeen controlled perturbations and
  what each moved, and `tests/test_hash_locality.py` asserts every verdict rather
  than accepting a regenerated file. The matrix covers both directions, including
  a check that a case which must re-key one write re-keys exactly one — so the
  "must move" rows cannot be satisfied by keying on something global again.
- `tests/test_publication_effect_identity.py` pins the separation directly: the
  fact identity ignores evidence and confidence entirely, while a change to
  supporting evidence, its digest, its path, its kind, the confidence score,
  method, evidence count, or confidence policy version each produce a different
  write.
- `tests/test_effect_identity_migration_preflight.py` re-checks the structural
  claims behind `EFFECT_IDENTITY_MIGRATION_PREFLIGHT.json` against the current
  tree.

## Related artifacts

- `src/l9_constellation_topology/publication/identity.py`
- `src/l9_constellation_topology/publication/lowering.py`
- `EFFECT_IDENTITY_MIGRATION_PREFLIGHT.json`
- `HASH_LOCALITY_EVALUATION.json`
- `docs/publication-boundary.md`
- [ADR-0019](0019-use-idempotency-reuse-replay-and-reconciliation.md)
- [ADR-0021](0021-internalize-publication-planning-and-memory-lowering.md)
- [ADR-0022](0022-key-memory-effects-by-fact-not-snapshot.md)
