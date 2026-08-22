# ADR-0022: Key memory effects by the fact, not the snapshot

- **Status:** Accepted; effect-identity algorithm superseded by
  [ADR-0025](0025-separate-fact-identity-from-durable-write-identity.md)
- **Date:** 2026-08-16
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`
- **Relates to:** [ADR-0019](0019-use-idempotency-reuse-replay-and-reconciliation.md),
  [ADR-0021](0021-internalize-publication-planning-and-memory-lowering.md)

## Context

Publication identity v1 derived every memory idempotency key from the semantic
fact *plus* the whole Topology Packet semantic hash *plus* the whole publication
policy hash.

That conflated two different things. A Topology Packet is a **snapshot**: it
describes the state of the constellation at one compilation. A published memory
effect is a **fact**: it asserts something about one repository. Binding fact
identity to snapshot identity means any semantic movement anywhere — in any
source repository, in any unrelated part of the graph — re-keys every effect in
the plan.

End-to-end requalification demonstrated the failure directly. A legitimate change
to `l9-meta-injector` altered the Repository Model Packet hash, which altered the
topology semantic hash, which altered all 27 publication idempotency keys — while
a separate topology-only provenance fix, which changed no published fact,
correctly changed 0 of 27. The keys were tracking the wrong thing.

Because `l9-graphiti-memory` honours a caller-supplied idempotency key and
returns the existing record on duplicate admission, this is not cosmetic
metadata. The key directly controls durable duplicate behaviour downstream.
Under v1, every unrelated edit anywhere would have re-admitted the entire corpus
as new facts.

Two conditions made this the moment to change it. Qualification produced zero
external memory effects and zero graph effects, so no durable state depends on v1
keys. And no live corpus yet exists to migrate.

## Decision

Memory-effect identity is **fact-local**.

A candidate's semantic identity comprises only what the effect *is*: operation,
candidate kind, namespace, memory class, normalized content, structured
assertion, and the topology entity ids it was lowered from. The idempotency key
is derived from that identity plus the lowering contract version, under an
explicit domain separator, and is prefixed `l9-topology-publication/v2:`.

Excluded from identity, deliberately and by test: the Topology Packet id and
semantic hash, Repository Model Packet ids and hashes, the publication plan id
and semantic hash, the publication policy hash, and every timestamp.

Those identifiers are **retained as provenance** on every intent — in request
metadata and in `MemoryProvenance` — because they describe where a fact was
observed, not which fact it is.

Packet-level semantic hashes are unchanged and must keep changing when their
semantic content changes. Snapshot hashes describe snapshots; effect identity
describes facts. This decision separates the two; it does not freeze either.

A policy change is not by itself a reason to re-key. If a policy change alters
actual effect semantics — namespace, memory class, content, assertion, or
eligibility — those changes already flow into candidate identity on their own. If
it alters nothing an effect asserts, the effect has not changed and keeps its
key. The plan hash still records the policy revision.

This supersedes no ADR. ADR-0019 governs stage-dispatch idempotency, a different
key with a different job: it binds a whole compilation fingerprint because it
governs compilation *reuse*. That key is unchanged.

## Consequences

### Positive

- An unrelated edit no longer re-admits unchanged facts downstream.
- A changed fact still produces a new key, so real updates are still visible.
- Effect identity is now checkout-path independent, wall-clock independent, and
  independent of unrelated snapshot movement.
- The `/v2` marker makes the algorithm explicit on the wire, so a v1 key and a v2
  key can never be silently confused.

### Costs and constraints

- This is a one-time breaking change to key derivation. It is safe only because
  no durable environment has consumed v1 keys. If evidence emerges that v1 keys
  reached durable state, that is a halt-and-report condition, not a silent
  migration.
- Callers can no longer infer the producing snapshot from the key. They must read
  provenance metadata instead, which is where that information belongs.

## Alternatives considered

- **Rejected:** Keep v1 and accept the blast radius. It makes every publication
  a full re-admission and defeats idempotency downstream.
- **Rejected:** Freeze the topology semantic hash so keys stay stable. This
  breaks snapshot identity to fix fact identity, and would hide real semantic
  change.
- **Rejected:** Exclude only the policy hash and keep the topology hash. The
  topology hash is the dominant source of the blast radius.
- **Rejected:** Version the key by plan generation counter. A counter is not
  derived from the fact and reintroduces snapshot coupling under another name.

## Invariants that must survive

- Repository Model, Topology, and publication-plan semantic hashes still change
  when their own semantic content changes.
- An unchanged fact retains its candidate id and idempotency key across
  unrelated Repository Model, Topology, or plan changes.
- A changed published fact changes both its candidate id and its key.
- Wall-clock time never participates in effect identity.
- Global snapshot identifiers remain present as provenance on every intent.
- Distinct facts never collide on one key.
- Publication planning still dispatches nothing.

## Compliance and validation

- `tests/test_publication_effect_identity.py` asserts fact-local identity,
  including that moving the Topology Packet semantic hash leaves every unchanged
  candidate id and idempotency key untouched, and that no global or volatile
  field appears in the identity payload.
- Parametrized tests assert that each of operation, namespace, memory class,
  content, assertion, candidate kind, and source entity ids changes identity.
- `tests/test_publication_planning.py` asserts that a bare policy revision does
  not re-key unchanged facts while a namespace change does.
- Provenance retention is asserted against request metadata and
  `MemoryProvenance` for every candidate.
- `scripts/verify_determinism.py` continues to gate plan, candidate, and key
  determinism across differing execution timestamps.

## Related artifacts

- `src/l9_constellation_topology/publication/identity.py`
- `src/l9_constellation_topology/publication/lowering.py`
- `src/l9_constellation_topology/publication/contracts.py`
- `tests/test_publication_effect_identity.py`
- `tests/test_publication_planning.py`
- `docs/publication-boundary.md`
- [ADR-0009](0009-preserve-evidence-authority-conflicts-and-unknowns.md)
- [ADR-0019](0019-use-idempotency-reuse-replay-and-reconciliation.md)
- [ADR-0021](0021-internalize-publication-planning-and-memory-lowering.md)
- [ADR-0023](0023-declare-field-cardinality-before-detecting-conflicts.md)
