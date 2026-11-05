# ADR-0032: Register governed native-header predicates as declaration-only claims

**Status:** Accepted (operator decision, 2026-11-05: admit header meanings in `Quantum-L9/.github` first, then integrate)

- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology` predicate registry (`reconciliation/predicates.py`)
- **Extends:** [ADR-0024](0024-compile-repository-model-assertions-into-semantic-claims.md), [ADR-0023](0023-declare-field-cardinality-before-detecting-conflicts.md)

## Context

`l9-meta-injector` emits one assertion per native `L9_META` header field (its ADR-082), under predicates such as `meta.l9v1.governance.owner`. Predicate policy 1.1.0 declared none of them. ADR-0024 therefore held every claim as `unsupported`: preserved, but raising one unknown and one diagnostic per `(subject, predicate)` group. Across the Phase 2 acceptance repositories (L9-Ops-MCP, cognitive.engine.graphs, enrichment.inference.engine), that was 6,431 unknowns, all holding publication.

Registering the predicates earlier would have meant inventing their meaning. The Semantic Foundation now defines them. `Quantum-L9/.github` v3.27.0 adds `l9.artifact-header-model/global@1` (ADR-024 there, PR #204), which says:

- every header field is a source declaration the file makes about itself;
- each of 30 fields has a defined meaning and a list of what it does not establish (`owner` is no ActorIdentity and no OWNED_BY, `ssot_for` no canonical source or GOVERNED_BY, `references` and `requires` no DEPENDS_ON, `status` no lifecycle state);
- `projection_boundary.canonical_relations: none`.

The producer now transcribes that ledger in one hash-bound mapping (l9-meta-injector ADR-084, profile 1.4.0).

## Alternatives considered

### Option A: keep them unsupported

- Pros: no policy change.
- Cons: thousands of unknowns hold publication for claims whose meaning is now governed, and single-valued contradictions such as two owners for one file are never surfaced as conflicts.

### Option B: register them all as `auxiliary`

- Pros: no projection, no unknowns.
- Cons: auxiliary reconciles as a set, so two different `status` or `owner` declarations about one file would aggregate silently. That breaks the ledger's rule that such conflicts are preserved and reported, and ADR-0023.

### Option C: register them by the ledger's value kind, with a declaration-only projection guard

- Pros: list fields aggregate, scalars conflict, and nothing projects.
- Cons: a third axis (projectability) sits beside cardinality in the registry.

## Decision

We choose **Option C**, in the one existing registry, with no new support class.

1. **Classes.**
   - The 60 governed header predicates are 30 fields under `l9v1` and `l9v2`. List value kinds (`label_list`, `reference_list`) are `set`; every other value kind is `single`.
   - `meta.declaration.carrier` and `meta.declaration.schema` are `auxiliary`.
   - Fields without a governed meaning stay `unsupported`: `meta.<ns>.unresolved_field`, `meta.<ns>.unsupported_field`, `meta.unversioned.field`, the producer-owned `meta.managed.*`, and any category/field mismatch.
2. **Declaration-only.** `DECLARATION_ONLY_PREDICATES` holds every governed header predicate plus the two structural ones. `is_projectable` refuses them before the projection table is consulted, so no future `_PROJECTORS` entry can make a header field project by accident.
3. **Declarations.** Each governed predicate declares the nine properties the Phase 2 pack requires:
   - definition, as a ledger `#fields.<field>` reference;
   - subject scope (`artifact`);
   - object type (the ledger value kind);
   - cardinality and support class;
   - authority (a declared source claim granting no ownership, identity or canonical status);
   - projection eligibility (`none`);
   - conflict behavior;
   - unknown behavior.
4. **Identity.** The predicate policy moves to **1.2.0**. Its view carries `declaration_only_predicates` and the full header declarations, so the `assertion_predicates` policy hash changes and no packet compiled under 1.1.0 shares an identity with one compiled under 1.2.0.
5. **Unchanged.**
   - The claim projection table (`claim_projection._PROJECTORS`), the eligibility policy, the RMP adapter and the packet schemas.
   - Header conflicts are raised with `blocking=False`. They are material only for candidates whose own source fields they name, so they stay visible without holding unrelated topology facts.

## Consequences

- Header claims reconcile as governed claims. The unknowns they used to raise disappear, and a single-valued contradiction about one file becomes a recorded, unresolved conflict.
- No OWNED_BY, GOVERNED_BY, DEPENDS_ON, capability or ownership fact can be derived from a header. A future projection of any header field requires an admitted Foundation decision naming the relation's owner, and a superseding ADR here.
- Other producer predicates that carry no Foundation meaning stay `unsupported`, and their unknowns remain: `workflow.*`, `source.import.*`, `contract.reference.*`.
- The `foundational-two-repo` golden changes only in `policy_hashes.assertion_predicates` and the identities derived from it.

## Compliance and validation

- `tests/test_header_predicates.py` covers the registry and the projection gate:
  - all 60 governed predicates carry the nine declared properties and cite their ledger field;
  - scalar header conflicts are confirmed with no winner and `blocking=False`;
  - list fields aggregate, and declarations in different files never conflict;
  - fields without a governed meaning stay `unsupported`, with a diagnostic and an unknown;
  - every declaration-only predicate projects nothing, checked by parameter over the whole set;
  - owner, `ssot_for`, `references`, `requires`, `load_when` and `amplifies` produce no edge while a `package.dependency` control still projects DEPENDS_ON;
  - changing a header declaration moves the policy hash.
- `tests/test_assertion_reconciliation.py` keeps the registry disjoint and complete, and now checks that `set` and `single` predicates are projectable exactly when they are not declaration-only.
- `make fixtures-check` passes after `make fixtures-update`. The `foundational-two-repo` golden differs from its 1.1.0 form only in `policy_hashes.assertion_predicates`, `artifact_hash`, `packet_id` and `semantic_hash`.

## Related artifacts

- `src/l9_constellation_topology/reconciliation/predicates.py` (policy 1.2.0)
- `src/l9_constellation_topology/reconciliation/__init__.py`
- `tests/test_header_predicates.py`, `tests/test_assertion_reconciliation.py`
- `tests/fixtures/topology_packets/foundational-two-repo/`
- Semantic Foundation `semantics/artifact_header_model.yaml` and ADR-024 in `Quantum-L9/.github` at `b3755ad778eef6d8a465c593d1b5870534ce4ede`
- `l9-meta-injector` ADR-084 and `docs/semantic-mapping.md` (PR #131)
