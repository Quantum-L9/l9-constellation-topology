# ADR-0034: Semantic claim read model and recognized managed-header vocabulary

**Status:** Accepted (operator instruction, 2026-11-06: execute the L9 Semantic Leverage Architecture Decision Pack, decisions D2 and D3, PR 2)

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
  - corroboration counts distinct source locations;
  - the view is pure and reports missing evidence;
  - the differential reports added, removed and re-read claims;
  - queries are bounded;
  - `query-claims` answers from a compiled bundle and compares a bundle with itself as unchanged.
- `tests/test_header_predicates.py` now holds the three field-observation predicates as recognized auxiliary observations with no unknown, conflict or projection. Predicates with no rule still raise an unknown and a diagnostic.
- `make fixtures-check` and `make hash-locality` pass after `make generated-update`; only the predicate policy hash and identities derived from it moved.

## Related artifacts

- `src/l9_constellation_topology/reconciliation/predicates.py` (policy 1.3.0)
- `src/l9_constellation_topology/topology/claim_view.py`
- `src/l9_constellation_topology/cli.py` (`query-claims`)
- `tests/test_claim_view.py`, `tests/test_header_predicates.py`
- `tests/fixtures/topology_packets/foundational-two-repo/`, `HASH_LOCALITY_EVALUATION.json`
- `l9-meta-injector` `src/extractors/native_metadata.ts` (`MANAGED_VOCABULARY`, predicate grammar) and `src/schema.ts` (managed field types)
