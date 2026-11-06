# ADR-0035: Conflict-aware canonical projection and resolution-aware impact

**Status:** Accepted (operator instruction, 2026-11-06: execute the L9 Semantic Leverage Architecture Decision Pack, decision D5, PR 3)

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

1. `projection_ineligibility(claim)` is the single projection-boundary decision, consulted by the claim projector and the work projector before any projector-specific endpoint rule. A claim is ineligible when:
   - its predicate is not projectable (`predicate-not-projectable`);
   - it carries any conflict, confirmed or possible, or names conflict ids (`conflicted`);
   - its authority is `candidate` or `unknown` (`insufficient-authority`).

   The current enums are used, never string comparison.
2. Target resolution stays each projector's own rule. External packages stay external identities, and unresolved work references stay reference nodes.
3. A conflicting claim remains a claim and a conflict record and produces no canonical relation. The claim view reports it as `projection_status: withheld` with `projection_withheld_reason`.
4. `assess_impact(..., resolution_aware=True)` (`l9-topology impact --resolution-aware`) treats an edge as unresolved only when its projector recorded `target_resolution` as `unresolved` or `ambiguous`. It does not traverse such an edge, does not count its endpoint as affected, and reports every unresolved edge the traversal reaches in `unresolved_edge_ids`. Every other edge, including an external-package dependency, is resolved. The default traversal is unchanged.

## Consequences

- Conflicting projectable declarations no longer produce canonical relations (pack Case G). Unconflicted ones project exactly as before.
- Dependency-impact consumers can separate resolved paths from declared-but-unresolved references (pack Case E), without losing provenance or legitimate external dependencies (Case H).
- No committed golden changes: the fixtures contain no conflicted projectable claim, the default traversal is unchanged, and the predicate policy is unchanged.
- Whether resolution-aware traversal should become the default, including for the compiler's `impact_indexes`, is left open. It needs its own decision because it changes packet identity.

## Compliance and validation

- `tests/test_qualified_projection.py`:
  - conflicting successors project no supersession edge, while an unconflicted one still projects;
  - a possible conflict and a candidate authority each withhold projection;
  - declaration-only predicates report their own reason;
  - the claim view reports `withheld` with its reason;
  - a conflicted work claim projects no work edge;
  - an unresolved target is reported and not traversed, while the generic traversal is unchanged;
  - an external package dependency stays resolved;
  - an ambiguous target is unresolved;
  - traversal stops only at the unresolved hop;
  - the CLI accepts `--resolution-aware`.
- The decision changes no committed fixture or golden: `make generated-check` must pass without running an update target. The captured run of record is the `validate` CI job on the head of the pull request that introduces this ADR; this document asserts no result of its own.

## Related artifacts

- `src/l9_constellation_topology/topology/claim_projection.py` (`projection_ineligibility`, `eligible_for_canonical_projection`)
- `src/l9_constellation_topology/topology/work_projection.py`
- `src/l9_constellation_topology/topology/impact.py` (`edge_is_resolved`, `resolution_aware`)
- `src/l9_constellation_topology/topology/claim_view.py` (`withheld`, `projection_withheld_reason`)
- `src/l9_constellation_topology/cli.py`
- `tests/test_qualified_projection.py`
