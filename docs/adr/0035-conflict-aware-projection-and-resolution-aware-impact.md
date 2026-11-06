# ADR-0035: Conflict-aware canonical projection and resolution-aware impact

**Status:** Accepted as a repository implementation decision (operator instruction, 2026-11-06; revised per operator Option 2 to freeze candidate L9-SEMANTIC-LEVERAGE-FREEZE/1.0 D5a/D5b/F12, PRs #43 and #45). This is not a formal freeze: the candidate is architecture-converged and authority-resolution-pending.

- **Decision owner:** Repository maintainers
- **Scope:** `topology/claim_projection.py`, `topology/work_projection.py`, `topology/impact.py`, `topology/claim_view.py`, `cli.py` (`impact --resolution-aware`)
- **Extends:** [ADR-0034](0034-semantic-claim-read-model-and-managed-header-vocabulary.md), [ADR-0024](0024-compile-repository-model-assertions-into-semantic-claims.md)

## Context

The claim projector checked only predicate eligibility. A single-valued projectable predicate with competing claims — two sources naming two different successors for `repository.replaced_by` — produced one `SUPERSEDES` edge per competing value. Canonical topology therefore asserted relations whose truth depended on picking one of the values, while the conflict record said no value had been picked. The work projector checked nothing at all; its predicates are set-valued today, so it could not yet be reached by a conflict, but nothing stopped a future one.

The work projector deliberately keeps an edge to an explicitly-labelled reference node when a declared target resolves to no single observed artifact. `assess_impact` traversed those edges like any other and never populated `ImpactIndex.unresolved_edge_ids`. A blast radius could therefore run through a target nobody identified.

## Alternatives considered

### Drop unresolved work edges

Rejected: the declaration is the strongest part of the signal, and ADR-level policy in `work_projection.py` already preserves it.

### Require every endpoint to be an observed repository

Rejected: a declared external package dependency is a legitimate, explicitly-labelled relation to an external identity (pack Case H).

### Pick the highest-confidence competing value

Rejected: no winner is chosen without an explicit authority rule (ADR-0023, ADR-0024).

### Make resolution-aware traversal the default immediately

Rejected for now: the compiler's own impact stage and every existing caller rely on generic reachability. Changing the default would silently change every packet's `impact_indexes`. It is offered as an explicit mode first.

## Decision

1. **Claim-level projection eligibility (D5a).** `projection_ineligibility(claim)` is consulted by the claim projector and the work projector before any projector-specific rule. A claim does not project when:
   - its predicate is not projectable (`predicate-not-projectable`);
   - its conflict status is in `PROJECTION_WITHHELD_CONFLICT_STATUSES` (`possible`, `confirmed`), or it names a conflict id (`conflicted`).

   The rule compares the existing `ConflictStatus` enum, never strings. It is not a global authority gate. Relation-specific authority and endpoint identity requirements stay inside each projector, and an unconflicted claim projects exactly as before this decision.
2. **Policy identity (freeze F12).** The rule is part of the predicate registry's policy view (`projection_eligibility`), and the registry moves to 1.4.0. The binding landed in #45, stacked on #43 under the file-scope invariant (ADR-0052), and merged into #43 before #43 reached `main`. That view is hashed into `TopologyPacket.policy_hashes["assertion_predicates"]` and into the compile idempotency key. A packet realized under a different rule therefore cannot share an identity. No packet field or schema changes.
3. A conflicting claim stays a claim and a conflict record. The claim view reports it as `projection_status: withheld` with `projection_withheld_reason: conflicted`.
4. **Resolved dependency impact (D5b)** is an explicit opt-in mode: `assess_impact(..., resolution_aware=True, observed_entity_ids=...)`, or `l9-topology impact --resolution-aware`. The default reachability traversal is unchanged.
   - It walks only `DEPENDENCY_EDGE_TYPES` (`DEPENDS_ON`, `BLOCKED_BY`). A caller-supplied edge set outside that set is refused.
   - It judges each target by the evidence of the producer that emitted the edge (`dependency_target_resolution`):
     - work projector `target_resolution: exact-artifact` → resolved; any other recorded value → unresolved;
     - claim projector `endpoint_kind: external-package-reference` → resolved, as an external package identity (Case H);
     - graph-builder repository dependency with a target the packet observed → resolved;
     - anything else → unresolved. An absent `target_resolution` is never read as resolved.
   - It never crosses an unresolved edge and never counts that edge's endpoint as affected. It reports every such edge it reaches in the existing `ImpactIndex.unresolved_edge_ids`. No new impact record, graph engine or dependency ontology is introduced.

## Consequences

- Conflicting projectable declarations no longer produce canonical relations (pack Case G).
- The predicate policy hash moves, so the `foundational-two-repo` golden and `HASH_LOCALITY_EVALUATION.json` change in that hash and the identities derived from it. No record content changes, because the fixtures contain no conflicted projectable claim.
- Dependency-impact consumers can separate resolved chains from declared-but-unresolved references (Case E) without losing legitimate external dependencies (Case H). Containment, documentation and governance relations stay out of the dependency question.
- Resolution-aware impact is a read-time interpretation; the compiler's stored `impact_indexes` remain generic reachability. Making it a default, or storing it, needs its own decision because it changes packet identity.
- The projection *table* (which predicates have a projector) is code bound by the compiler build identity, not by a policy hash. That was true before this decision and is unchanged here.

## Compliance and validation

- `tests/test_qualified_projection.py`:
  - conflicting successors project no supersession edge, while an unconflicted one still projects;
  - a possible conflict withholds projection, and an unconflicted candidate-authority claim still projects (no global authority gate);
  - declaration-only predicates report their own reason;
  - the claim view reports `withheld` with its reason;
  - a conflicted work claim projects no work edge;
  - an unresolved target is reported and not traversed, while the generic traversal is unchanged;
  - an external package dependency stays resolved;
  - an ambiguous target is unresolved;
  - an absent `target_resolution` is unresolved, while a graph-builder dependency on an observed repository is resolved;
  - only `DEPENDS_ON` and `BLOCKED_BY` are walked, and other caller-supplied relations are refused;
  - traversal stops only at the unresolved hop;
  - the CLI accepts `--resolution-aware`.
- Generated artifacts are refreshed with `make generated-update` and checked with `make generated-check`; only the predicate policy hash and identities derived from it move. The captured run of record is the `validate` CI job on the head of the pull request that introduces this ADR; this document asserts no result of its own.

## Related artifacts

- `src/l9_constellation_topology/reconciliation/predicates.py` (policy 1.4.0, `PROJECTION_WITHHELD_CONFLICT_STATUSES`)
- `src/l9_constellation_topology/topology/claim_projection.py` (`projection_ineligibility`, `eligible_for_canonical_projection`)
- `src/l9_constellation_topology/topology/work_projection.py`
- `src/l9_constellation_topology/topology/impact.py` (`DEPENDENCY_EDGE_TYPES`, `dependency_target_resolution`, `resolution_aware`)
- `src/l9_constellation_topology/topology/claim_view.py` (`withheld`, `projection_withheld_reason`)
- `src/l9_constellation_topology/cli.py`
- `tests/test_qualified_projection.py`
