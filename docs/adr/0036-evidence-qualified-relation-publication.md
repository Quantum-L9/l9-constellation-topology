# ADR-0036: Evidence-qualified relation publication and predicate-selective claims

**Status:** Accepted on merge by the repository owner; until then this record is a proposal on its pull request. Activation of policy 2.0.0 for downstream consumption is a separate owner decision (see *Activation boundary*).

- **Decision owner:** Repository maintainers
- **Scope:** `publication/qualification.py`, `publication/plan.py`, `publication/policy.py`, `publication/lowering.py`, `publication/eligibility.py`, `.l9/publication-policy.yaml`
- **Extends:** [ADR-0021](0021-internalize-publication-planning-and-memory-lowering.md), [ADR-0035](0035-conflict-aware-projection-and-resolution-aware-impact.md)
- **Bound by:** [ADR-0025](0025-separate-fact-identity-from-durable-write-identity.md), [ADR-0027](0027-separate-observation-time-from-publication-time.md), [ADR-0033](0033-register-governed-header-predicates-as-declaration-only.md), [ADR-0034](0034-semantic-claim-read-model-and-managed-header-vocabulary.md)

## Context

Publication selected relationships by edge type alone. Any `GOVERNED_BY`, `DOCUMENTED_BY` or `VALIDATED_BY` edge was lowered into a durable `semantic` assertion, whatever produced it. The graph builder emits those three types for every artifact whose *path* classifies it as an ADR, a governance file, a README or a CI workflow (`_ARTIFACT_RELATION_BY_TYPE`). The only evidence on such an edge is the artifact's own observation: it proves the file exists and what kind of file it is. It does not prove that the repository is governed by it, documented by it, or validated by it. Downstream, the published assertion is indistinguishable from a relation some producer actually established.

Claim publication had the same shape. With `semantic_claim` selected, every reconciled claim was lowered, including auxiliary predicates and — once a producer emits them — governed and managed header declarations (`meta.*`), which ADR-0033 and ADR-0034 define as declarations a file makes about itself, never projected.

## Decision

1. **One pure qualification function.** `qualify_relation(edge, QualificationIndex)` decides, per edge, whether its own producer evidence proves the relation. It identifies the emitting producer from what the edge and topology state already carry (`relation_origin`), then applies that producer's rule:

   | Origin | Recognized by | Qualifies when |
   |---|---|---|
   | `work-projector` | `target_resolution` | the originating claim exists and passes D5a, and `target_resolution` is `exact-artifact` (D5b) |
   | `claim-projector` | `projected_from_claim_id` + `endpoint_kind` | `endpoint_kind` matches the family, and the originating claim exists and passes D5a |
   | `exact-duplicate` | `DUPLICATE_OF` + `method` | `method` is `content-hash-equality/v1` and `content_hash` is present |
   | `producer-declared` | a resolved observed/declared/validated/committed evidence record whose `field` names the relation | always |
   | `repository-upstream` | graph builder: target in the repository's `upstream_repository_ids` | the target is an observed repository (D5b) |
   | `repository-owner`, `capability-record`, `artifact-capability` | graph builder: the edge mirrors that record's own list | always (`record-membership`) |
   | `artifact-containment`, `corpus-scope` | graph builder / corpus scope `CONTAINS` | always (`inventory`) |
   | `artifact-classification` | graph builder: repository→own-artifact `GOVERNED_BY`/`DOCUMENTED_BY`/`VALIDATED_BY` with no relation evidence | never |

   `ADMISSIBLE_ORIGINS` declares which origins each edge type admits. It fails closed: an edge type with no rule (`qualification.relation_type_unrecognized`), an origin the type does not admit or that cannot be identified (`qualification.evidence_origin_unsupported`), a recognized origin whose evidence does not resolve or whose mandatory relation-specific evidence is absent (`qualification.relation_evidence_missing`), a classification-only edge (`qualification.artifact_classification_only`), a conflicted originating claim (`qualification.originating_claim_not_projectable`), a claim-projected endpoint of the wrong kind (`qualification.endpoint_kind_mismatch`) and an unobserved graph-builder dependency target (`qualification.endpoint_unresolved`) are all unqualified. The established `relation.work_target_not_exactly_resolved` keeps its string.

   D5a and D5b are reused by import (`projection_ineligibility`, the impact module's resolution constants), not restated, and neither becomes a universal authority rule: an unconflicted candidate-authority claim still qualifies its projection, and an external package endpoint stays resolved.
2. **Unqualified is not unselected.** Under `relation_qualification: strict` qualification runs first. An unqualified edge is skipped under its `qualification.*` reason; a qualified edge whose type the policy does not select is skipped under `policy.edge_type_not_selected`. That skip therefore now implies the edge was qualified. `PublicationCandidate`, `SkippedCandidate` and `EligibilityDecision` are unchanged. A qualified relationship's request metadata records `topology_relation.qualification` (`origin`, `status`, `basis`); metadata is outside fact and effect identity.
3. **Predicate-selective claims.** `claim_publication: selective` lowers a claim only when its predicate is named in `eligible_claim_predicates`; a registry-declared predicate that is not named is skipped under `policy.claim_predicate_not_selected`. Declaration-only predicates (governed and managed header fields, header structure, field observations) may not appear in that list; they are published only when named in `declaration_only_claim_predicates`, and are otherwise skipped under `policy.declaration_only_claim_not_opted_in`. A predicate the registry does not declare is still lowered and held (`predicate.unsupported_by_registry`), so the registry gap stays visible. The parser rejects lists under `claim_publication: all`, unknown predicates, duplicates, and declaration-only predicates in the wrong list. No expression language is introduced.
4. **Policy 2.0.0.** The checked-in policy selects `strict`, `selective`, every registry predicate with declared meaning (`set` or `single`, not declaration-only), and no declaration-only predicate. A policy whose four new fields all hold their pre-ADR-0036 values omits them from its hashed view, so the 1.0.0 policy keeps its exact `policy_hash` and produces a byte-identical plan. `tests/fixtures/publication_policies/legacy-v1` is that policy, byte for byte.
5. **The Topology Packet is unchanged.** Nothing in this decision touches compilation, canonical edges, or `TopologyPacket.policy_hashes`.

## Consequences

### Identity and lifecycle

Measured from identical pinned source packets (`tests/fixtures/repository_model_packets/*`; the producer-emitted corpus fixture):

- **Topology packet and semantic hashes:** unchanged.
- **Policy identity:** `foundational-topology-publication/1.0.0` → `/2.0.0`; `policy_hash` moves. Under the legacy fixture it does not.
- **Plan identity:** `plan_id` and plan semantic hash move under 2.0.0. Under the legacy fixture they equal the pre-change plan.
- **Candidate identity:** every candidate retained keeps its `candidate_id`; strict only removes candidates and never adds one.
- **Effect keys:** every retained candidate's idempotency key moves, *solely* because of the version bump: ADR-0025 makes `Confidence.policy_version` (`l9-topology-publication/<version>`) part of the requested write. The same strict policy at version 1.0.0 moves no key.
- **Removed effects:** a candidate no longer planned is not retracted. ADR-0027 forbids retraction from missing or newly filtered observations, and this repository plans no retraction; whether anything previously published must be retracted is a downstream decision.

### Activation boundary

Activation means a downstream consumer acting on plans built under policy 2.0.0. It is **not authorized by this record**:

- Whether any 1.0.0 key has reached durable memory is **Unknown**. `EFFECT_IDENTITY_MIGRATION_PREFLIGHT.json` records that no dispatch surface exists in this repository and that the downstream revision it inspected held no trace of this repository's namespace; it is bound to that revision and says nothing about durable state since. Inspecting current durable state is outside this repository's authority.
- If 1.0.0 effects were dispatched, adopting 2.0.0 issues a new write for every retained fact (new keys, same `candidate_id`s), and leaves the removed classification-only relations in durable memory with nothing in this repository to retract them.

The repository owner decides whether to accept the version bump's re-keying, or to require a migration plan, before plans under 2.0.0 are consumed.

## Alternatives considered

- **Hold unqualified relations instead of skipping them.** Rejected: a held candidate is a fact awaiting resolution. A classification-only edge is not awaiting anything; no further evidence can arrive through the same rule.
- **A separate qualification service or graph.** Rejected by scope: one pure function over the existing state.
- **A generic policy-expression engine for claim selection.** Rejected: two literal predicate lists cover the requirement and keep the policy reviewable.
- **Keep version 1.0.0 to avoid re-keying.** Rejected: the rules that produce the plan changed, and ADR-0025 deliberately makes a relabelled policy a different request.

## Compliance and validation

- `tests/test_publication_qualification.py`: every edge type has a rule; qualification is pure and replay-deterministic; every pinned edge has an identified producer; classification promotion is unqualified; D5a and D5b gates; missing originating claim, endpoint mismatch, missing evidence, unrecognized type; the strict effect versus the legacy fixture from identical packets (only removals, exact reasons, counts); retained effects re-key only through the version; qualification basis only under strict; declaration-only opt-in; unsupported predicates still held; policy parser fail-closed cases.
- `tests/test_publication_planning.py`, `tests/test_semantic_claim_activation.py`, `tests/test_assertion_reconciliation.py` updated to the 2.0.0 contract.
- `HASH_LOCALITY_EVALUATION.json` regenerated: every verdict unchanged; only candidate counts (18 → 12) and the policy identity move. The `published_assertion` case plans its mutated edge with qualification relaxed, so it still measures identity rather than qualification.

## Related artifacts

- `src/l9_constellation_topology/publication/qualification.py`
- `.l9/publication-policy.yaml`
- `tests/fixtures/publication_policies/legacy-v1/.l9/publication-policy.yaml`
- `scripts/evaluate_hash_locality.py`
