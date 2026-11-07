# ADR-0037: Stop promoting artifact classification to canonical relations

**Status:** Accepted on merge by the repository owner; until then this record is a proposal on its pull request. It changes canonical Topology Packet content and identity, which requires that owner decision.

- **Decision owner:** Repository maintainers
- **Scope:** `topology/graph_builder.py`
- **Consistent with:** [ADR-0009](0009-preserve-evidence-authority-conflicts-and-unknowns.md), [ADR-0012](0012-use-stable-repository-and-entity-identity.md), [ADR-0013](0013-keep-graph-construction-pure-and-edge-taxonomy-versioned.md), [ADR-0033](0033-register-governed-header-predicates-as-declaration-only.md), [ADR-0035](0035-conflict-aware-projection-and-resolution-aware-impact.md)
- **Follows:** [ADR-0036](0036-evidence-qualified-relation-publication.md), which already withholds these edges from publication

## Context

`build_topology_graph` emitted, for every artifact, a `CONTAINS` edge and — when the artifact's `artifact_type` was in `_ARTIFACT_RELATION_BY_TYPE` — a second edge from the repository to the same artifact:

| `artifact_type` | Promoted edge |
|---|---|
| `architecture-decision` | `GOVERNED_BY` |
| `governance` | `GOVERNED_BY` |
| `documentation` | `DOCUMENTED_BY` |
| `ci-workflow` | `VALIDATED_BY` |

`artifact_type` is a classification of the file. The legacy adapter derives it from the path (`README*` is documentation, any `.md` under a path containing `adr` is an architecture decision, `.github/workflows/` is a CI workflow); the Meta producer sets it from its own inventory. The promoted edge carried the artifact's own evidence: an observation that the file exists. Nothing in the rule's inputs establishes that the repository is governed by that file, documented by it, or validated by it, and a reader of the graph could not tell these edges from relations a producer actually declared.

Every rule in the graph builder that creates an edge was inspected:

| Rule | Input | Relationship-specific support | Decision |
|---|---|---|---|
| Repository `CONTAINS` artifact | artifact record | the artifact record names its repository (inventory) | Kept |
| Repository `GOVERNED_BY` / `DOCUMENTED_BY` / `VALIDATED_BY` artifact | `artifact_type` | none: classification only | **Removed** |
| Artifact `IMPLEMENTS` capability | `artifact.capabilities` | the artifact record lists the capability | Kept |
| Repository `DEPENDS_ON` repository | `upstream_repository_ids` | a dependency name matched an observed repository (ADR-0035 D5b) | Kept |
| Repository `OWNED_BY` owner | `owner_ids` | the repository record lists the owner | Kept |
| Implementer `IMPLEMENTS` / exposer `EXPOSES` capability | capability record | the capability record lists it | Kept; see *Owner decisions* |

## Decision

1. The graph builder no longer promotes `artifact_type` to `GOVERNED_BY`, `DOCUMENTED_BY` or `VALIDATED_BY`. `artifact_type` stays a property of the artifact node.
2. These relations remain canonical when a producer establishes them: a relationship declared in a Repository Model Packet payload, or a claim projection (`authority.canonical_contract` → `GOVERNED_BY` a declared contract reference) are unaffected.
3. Nothing else changes: no edge type is added or removed from the taxonomy, no schema changes, no second claim model, no inferred authority system. `CONTAINS`, claims and evidence records, every projector, external package references, generic reachability and resolution-aware impact are untouched.

## Consequences

Measured from identical pinned source packets:

| Pinned input | Edges | Removed | Retained edge IDs |
|---|---|---|---|
| `tests/fixtures/repository_model_packets/*` (3 packets) | 51 → 42 | 5 `DOCUMENTED_BY`, 2 `GOVERNED_BY`, 2 `VALIDATED_BY` | 42 / 42 unchanged |
| producer-emitted corpus fixture (5 roots + corpus packet) | 166 → 152 | 14 `DOCUMENTED_BY` | 152 / 152 unchanged |
| `foundational-two-repo` golden | regenerated | the same rule | unchanged |

- **Topology identity:** the Topology Packet semantic hash and `packet_id` move, because `edge_records` and `graph_records` change. Every other state collection — repositories, artifacts, capabilities, claims, evidence, flows, impact indexes, maturity, risks, conflicts, unknowns, corpus, candidate and readiness domains — is byte-identical. No entry of `TopologyPacket.policy_hashes` moves: the edge taxonomy is unchanged, and graph-builder rules are bound by the compiler build, not by a policy hash (as ADR-0035 records for the projection table).
- **Publication under the ADR-0036 strict policy:** the candidate set, candidate IDs and every effect key are unchanged; strict already skipped these edges. `plan_id` moves only because the plan's semantic view names the source topology hash.
- **Publication under the legacy 1.0.0 policy:** the removed edges' 9 and 14 relationship candidates disappear; every retained candidate keeps its candidate ID and effect key.
- **No retraction.** ADR-0027 forbids retracting a published fact because a later observation omits it. Nothing here retracts anything; any downstream record lowered from a removed edge under policy 1.0.0 stays as it is until a downstream decision says otherwise.
- **Stored packets.** A packet compiled before this decision still carries the promoted edges. ADR-0036 qualification recognizes them (`artifact-classification`) and never publishes them.

### Owner decisions

- Accepting a canonical identity change for every packet whose inputs contain an ADR, governance, documentation or CI-workflow file.
- Role capabilities. `capability:<repo>:<role>` records come from repository role classification in the legacy adapter, and the graph builder mirrors their `implemented_by` as `IMPLEMENTS`. Their evidence is the repository's own observation evidence. This is also classification-derived and is **preserved**: it is outside the three relations this record covers, and changing it changes capability semantics, which needs its own decision.
- `OWNED_BY` and graph-builder `DEPENDS_ON` carry repository-level aggregate evidence rather than a span naming the owner or the dependency. They are preserved; D5b already treats the observed dependency target as that producer's positive evidence.

## Alternatives considered

- **Keep the edges and mark them low confidence.** Rejected: confidence describes how sure a relation is, not whether a relation was observed. A low-confidence `GOVERNED_BY` still asserts governance.
- **Keep the edges and filter them only in publication.** That is ADR-0036 alone. It leaves canonical topology, impact consumers and reports stating relations no producer established.
- **Replace them with a new edge type** (for example `CLASSIFIED_AS`). Rejected by scope: the information is already the node's `artifact_type` property, and a new taxonomy member needs its own decision.

## Compliance and validation

- `tests/test_topology_graph_v5.py`: no classification-promoted edge although the fixtures contain every classified artifact type; `artifact_type` stays a node property and `CONTAINS` stays; the 14 retained edge IDs of the pre-ADR-0037 golden are pinned as literals and reproduced exactly; producer-declared `GOVERNED_BY`/`DOCUMENTED_BY`/`VALIDATED_BY` still flow through.
- `tests/test_publication_qualification.py`: compiled pinned topologies carry no classification-promoted edge; a pre-ADR-0037 topology carrying them still has exactly those skipped by strict qualification.
- `make generated-update` regenerated the `foundational-two-repo` golden and `HASH_LOCALITY_EVALUATION.json`; `make generated-check` is read-only.

## Related artifacts

- `src/l9_constellation_topology/topology/graph_builder.py`
- `src/l9_constellation_topology/compatibility/repo_card_adapter.py` (`_artifact_type`, unchanged)
- `tests/fixtures/topology_packets/foundational-two-repo/`
- `HASH_LOCALITY_EVALUATION.json`
