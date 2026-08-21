# ADR-0024: Compile repository-model assertions into canonical semantic claims

- **Status:** Accepted
- **Date:** 2026-08-21
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`
- **Relates to:** [ADR-0021](0021-internalize-publication-planning-and-memory-lowering.md),
  [ADR-0023](0023-declare-field-cardinality-before-detecting-conflicts.md),
  [ADR-0025](0025-separate-fact-identity-from-durable-write-identity.md)

## Context

Repository-model packet 1.1.0 added an assertion domain: typed semantic claims a
repository makes about itself, each citing an exact line span in a named file
together with that file's sha256 and the extractor that read it.

This consumer accepted those packets and preserved the domain through
`RepositoryModelV1Adapter`. Then it dropped it. `normalize_models` did not carry
`assertions` into `NormalizedInputs`, and `compile_topology` never reconciled
them, so every assertion a producer emitted was discarded between ingress and
topology. The pipeline was accepting semantic knowledge and compiling as though
it had never arrived.

Three questions had to be answered before the domain could be activated.

**Where does a claim live?** None of the existing canonical records can carry an
arbitrary subject/predicate/object losslessly. `RepositoryRecord` has a closed
field set with no room for an arbitrary predicate. `CapabilityRecord` describes a
capability, not a claim. `EdgeRecord` needs two resolvable topology entities,
which most claims do not have — a dependency on `fastapi` names a package, not a
constellation member. `ConflictRecord` and `UnknownRecord` describe what went
*wrong* with a claim rather than the claim itself. Forcing a claim into any of
them would either drop the predicate or assert a relationship never observed.

**What does more than one answer mean?** A predicate is a producer-chosen string.
Treating every such string alike is wrong in both directions: fourteen values of
`package.dependency` are fourteen true facts, while two values of `package.name`
are one question with two competing answers. Without a declared arity the first
becomes a manufactured contradiction and the second a silent aggregation.

**How much may a claim be projected into?** An observed route says a route was
observed. It does not say the service is reachable, and an unfinished-work marker
in a handler body does not settle whether the handler works.

## Decision

Assertions are carried, reconciled, and preserved as first-class topology
knowledge, and projected only where an explicit mapping exists.

1. **Evidence at the packet boundary.** `RepositoryModelV1Adapter` builds an
   `EvidenceRecord` per assertion, where the parent packet is still in hand. The
   record's `source_ref.content_hash` is the *source file's* digest, not the
   repository snapshot's, so a claim stays bound to the bytes that support it
   across unrelated commits. The producer's assertion id, extractor, span, and
   read excerpt are carried in the record's value.

2. **A versioned predicate registry.** `reconciliation/predicates.py` declares
   each predicate as `set`, `single`, `auxiliary`, or `unsupported`. Its hash
   joins `TopologyPacket.policy_hashes`, so changing what a predicate means
   cannot reuse the identity of a packet compiled under the old meaning.

3. **A canonical claim record.** `SemanticClaimRecord` is identified by
   `H(subject_id, predicate, object)` alone. The packet that carried it, the
   topology hash, the wall clock, and the checkout are outside that identity by
   construction, because none of them are arguments to it.

4. **Reconciliation by declared arity.** Set predicates union. Single predicates
   resolve when every assertion agrees, aggregating supporting evidence rather
   than deduplicating it away; when they disagree, every competing claim is kept,
   a `ConflictRecord` is emitted, and no winner is elected. Auxiliary predicates
   reconcile as sets and never project. An unsupported predicate is preserved
   with its evidence plus a diagnostic and a predicate-scoped unknown: nothing
   aggregated, nothing contradicted, nothing dropped.

5. **Projection only where mapped.** `package.dependency`, `service.action`,
   `http.route`, `authority.canonical_contract`, and `repository.replaced_by`
   project. External names become explicitly-labelled external identities
   (`package:`, `contract-reference:`, `repository-reference:`) carrying their
   own graph nodes, never synthesized `repo:` identities. No rule reads
   `http.handler_body_marker`, turns `package.framework` into a service role, or
   equates `package.name` with `service.name`.

6. **Conservation is validated, not assumed.** `cross-assertion-conservation`
   fails the compile if any input assertion reaches the compiler and leaves no
   trace, or if a claim cites an assertion no input made. Identity, not count.

7. **Claims publish as triples.** A claim lowers to a `MemoryWriteRequest` whose
   `assertion` is the claim verbatim, so it publishes as the statement it is even
   where no richer graph projection exists.

## Consequences

- Semantic knowledge a producer emits now reaches topology and memory instead of
  being discarded. On `cryptoxdog/golden-repo`, 77 assertions across 22
  predicates become 56 reconciled claims with zero loss.
- A repository can be deprecated *and* describe itself as a reference
  implementation; both claims survive, because they answer different questions.
- Competing package names are reported as the conflict they are, and the affected
  claims are held rather than published — while every other claim about the same
  repository publishes normally.
- `TopologyState` gains a payload domain, so topology packet identity moves once
  for every existing packet. Repository-model 1.0.0 inputs carry no assertion
  domain and compile exactly as before, inventing nothing.
- Two reconcilers must never adjudicate one fact. `reconcile_evidence` reads the
  field-cardinality contract and therefore deliberately skips assertion-derived
  evidence; `reconcile_assertions` owns predicates, with the registry that knows
  their arity.

## Alternatives considered

**Carry assertions in diagnostics.** Rejected: diagnostics are prose, so the
claim would not be queryable, reconcilable, or publishable as a triple, and
evidence would be reduced to "the packet said so".

**Force claims into `EdgeRecord`.** Rejected: it would require inventing a
topology entity for every object, which is exactly the fabrication the external
identity prefixes exist to prevent.

**Project every predicate.** Rejected: projection asserts more than the assertion
did. Preservation is unconditional; projection is earned by an explicit mapping.

**Treat an unknown predicate as an error.** Rejected: unknown beats guess, but it
does not beat *preserved*. The claim and its evidence survive; only its meaning
is withheld.

## Compliance and validation

- `cross-assertion-conservation` in `validation/topology_validator.py` fails the
  compile when an input assertion leaves no trace in either the evidence pool or
  the claim set, or when a claim cites an assertion no input made. It compares
  identities rather than counts, so a lost assertion cannot be masked by a
  coincidentally equal total.
- `tests/test_semantic_claim_activation.py` runs against a real repository-model
  1.1.0 bundle emitted by the bound `l9-meta-injector`, and pins each epistemic
  requirement by name: every emitted predicate survives, exact spans and file
  digests reach topology, competing package names conflict without a winner,
  agreement across two files aggregates evidence, deprecation and reference role
  both survive, an unfinished-work marker never becomes a verdict, package
  identity is never conflated with service identity, a dependency never becomes
  an observed repository, and a 1.0.0 constellation invents no claims.
- `tests/test_assertion_reconciliation.py` covers the unsupported-predicate path,
  which no producer emission can reach, and asserts that assertion evidence is
  adjudicated once — by the predicate registry, not also by the field-cardinality
  contract.
- `scripts/qualify_repository_model_assertions.py` records activation against
  externally produced packets in `QUALIFICATION.json`, including assertion loss
  count and dispatch count.

## Related artifacts

- `src/l9_constellation_topology/domain/claim.py`
- `src/l9_constellation_topology/reconciliation/predicates.py`
- `src/l9_constellation_topology/packets/assertion_evidence.py`
- `src/l9_constellation_topology/stages/reconcile_assertions.py`
- `src/l9_constellation_topology/topology/claim_projection.py`
- `schemas/semantic-claim-record.schema.json`
- `tests/fixtures/semantic_assertion_repository/`
- `QUALIFICATION.json`
- [ADR-0009](0009-preserve-evidence-authority-conflicts-and-unknowns.md)
- [ADR-0023](0023-declare-field-cardinality-before-detecting-conflicts.md)
- [ADR-0025](0025-separate-fact-identity-from-durable-write-identity.md)
