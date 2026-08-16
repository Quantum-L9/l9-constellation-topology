# Evidence Model

Evidence is a first-class record with a stable ID, subject, optional field, production stage, evidence class, source type, source reference, value, decomposed confidence, producer, and producer version.

Authority order:

1. Human-declared source
2. Validated Repository Model Packet evidence
3. Deterministic direct observation
4. Cross-record deterministic derivation
5. Heuristic derivation
6. Model-assisted inference
7. Prior generated topology

Conflicts are preserved as records. Unknowns are explicit records. Neither is resolved through last-write-wins behavior.

## Cardinality: multiplicity is not contradiction

Divergent observed values are classified by the fact's declared cardinality, not
by how many of them there are. A repository written in Python and Shell holds two
true values of one set-valued fact; it does not hold two competing answers to one
question.

| Cardinality | Meaning | Divergence becomes |
|---|---|---|
| `single` | at most one value is true at a time | a conflict |
| `set` | several values are simultaneously true | an aggregate |
| `unknown` | the policy declares no rule for this fact | an explicit unknown |

Set-valued facts — languages, workflows, package managers, governance and ADR
references, artifact and capability identifiers, declared actions, and the other
collections named in `reconciliation/cardinality.py` — aggregate deterministically
and retain every contributing evidence reference. A field with no declared
cardinality is never guessed in either direction: nothing is aggregated, nothing
is called a contradiction, and an unknown record carries the divergence and its
evidence forward.

This matters beyond reporting accuracy. Publication holds any candidate whose
consumed field is in conflict, so treating multiplicity as contradiction silently
withholds facts that were never in doubt.

Reconciliation semantics are compiler policy, so they are versioned
(`RECONCILIATION_POLICY_VERSION`) and hashed into `TopologyPacket.policy_hashes`.
Because `policy_hashes` participates in the topology semantic view, a change to
what counts as a conflict cannot silently reuse the identity of a packet compiled
under the previous meaning.
