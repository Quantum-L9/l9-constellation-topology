# Candidate topology

Authority: [ADR-0026](adr/0026-accept-corpus-intelligence-as-an-auxiliary-packet.md).
Boundary: [`corpus-intelligence-boundary.md`](corpus-intelligence-boundary.md).

## Why candidates are carried at all

A corpus of forty thousand loose documents has almost no declared structure. The
similarity analysis is the only signal about which of them belong together, and
discarding it because it is uncertain would throw away the point of analysing a
corpus.

So candidates are first-class topology. They are recorded, enriched with
structural evidence, projected into the graph, reported, and routed for
reasoning. What they never become is canonical.

## What "never becomes canonical" is enforced by

Not a flag. A flag would have to be checked at every traversal, and the first
place it was forgotten would silently promote similarity into dependency.

Three structural properties instead:

**Separate state fields.** `TopologyState.candidate_relations` and
`candidate_clusters`. Impact, flow, maturity, risk, and publication all read
`edge_records`, so they cannot see a candidate.

**A separate type.** `CandidateRelationRecord` is deliberately not an
`EdgeRecord` and carries no `EdgeType`. It cannot be passed to the graph
builder, so it cannot be passed to it by mistake.

**An authority invariant on the record.** Every candidate record validates that
its confidence carries `Authority.candidate`. However strong the producer's
class, a similarity-derived grouping is a candidate: authority names where a
claim comes from, not how much a profile liked it.

The graph projection adds two visible markers on top: a `Candidate…` label and
`canonical: False`. Both are for readers and queries; neither is what does the
work. Candidate graph records are emitted as **nodes** rather than edges, because
the graph's edge records are built from `edge_records` and an edge-shaped
candidate would be one filter away from being traversed as canonical.

## Structural enrichment

The producer proposes groups from what a corpus scan can see. Topology holds the
compiled canonical graph, so it knows things the producer did not: which members
are byte-identical, which explicitly reference or depend on each other, which
supersede which, and what their reconciled claims say about status and kind.

`CandidateStructuralEvidence` records that, deterministically:

* `member_count`, `repository_count`, `root_count`, `archive_member_count`
* `internal_exact_duplicate_count`, `internal_explicit_reference_count`,
  `internal_dependency_count`, `internal_supersession_count`, `blocker_count`
* `work_status_distribution`, `work_kind_distribution`, `conflicting_status_count`
* `capability_count`, `external_dependency_count`

The distributions are there because a total hides the thing worth seeing. Four
members all declaring `WIP`, and four split two-and-two between `WIP` and
`Complete`, have the same member count and are completely different situations.

`structural_support_count` sums the explicit internal links. It is published
beside the candidate as a **measurement** and is never a term in its confidence.

## Lower, never raise

Structural contradiction may lower a candidate's confidence class and raise an
ambiguity flag. Structural corroboration may not raise it.

The asymmetry is deliberate. Two members referencing each other is a fact about
them, not evidence that the producer's threshold was correct — and the
producer's own pass already had those references available when it assigned the
class. Raising here would override a decision made under rules this compiler does
not own, using an input that decision already saw.

Lowering is different: finding that a "project" has members declaring
incompatible statuses is a reason to trust the grouping less, and saying so costs
nothing if the grouping was right anyway.

| Flag | Raised when | Effect |
|---|---|---|
| `conflicting_status` | members declare incompatible `work.status` | lower to `weak` |
| `structurally_disconnected_members` | no explicit internal link at all | lower to `moderate` |
| `spans_multiple_roots` | members live in more than one root | flag only |

`structurally_disconnected_members` does not make a candidate wrong. Nothing in
a corpus may connect two documents that are unmistakably about one project. It
means the grouping is unsupported by observed structure, which is a different
and useful thing for a reader to know.

## Readiness evidence

Counts of artifacts and declarations observed. Nothing is combined, weighted,
normalized, or projected forward.

`FORBIDDEN_READINESS_FIELDS` names what the record must never gain —
`percent_complete`, `priority_score`, `strategic_value`, `ROI`,
`production_ready`, `recommended_build_order`, `readiness_score`,
`completion_ratio` — so the refusal is testable rather than merely stated.

The obvious next step is the mistake: divide test files by source files, call it
a coverage proxy, call the result readiness. That number looks like a
measurement and is not one — a repository with one thorough test file and one
with forty trivial ones score identically, and a body of work whose documents are
mostly undecodable scores as though it had nothing in it. Once a score exists,
downstream will rank on it.

`coverage_gap_count` sits beside the counts for the same reason: thin evidence
presented at full confidence reads as a thin project. A subject whose members are
largely unreadable is reported at reduced confidence.

Readiness never claims `Authority.source`. Counting test files is deterministic;
"there are four files named like tests" is still not a claim any repository made
about itself.

## The reasoning handoff

Deterministic, and performs no reasoning. No model is called; the router is a
pure function of the topology it is handed. Rows routed to `NONE` are emitted
rather than dropped, so the queue can be checked for the property that matters
most: that exact duplicates and similarity-only candidates never reach a
reasoner.

Both decisions are recorded — `upstream_recommended_reasoning_type` and
`topology_recommended_reasoning_type`. Keeping only the second would make a
disagreement invisible, and a disagreement is the thing worth auditing.

**Escalates** on ambiguity a reasoner could resolve: a confirmed claim conflict
between members, a reference that matched several artifacts, an ambiguous
supersession, a project candidate nothing structurally links, a candidate
spanning roots and versions.

**De-escalates** on questions already answered: a group whose members are wholly
byte-identical has nothing to adjudicate — every copy is the same file, and a
reasoner would spend its attention confirming equality a hash already decided.
Likewise a grouping fully explained by an exactly resolved supersession.

De-escalation never beats escalation. A group that is wholly byte-identical *and*
carries a confirmed conflict still goes to a reasoner: the conflict is a real
question the hashes did not answer.

`bounded_neighborhood_refs` carries entities one explicit canonical hop from the
candidate's members. One hop, not a traversal — an unbounded neighbourhood is the
corpus, and handing a reasoner the corpus is not a handoff.

## Publication

Candidate domains are held by default, and the hold is recorded with
`policy.candidate_domain_not_published`. Readiness is held with
`policy.readiness_evidence_not_published`; reasoning candidates with
`policy.reasoning_candidate_not_published`.

Durable memory is where the epistemic class disappears: a candidate published as
an observation reads downstream exactly like an observation, and nothing in the
record says it was ever a proposal. "These files are the same project" does not
become durable memory before a World Model or a human has adjudicated it.
