# ADR-0023: Declare field cardinality before detecting conflicts

- **Status:** Accepted
- **Date:** 2026-08-16
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`
- **Relates to:** [ADR-0022](0022-key-memory-effects-by-fact-not-snapshot.md)

## Context

Evidence reconciliation treated any subject/field group holding more than one
distinct value as a conflict. The rule was purely numeric: plurality implied
contradiction.

That is wrong for most of the fields this repository actually models. The frozen
domain records are full of tuple-typed members — `languages`,
`package_managers`, `workflows`, `adr_refs`, `governance_refs`, `capability_ids`,
`artifact_ids`, `upstream_repository_ids`, and more. Two scanners reporting
`python` and `shell` for `languages` are not disagreeing; they are each reporting
part of a true set. `aggregate_repositories` already understood this and unioned
such fields, so the pipeline simultaneously aggregated a field downstream and
reported it as contradictory upstream.

The consequence was manufactured conflicts. Because conflict status feeds the
confidence ceiling and publication eligibility, a repository could be held back
from publication for "contradicting itself" about a set it merely had several
members of. `upstream_repository_ids` — a set-valued field — was already being
emitted as evidence and was subject to exactly this false positive.

The inverse failure matters too. Assuming an undeclared field is single-valued
invents contradictions nobody observed; assuming it is set-valued hides real
ones.

## Decision

Cardinality is **declared**, versioned, and consulted before any conflict is
recorded.

`cardinality.py` declares each known field as `SINGLE` or `SET`, grounded in the
frozen domain records rather than guessed. Reconciliation then branches:

- **`SET`** — distinct values agree. They aggregate downstream and no conflict is
  recorded.
- **`SINGLE`** — distinct values are mutually exclusive claims about one fact.
  A `ConflictRecord` is recorded carrying every competing value and every
  contributing evidence reference.
- **`UNKNOWN`** — the contract does not declare this field. An `UnknownRecord` is
  recorded instead. Divergence is preserved and surfaced; it is neither resolved
  by guessing nor promoted into a conflict that was never observed.

The contract carries an id and version, and that version joins
`active_contract_versions`, so it participates in compiler identity. This is
required rather than incidental: the same evidence reconciled under a different
cardinality declaration yields a different conflict set, and therefore different
topology truth.

Conflicts remain non-destructive. A conflict records the competing values; it
never deletes the weaker claim. A stale statement and a current one both survive
with their sources intact, and deciding between them stays a downstream concern.

## Consequences

### Positive

- Set-valued fields stop generating false conflicts, so confidence ceilings and
  publication eligibility reflect real disagreement.
- Genuine single-valued contradictions remain detected and blocking-capable.
- Undeclared fields produce an honest unknown rather than a fabricated conflict.
- Reconciliation intent is now explicit and reviewable in one declaration
  instead of implicit in a length check.

### Costs and constraints

- Adding a field to a domain record without declaring its cardinality yields
  unknowns rather than conflicts. That is the intended fail-safe direction, but
  it means the declaration must be maintained alongside the domain records.
- Changing the declaration changes compiler identity, which is correct and
  deliberate, but means cardinality edits are not free.

## Alternatives considered

- **Rejected:** Infer cardinality from the domain record's Python type at
  runtime. It couples reconciliation to model reflection, cannot describe fields
  that are not model members, and gives no versioned identity to hash.
- **Rejected:** Treat everything as set-valued. This hides real contradictions,
  including two different names or revisions for one repository.
- **Rejected:** Keep the numeric rule and suppress known-noisy fields by name at
  the call site. That is the same declaration, written where it cannot be
  reviewed or versioned.
- **Rejected:** Default undeclared fields to single-valued. Convenient, but it
  manufactures contradictions from unmodelled data.

## Invariants that must survive

- Plurality alone never constitutes a conflict.
- A single-valued field with incompatible claims always conflicts.
- Undeclared cardinality never invents a conflict.
- Competing claims and their evidence references are preserved, never deleted.
- Reconciliation output is deterministic and order-independent.
- The cardinality contract version participates in compiler identity.

## Compliance and validation

- `tests/test_field_cardinality.py` asserts that set-valued plurality produces no
  conflict, that contradictory single-valued claims do, that undeclared fields
  produce unknowns rather than conflicts, that stale and current claims are both
  preserved, that reconciliation is order-independent, and that the contract
  version is present in `active_contract_versions`.
- The declaration is asserted against the frozen domain records so the two
  cannot silently diverge.

## Related artifacts

- `src/l9_constellation_topology/cardinality.py`
- `src/l9_constellation_topology/stages/reconcile_evidence.py`
- `src/l9_constellation_topology/stages/aggregate_repositories.py`
- `src/l9_constellation_topology/config.py`
- `tests/test_field_cardinality.py`
- [ADR-0009](0009-preserve-evidence-authority-conflicts-and-unknowns.md)
- [ADR-0022](0022-key-memory-effects-by-fact-not-snapshot.md)
