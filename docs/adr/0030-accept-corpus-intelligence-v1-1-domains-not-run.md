# ADR-0030: Accept corpus-intelligence 1.1.0 `domains_not_run`

**Status:** Accepted
**Extends:** [ADR-0026](0026-accept-corpus-intelligence-as-an-auxiliary-packet.md)

## Context

`l9-meta-injector` 4.2.0 emits `l9.corpus-intelligence` 1.1.0 under its
accepted ADR-068. The additive `domains_not_run` array distinguishes an
analysis pass that was not run from a pass that ran and found no records. The
producer binds the array into its semantic hash between `corpus` and
`schema_hash`, and also emits lexical `TOPIC_CANDIDATE` clusters.

Topology's closed corpus packet model admitted neither the new key nor its
versioned semantic view. It therefore rejected valid producer bundles before
candidate lowering could preserve their lineage.

## Decision

Accept corpus packet versions **1.0.0** and **1.1.0** at the ingress boundary.

For 1.1.0, require `domains_not_run` to be an array of unique entries whose
`domain` is one of the nine declared payload domains and whose `reason` is
non-empty. A domain declared not run must have an empty materialized payload.
The field is included in the semantic view immediately after `corpus`, exactly
as the producer hashes it.

For 1.0.0, the field remains absent from both packet serialization and the
semantic view. Existing 1.0.0 identities and output bytes therefore remain
unchanged. Unknown fields and malformed run statements remain refused by the
closed models and validation boundary.

Lexical `TOPIC_CANDIDATE` clusters remain candidate records: topology accepts,
lowers, and preserves their producer profile and lineage; it does not promote
them into canonical edges.

## Consequences

A real 1.1.0 producer-emitted fixture verifies and compiles through the same
loader as normal ingress. The retained 1.0.0 fixture and its semantic identity
continue to load unchanged. Versioned adaptation is limited to this packet
boundary; no pipeline, runtime dependency, or canonical candidate policy
changes.

## Alternatives considered

**Treat an omitted 1.1.0 field as an empty array.** Rejected: the producer uses
an empty array to say the pass ran and found nothing, so defaulting would erase
the fact the new field exists to retain.

**Add the field to the 1.0.0 semantic view.** Rejected: it would change
established 1.0.0 packet identity and rendering for an additive contract.

## Compliance and validation

- Contract tests cover 1.0.0 identity preservation, 1.1.0 hash agreement,
  unknown/repeated/non-empty-domain refusals, and semantic-hash tampering.
- The producer-emitted fixture is refreshed only by the immutable producer
  revision's `emit_corpus_intelligence_fixture.ts` command, then loaded and
  compiled by the consumer tests.

## Related artifacts

- `src/l9_constellation_topology/packets/corpus_intelligence.py`
- `src/l9_constellation_topology/packets/corpus_bundle.py`
- `src/l9_constellation_topology/packets/corpus_validator.py`
- `tests/test_corpus_intelligence_contract.py`
- `tests/test_producer_emitted_corpus_packet.py`
- [ADR-0026](0026-accept-corpus-intelligence-as-an-auxiliary-packet.md)
