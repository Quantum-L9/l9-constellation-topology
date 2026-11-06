# ADR-0034: Semantic claim read model and recognized managed-header vocabulary

**Status:** Accepted as a repository implementation decision (operator instruction, 2026-11-06, PR #42; amended by #46). This is not a formal freeze: the D2 read model implements freeze candidate L9-SEMANTIC-LEVERAGE-FREEZE/1.0, which is architecture-converged and authority-resolution-pending. The managed-header vocabulary (D3) is implemented but **not formally admitted** by a domain authority, and Semantic Foundation v3.27.0 admission remains unresolved.

- **Decision owner:** Repository maintainers
- **Scope:** `reconciliation/predicates.py` (policy 1.3.0), new `topology/claim_view.py`, `cli.py` (`query-claims`)
- **Extends:** [ADR-0033](0033-register-governed-header-predicates-as-declaration-only.md), [ADR-0024](0024-compile-repository-model-assertions-into-semantic-claims.md)
- **Supersedes in part:** ADR-0033's statement that `meta.<ns>.unresolved_field`, `meta.<ns>.unsupported_field` and `meta.unversioned.field` stay `unsupported`

## Context

Topology already emits `SemanticClaimRecord` with subject, predicate, object, evidence references, assertion lineage, authority, confidence, cardinality, support, conflict state and projection state. Downstream users had two ways in: raw packet JSON, or graph edges. The middle layer — source-backed claims that answer real questions without being canonical graph facts — had no typed interface.

Separately, the predicate registry recognized the Foundation-governed native `L9_META` vocabulary (ADR-0033) but not the producer-owned managed header l9-meta-injector writes (declared schema `managed:l9-meta-injector`). Every `meta.managed.*` claim raised an unsupported-predicate unknown, so "this file declares `injectable: true`" was indistinguishable from "we do not know what this field means", and both were reported like missing architectural facts. The producer's own field-observation grammar (`unresolved_field`, `unsupported_field`, `unversioned.field`) was in the same position.

## Alternatives considered

### A separate managed-header registry

Rejected: two registries would answer "what does this predicate mean" differently depending on which was consulted. The existing registry owns predicate meaning.

### A wildcard `meta.managed.*`

Rejected: it would silently assign meaning to fields a future producer adds (pack Case F).

### Classify every managed field as `auxiliary`

Rejected: every managed field is scalar in the producer's schema (`src/schema.ts` `BaseHeader`, `ArtifactMeta`). Calling them multi-valued would hide genuine competing declarations.

### Serialize claim views into the Topology packet

Rejected for now: the view is derivable from data the packet already carries. Adding it to the packet contract needs its own decision and a demonstrated need.

## Decision

1. **Predicate policy 1.3.0** registers the 13 managed fields the producer defines (`MANAGED_VOCABULARY` in its `src/extractors/native_metadata.ts`) as `meta.managed.<category>.<field>`. Each is `single`, declaration-only, and never projectable. Each carries the same nine declaration properties as a governed header predicate. Its `definition` is `l9-meta-injector:managed-header#fields.<field>` and its authority statement says it is producer-owned, not Foundation-governed, and grants no ownership, identity, capability or canonical status. A managed field the producer does not define stays `unsupported`.
2. The producer's field-observation predicates are `auxiliary` (recognized, multi-valued, never projected). `predicate_interpretation()` keeps five readings apart: `declaration`, `auxiliary-observation`, `unresolved-value`, `unsupported-field`, `unsupported-predicate`. Conflict state stays orthogonal, on the claim.
3. **`topology/claim_view.py`** derives a `SemanticClaimView` from each claim and the evidence records it cites: subject kind, raw value, declared value kind, interpretation, definition reference, support, cardinality, authority, confidence, conflict state and ids, assertion ids, evidence refs, source locations, any missing evidence refs, projection status (`projected`, `not-projected`, `not-projectable`), projected entity ids, and the registry identity (`id@version#hash`) it was read under. It is an internal read type: never serialized into a packet, never written, recomputed per read.
4. `SemanticClaimIndex` answers a bounded, deterministic `ClaimQuery` (subject, subject kind, predicate, whole-segment predicate prefix, value, interpretation, conflict, projection, source path, minimum distinct source locations; limit 1–10,000, truncation reported) and a differential between two snapshots (added, removed, re-read). The differential compares where support was read, not packet-scoped evidence ids.
5. **`l9-topology query-claims`** exposes both over a compiled bundle, read-only. It reports whether the packet was compiled under the same predicate registry the reading uses (`matches_packet`).

### Amendment (2026-11-06): pagination and categorized differential

Freeze candidate L9-SEMANTIC-LEVERAGE-FREEZE/1.0 (D2) asks for deterministic pagination and a differential that separates kinds of change. `ClaimQuery.after` adds keyset pagination by `claim_id`, and results report `next_after`. Each re-read claim in a differential lists `categories` (`evidence`, `policy-interpretation`, `reconciliation`, `projection`), with logical additions and removals reported separately. Only `policy-interpretation` fields (support, cardinality) are pure functions of predicate and policy. A change in them between two packets with known, different recorded predicate policy hashes is reported as `caused_by_policy_change`. Reconciliation outcomes (authority, confidence, conflict) can change with the data alone, so they are never attributed to a coinciding policy change. The view remains a transient presentation type; nothing is persisted or serialized into a packet. This amendment does not admit the managed-header vocabulary (D3), and it does not resolve the Semantic Foundation admission question.

### Amendment (2026-11-06): what each view field is, and what carries meaning

`SemanticClaimView` puts four different kinds of information side by side. Only the first is a claim value; the others are read-time presentation, and none of them grants authority by appearing in the view.

| Kind | Fields | Where it comes from | What it may be used for |
|---|---|---|---|
| Stored on `SemanticClaimRecord` | `claim_id`, `subject_id`, `predicate`, `raw_value` (the record's `object`), `authority`, `confidence`, `conflict_status`, `conflict_ids`, `source_assertion_ids`, `evidence_refs`, `projected_entity_ids`; also `support` and `cardinality` (see the next row) | The compiled packet, unchanged | The claim as compiled. These values move only when the packet does |
| Computed or joined presentation | `source_locations` and `missing_evidence_refs` (joined from `EvidenceRecord` by id); `projection_status` and `projection_withheld_reason` (from the stored `projected` flag and this build's `projection_ineligibility`); `interpretation_policy_ref` | Recomputed on every read; never persisted or serialized into a packet | Locating evidence and explaining why a claim did or did not project |
| Consumer-policy predicate interpretation | `interpretation`, `value_kind`, `definition_ref`; `support` and `cardinality` are the same kind of value, but fixed by the predicate policy at compile time and stored | This repository's predicate registry. The first three are read under the registry of the build doing the reading, which can differ from the packet's (`matches_packet`) | Reading a claim at its intended strength. It is this repository's interpretation, not the producer's meaning and not a Semantic Foundation definition |
| No independent semantic authority | `subject_kind` (the prefix of `subject_id`); the distinct-location count behind corroboration filters; `interpretation_policy_ref` and `matches_packet` (identities and an equality, not meaning); the differential's `categories` and `caused_by_policy_change` | Derived mechanically from the rows above | Filtering, paging and explaining a change. Never as evidence that a claim is true, admitted or canonical |

For a header predicate, meaning belongs to whoever owns the vocabulary. The Foundation owns native `L9_META` (ADR-0033); l9-meta-injector owns the managed header. `definition_ref` points at that owner and is not a definition itself. The producer has proposed a versioned managed-header contract, `l9-meta-injector:managed-header@1.0.0` (its ADR-086, Proposed). This registry still cites the unversioned `l9-meta-injector:managed-header#fields.<field>` and does not bind to that version. Binding to it is a separate decision that would move the predicate policy version and hash. Until then the managed-header vocabulary (D3) stays implemented and not admitted, and this amendment changes no field, value or policy hash.

## Consequences

- Managed declarations reach consumers as declarations at their actual strength. No new edge type, owner identity, capability record or graph mutation is introduced. `owner: platform` is retrievable as a declared owner, never as an `OWNED_BY` edge (pack Case D).
- Competing single-valued managed declarations remain conflicts.
- The registry hash moves, so `TopologyPacket.policy_hashes["assertion_predicates"]` and every packet identity compiled under it move. The `foundational-two-repo` golden and `HASH_LOCALITY_EVALUATION.json` change only in that hash and its derived identities.
- Nothing about canonical projection changes here. Conflict-aware projection and resolution-aware impact are a separate decision (pack D5).

## Compliance and validation

- `tests/test_claim_view.py`:
  - every producer managed field is registered `single`, declaration-only, unprojectable, and cites the producer vocabulary;
  - a managed field the producer does not define stays `unsupported` (Case F);
  - the five interpretations stay distinct;
  - competing single-valued managed declarations stay a confirmed conflict;
  - managed declarations raise no unsupported-predicate unknown and project nothing;
  - a declared owner is retrievable with its source location and projects nothing (Case D);
  - injectable artifacts are discoverable with their evidence, and declared classification projects nothing (pack section 12);
  - filters narrow deterministically, prefixes match whole segments, and truncation is reported;
  - corroboration counts distinct source locations, including structured locators that carry no line number;
  - the view is pure and reports missing evidence;
  - the differential reports added, removed and re-read claims, including a confidence-only change;
  - queries are bounded;
  - `query-claims` answers from a compiled bundle and compares a bundle with itself as unchanged.
- `tests/test_header_predicates.py` now holds the three field-observation predicates as recognized auxiliary observations with no unknown, conflict or projection. Predicates with no rule still raise an unknown and a diagnostic.
- Generated artifacts are refreshed with `make generated-update` and checked with `make generated-check`. The reviewed diff of the `foundational-two-repo` golden and `HASH_LOCALITY_EVALUATION.json` moves only the predicate policy hash and identities derived from it. The captured run of record is the `validate` CI job on the head of the pull request that introduces this ADR; this document asserts no result of its own.

## Related artifacts

- `src/l9_constellation_topology/reconciliation/predicates.py` (policy 1.3.0)
- `src/l9_constellation_topology/topology/claim_view.py`
- `src/l9_constellation_topology/cli.py` (`query-claims`)
- `tests/test_claim_view.py`, `tests/test_header_predicates.py`
- `tests/fixtures/topology_packets/foundational-two-repo/`, `HASH_LOCALITY_EVALUATION.json`
- `l9-meta-injector` `src/extractors/native_metadata.ts` (`MANAGED_VOCABULARY`, predicate grammar) and `src/schema.ts` (managed field types)
