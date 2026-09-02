# ADR-0027: Separate observation time from publication time, and do not retract on absence

**Status:** Accepted
**Extends:** [ADR-0021](0021-internalize-publication-planning-and-memory-lowering.md),
[ADR-0025](0025-separate-fact-identity-from-durable-write-identity.md)

## Context

A published fact carried one temporal coordinate: `valid_from`, set to the
moment the plan was built. Nothing recorded when the fact was *seen*. A
dependency declared in a `pyproject.toml` committed months ago and a dependency
added this morning arrived downstream with the same validity start, and a reader
could not tell them apart.

The larger question behind it is retraction. Topology emits only
`memory.ingest`; `supersedes` is empty by construction and `valid_to` is never
set. A fact that leaves the corpus — a deleted file, a dropped dependency, a
retracted ADR — stays current in durable memory and stays projected, forever.
Two compiles of a shrinking corpus produce a monotonically growing graph.

The tempting fix is to treat absence as retraction: compile, diff against what
memory currently holds for the scope, and close whatever the new compile did not
produce. This decision refuses that, and says what would have to be true first.

## Decision

### Observation time is lowered; publication time stays what it is

`source_observed_at` now carries the earliest `created_at` among the evidence
records supporting a fact. The downstream contract has had the field all along.

`valid_from` remains publication time and is not redefined. The two answer
different questions — when the fact was seen, and when this compiler stated it —
and a fact can legitimately be published long after it was observed.

A fact with no resolved evidence carries no `source_observed_at`. Publication
time is not a substitute for an observation that did not happen.

Neither field participates in effect identity, so nothing is re-keyed. An
unchanged fact re-published keeps its original `valid_from` because its
idempotency key is unchanged and the write answers `DUPLICATE` — the record is
not rewritten, so its validity start cannot drift. That invariant is a
consequence of ADR-0025's identity separation, not a new rule.

### Absence does not retract

**A fact missing from a compile MUST NOT close a fact in durable memory.**

Retraction requires knowing that a compile observed a scope *exhaustively*. Two
facts about this pipeline say it does not:

- The Repository Model Packet carries no scope-level completeness assertion. Its
  only completeness axis is `ConfidenceAssessment.completeness`, which grades an
  individual record, not the coverage of a scan.
- The producer's own repository record is fixed at `completeness: "partial"`,
  deliberately, and a documented resource budget bounds what an observation
  expands into. The producer does not claim exhaustiveness because it does not
  have it.

So absence in a compile is ambiguous between "this fact is gone" and "this run
did not look there". Under that ambiguity, absence-based retraction closes true
facts, silently, in proportion to how partial the scan was — and the failure is
invisible, because a closed fact and an unobserved one look identical
afterwards. A monotonically growing graph is a known, bounded, correctable
problem. Silent deletion of true history is not.

`validate_topology` already refuses to commit a failed compile, so a *failed*
run cannot retract anything. That is necessary and not sufficient: a
*successful* compile over a subset is exactly the dangerous case, and nothing
currently distinguishes it from a complete one.

## What would unblock retraction

Retraction becomes implementable when a compile can state its own coverage. In
dependency order:

1. **The producer declares scope completeness.** `l9.repository-model` gains an
   explicit assertion — per repository — that the observation was exhaustive
   under a named policy, together with what it deliberately excluded and what
   the resource budget truncated. A run that cannot assert it says so, and that
   run is never a retraction authority.
2. **Topology carries the declaration into the packet**, so the scope a compile
   claims authority over is part of what the packet means and is bound by its
   semantic hash.
3. **The plan gains a retraction disposition** naming that scope, the facts it
   observed within it, and the publication time to close absent facts at.
   Retraction stays temporal: `valid_to`, never a destructive delete. Ordinary
   corpus lifecycle is not a privacy erasure and must not borrow that path's
   authority.
4. **Memory gains a temporal-close operation** keyed by `publication_candidate_id`,
   idempotent under replay, and refusing any plan whose declared scope is not
   complete.

Until step 1 exists, the remaining steps have nothing trustworthy to act on.
Building them first would produce a mechanism whose only missing part is the one
that decides whether it is safe to fire.

## Consequences

- A published fact now states when it was observed, not only when it was said.
- Durable memory still grows monotonically. Facts that leave the corpus remain
  current until retraction is unblocked, and consumers must not read "present in
  memory" as "present in the corpus today".
- The gap is recorded here rather than closed with a rule that would delete true
  history whenever a scan came back short.

## Alternatives considered

**Retract on absence, guarded by validation status.** A failed compile already
commits nothing, so only successful compiles could retract. Rejected: the
dangerous case is a *successful* compile over a subset, which is
indistinguishable from a complete one. The guard blocks the case that was
already safe.

**Retract on absence, scoped to namespaces the compile touched.** Narrower —
a compile over two repositories could not close facts about a third. Rejected
for the same reason one level down: it does not distinguish observing a
repository fully from observing part of it, and the producer's resource budget
makes partial observation of a single root ordinary rather than exceptional.

**Infer completeness from `ConfidenceAssessment.completeness`.** Rejected: that
axis grades one record's evidence, not a scan's coverage, and the producer's
repository record is fixed at `partial` by design. Reading it as a scope claim
would invert its meaning.

**Set `valid_to` on every republication and re-open surviving facts.** Every
compile would close and reopen the whole scope, so a fact's history would record
compiler runs rather than anything about the fact. Rejected: it destroys the
temporal signal it appears to provide, and it re-keys every write on every run.

**Use the privacy deletion path for corpus lifecycle.** Rejected: deletion is
destructive, requires ADMIN plus an out-of-band verification reference, and
produces a tombstone. Ordinary corpus lifecycle is not an erasure request and
must not borrow that authority.

**Redefine `valid_from` as observation time.** Rejected: publication time is a
real coordinate that something must carry, and overwriting it would leave the
pipeline unable to say when a fact was stated. Both are kept because they answer
different questions.

## Compliance and validation

- `tests/test_publication_temporal.py` proves evidence-backed facts carry an
  observation time, that an unsupported fact claims none, that observation time
  is not merely a copy of publication time, and that no candidate requests a
  retraction.
- The same suite proves republishing an unchanged fact at a later time moves
  neither its `candidate_id` nor its `idempotency_key`, which is what keeps its
  `valid_from` from drifting.
- `tests/test_publication_downstream_conformance.py` keeps `source_observed_at`
  within the bound downstream contract.
- Effect identity excludes both temporal fields, so `tests/fixtures/publication_identity/golden-vectors.json`
  is unaffected and proves it.

## Related artifacts

- `src/l9_constellation_topology/publication/lowering.py`
- `tests/test_publication_temporal.py`
- [`ADR-0021`](0021-internalize-publication-planning-and-memory-lowering.md)
- [`ADR-0025`](0025-separate-fact-identity-from-durable-write-identity.md)
- `l9-graphiti-memory`: `contracts/temporal.py`, `services/memory_service.py`
