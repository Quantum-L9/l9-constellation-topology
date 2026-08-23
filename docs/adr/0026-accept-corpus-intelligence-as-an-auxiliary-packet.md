# ADR-0026: Accept corpus intelligence as an auxiliary packet beside repository models

**Status:** Accepted
**Extends:** [ADR-0003](0003-repository-model-packets-are-canonical-inputs.md),
[ADR-0004](0004-topology-packet-is-the-canonical-output.md),
[ADR-0024](0024-compile-repository-model-assertions-into-semantic-claims.md)

## Context

`l9-meta-injector` now observes more than repositories. It reads folders, ZIP
archives and nested archives, and it decodes Word documents, PDFs, slide decks,
spreadsheets, and notebooks. Over that corpus it computes things no single root
can know: which artifacts are byte-identical across two disks, which documents
look like one body of work, how much test and CI evidence a candidate group
carries, and which candidates deserve a reasoner's attention.

Topology could compile none of it. Its only input was the Repository Model
Packet, whose payload domains describe one root's own contents.

The obvious move — widen `l9.repository-model` — is the one this decision
refuses.

## Decision

Accept a second, optional input packet: **`l9.corpus-intelligence` 1.0.0**. The
Repository Model Packet remains the canonical source-observation input and is
unchanged.

### Why not widen the repository-model packet

Because it would erase a distinction that cannot be reconstructed afterwards.

A repository-model assertion cites an exact span in a hashed file. A topic
candidate is the output of a similarity profile run at a chosen threshold. Both
are real evidence and they are not the same kind of statement — the first is
something a repository said about itself, the second is something an analysis
concluded about several. Carried in one payload domain, they arrive at the
compiler indistinguishable, and the compiler's central job is deciding what may
become canonical truth.

The failure that follows is quiet and terminal. A strong project candidate
becomes a `MEMBER_OF` edge; that edge enters impact analysis; impact feeds
maturity and risk; three layers down a similarity score is indistinguishable
from a declared dependency, and nothing in the output says which is which. The
separation has to exist at the boundary, because there is no later point at
which it can be reintroduced.

### What ADR-0003 does and does not say

ADR-0003 established that Repository Model Packets are canonical inputs. That
remains true and this decision does not weaken it: **every** artifact identity a
corpus packet mentions must resolve to an artifact some Repository Model Packet
carried, and a corpus packet naming a subject no repository packet observed is
refused.

What ADR-0003 is now read as saying precisely: repository-model packets are the
canonical source of **observation**. They are not the only admissible input.
Corpus intelligence is an analysis *over* a named set of them — it introduces no
new observations of its own, and it cannot widen the compile's subject set.

### The epistemic classes, carried in the type system

| Domain | Class | May become |
|---|---|---|
| `document_work_signals` | source-backed | semantic claims, projected relations |
| `exact_duplicate_relations` | deterministic | `DUPLICATE_OF` edges |
| `readiness_evidence` | derived measurement | a readiness record; never a score |
| `semantic_pair_relations`, `*_candidates` | candidate | candidate records only |
| `reasoning_candidates` | a request | a routing decision |

The separation is enforced by *where a record can be put*, not by a flag on it.
Candidates live in `TopologyState.candidate_relations` and
`candidate_clusters`; every canonical consumer — impact, flow, maturity, risk,
publication — reads `edge_records`. A boolean would have to be checked at each
traversal, and the first place it was forgotten would silently promote
similarity into dependency.

## Consequences

**Topology Packet 1.1.0.** Six payload domains are added — corpus, root,
candidate relations, candidate clusters, readiness, reasoning candidates — plus
`inputs.corpus_intelligence_packets`. A 1.0.0 bundle still loads: it declares no
refs for the new domains, and the loader reads an absent ref as an empty domain.

**A compile with no corpus input is unchanged.** `corpus_bundle_paths` defaults
to empty, the new domains come out empty, and nothing else moves.

**Structured evidence locators.** `EvidenceSourceRef` gains a discriminated
`SourceLocator`. A `.docx` work signal cites a block index, a `.pptx` signal a
slide and shape; a line number beside a structured locator is refused outright,
because a consumer reading only `line_number` cannot tell an invented coordinate
from a real one.

**One reconciliation engine.** Work signals and repository-model assertions both
lower to `SemanticInput` and reconcile through the same code under the same
predicate registry. A second engine for structured documents would file a
`.docx` claiming `Complete` and a `.md` claiming `WIP` as two self-consistent
facts in two collections, and the contradiction would be reported by neither.

**Edge taxonomy 2.0.0.** `DUPLICATE_OF`, `BLOCKED_BY`, `REFERENCES`, and a
declaration of which types canonical impact may traverse. `assess_impact`
previously defaulted to `set(EdgeType)`, which would have pulled byte identity
into dependency traversal the moment the member was added.

**Candidates may be lowered, never raised.** Topology's structural evidence can
contradict an upstream candidate and lower its confidence; it cannot corroborate
one into a higher class. The corroborating links were already available to the
profile that assigned the class, so raising here would override a decision made
under rules this compiler does not own, using an input that decision already saw.

**Fail-closed integrity.** A corpus packet whose identities do not resolve is
refused rather than partially compiled. Compiling the resolvable subset would
produce a topology that looks complete and silently omits whatever the producer
got wrong.

**A compatibility adapter, explicitly temporary.** The producer does not emit
`l9.corpus-intelligence` yet. `adapt-meta-corpus` reads a current corpus
generation and produces the canonical packet, so the compiler's API is the packet
and the raw file layout never becomes it. Its limitation is reported rather than
papered over: the current generation records work signals only as line spans, and
for formats without lines those signals are declined rather than given an
invented coordinate. See
[`docs/corpus-intelligence-boundary.md`](../corpus-intelligence-boundary.md).

## Alternatives considered

**Widen `l9.repository-model`.** Rejected above: it destroys the epistemic
distinction at the only point where it can be made.

**A confidence threshold that promotes strong candidates to canonical edges.**
Rejected. The threshold would be this compiler's, applied to a score computed
under a profile it does not own, to promote a claim whose underlying observation
never asserted the relation. A candidate at 0.99 is still a candidate; what
changes at adjudication is not the number.

**Emit candidates as edges with `authority: candidate`.** Rejected. It relies on
every downstream traversal remembering to filter, and puts the burden on the
consumer least able to know it matters. Separate fields cost one line at each
call site and cannot be forgotten.

**Publish candidate clusters as durable memory, marked provisional.** Rejected.
Durable memory is where the epistemic class disappears — a candidate published as
an observation reads downstream exactly like an observation. Candidates are held
by default and the hold is recorded, so "we held six project candidates" and
"there were no project candidates" stay different facts.

## Compliance and validation

- `tests/test_corpus_intelligence_contract.py` exercises the packet boundary's
  refusals: an unresolvable artifact, subject, candidate member, supporting
  relation, readiness subject, reasoning candidate, or evidence-pack reference
  each fail the packet closed. A duplicate cluster carrying two content hashes is
  refused, and a candidate whose type tag disagrees with the domain it sits in is
  refused at model construction.
- `tests/test_structured_locators.py` covers every locator kind, and pins the
  central refusal in both places it is enforced: `EvidenceSourceRef` rejects a
  line number beside a structured coordinate, and the packet validator rejects a
  line locator on a format without lines. It also asserts that an existing
  line-only reference serializes exactly as it did before the field existed.
- `tests/test_corpus_topology_compilation.py` asserts the containment
  structurally rather than by inspection: no candidate identity appears in
  `edge_records`, a project candidate creates no `MEMBER_OF` edge, a topic
  candidate cannot connect two artifacts under impact, a near-duplicate scored
  0.94 never becomes `DUPLICATE_OF`, and duplicate edges are excluded from
  default impact traversal while remaining reachable when asked for explicitly.
- The same suite covers the cross-format contradiction the shared reconciliation
  engine exists for: a `.docx` declaring `WIP` and a `.pptx` declaring `Complete`
  produce one conflict and two preserved claims, and neither is elected.
- `tests/test_corpus_hash_locality.py` pins the identity separation the corpus
  domain adds two new ways to break: changing `corpus_analysis_id` moves the
  topology semantic hash and re-keys **zero** canonical durable writes, while
  editing one document re-keys the facts that document supports and leaves
  unrelated ones untouched.
- `tests/test_corpus_publication_containment.py` asserts that every candidate
  domain, readiness record, and reasoning candidate is recorded as *held* rather
  than silently omitted, that no candidate identity reaches any generated intent,
  and that a work relation whose target did not resolve exactly is never
  published.
- `tests/test_meta_generation_adapter.py` proves the generation's bytes are
  unchanged across an adaptation, that a snapshot drifted from its own bundles is
  refused, and that a binary-document work signal is declined and reported rather
  than given an invented locator.

## Related artifacts

- `src/l9_constellation_topology/packets/corpus_intelligence.py`
- `src/l9_constellation_topology/packets/corpus_validator.py`
- `src/l9_constellation_topology/packets/corpus_bundle.py`
- `src/l9_constellation_topology/packets/corpus_evidence.py`
- `src/l9_constellation_topology/packets/document_signal_evidence.py`
- `src/l9_constellation_topology/packets/adapters/meta_generation.py`
- `src/l9_constellation_topology/domain/candidate.py`
- `src/l9_constellation_topology/domain/corpus.py`
- `src/l9_constellation_topology/domain/readiness.py`
- `src/l9_constellation_topology/domain/reasoning.py`
- `src/l9_constellation_topology/reconciliation/inputs.py`
- `src/l9_constellation_topology/topology/candidates.py`
- `src/l9_constellation_topology/topology/duplicates.py`
- `src/l9_constellation_topology/topology/work_projection.py`
- `src/l9_constellation_topology/topology/reasoning_router.py`
- `docs/corpus-intelligence-boundary.md`
- `docs/candidate-topology.md`
- [ADR-0003](0003-repository-model-packets-are-canonical-inputs.md)
- [ADR-0013](0013-keep-graph-construction-pure-and-edge-taxonomy-versioned.md)
- [ADR-0023](0023-declare-field-cardinality-before-detecting-conflicts.md)
- [ADR-0024](0024-compile-repository-model-assertions-into-semantic-claims.md)
- [ADR-0025](0025-separate-fact-identity-from-durable-write-identity.md)
