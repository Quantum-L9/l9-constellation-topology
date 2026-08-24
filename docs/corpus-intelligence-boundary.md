# The corpus intelligence boundary

Authority: [ADR-0026](adr/0026-accept-corpus-intelligence-as-an-auxiliary-packet.md).
Candidate semantics: [`candidate-topology.md`](candidate-topology.md).

## What crosses it

```
l9-meta-injector
   |
   +--> per-root l9.repository-model ---------+
   |                                          |
   +--> l9.corpus-intelligence ---------------+
                                              |
                                              v
                               l9-constellation-topology
                                              |
                     +------------------------+--------------------+
                     |                                             |
                     v                                             v
            canonical topology                            candidate topology
                     |                                             |
                     +------------------------+--------------------+
                                              |
                                              v
                                reasoning handoff / publication
```

Two inputs, kept apart because they are different kinds of statement.

A **Repository Model Packet** is source observation: what one root contains, and
what it says about itself, each assertion citing an exact span in a hashed file.

A **Corpus Intelligence Packet** is an analysis *over* a named set of those
packets. It introduces no observations of its own. Every artifact identity in
every one of its domains must resolve to an artifact one of the packets it names
actually carried, and a packet naming a subject no repository packet observed is
refused rather than partly compiled.

## The five epistemic classes

The packet's payload is split by how much each domain can be trusted to mean,
and the split is structural rather than a convention:

| Domain | Class | Compiles to |
|---|---|---|
| `document_work_signals` | source-backed | semantic claims, projected work relations |
| `exact_duplicate_relations` | deterministic | `DUPLICATE_OF` edges |
| `readiness_evidence` | derived measurement | `ReadinessEvidenceRecord` |
| `semantic_pair_relations` | candidate | `CandidateRelationRecord` |
| `topic` / `project` / `consolidation_candidates` | candidate | `CandidateClusterRecord` |
| `reasoning_candidates` | a request | `TopologyReasoningCandidate` |

Canonical records land in `edge_records`, `semantic_claims`, and the graph.
Candidate records land in `candidate_relations` and `candidate_clusters`, which
no canonical consumer reads. That is the whole enforcement: impact, flow,
maturity, risk, and publication all traverse `edge_records`, so a candidate
cannot reach them by being forgotten.

## Structured evidence locators

A Markdown file has lines. A Word document, a slide deck, a workbook, and a PDF
do not. `EvidenceSourceRef.locator` is a discriminated union over the coordinate
systems that actually exist:

| Kind | Fields | Format |
|---|---|---|
| `line` | `start_line`, `end_line` | text, markdown |
| `pdf` | `page_number`, `block_index` | PDF |
| `docx` | `block_index`, `block_kind`, `part` | Word |
| `pptx` | `slide_number`, `shape_index`, `part` | PowerPoint |
| `spreadsheet` | `sheet`, `cell_or_range` | Excel |
| `notebook` | `cell_index`, `cell_type`, optional in-cell span | Jupyter |
| `csv` | `row`, optional `column` | delimited text |
| `html` | `stable_node_index`, `node_path` | HTML |

`part` is on the OOXML kinds because block 3 of a document body is not block 3
of a footnote, and a notes slide carries its own shape ordinals: the ordinal
alone does not identify the block. `node_path` is on `html` because the node
index is stable only relative to a traversal, so the path is the half a reader
can actually follow. A notebook cell does have lines, so a span *within* one is
a real coordinate rather than an invented one.

The producer names these kinds `line_span`, `pdf_page_block`, `docx_block`,
`pptx_shape`, `spreadsheet_cell`, `notebook_cell`, `csv_row` and `html_node`.
The adapter renames them and nothing else: no coordinate is converted into
another, because the whole point of a structured locator is that a page is not
a line.

A line number beside a structured locator is refused. `line 7` of a `.docx`
names nothing an operator can open, and a consumer reading only `line_number`
cannot tell an invented coordinate from a real one — which makes a wrong locator
strictly worse than an absent one.

Existing repository-model assertions keep `line_number` alone and carry no
locator. Their evidence hashes exactly as it did before the field existed, so
every already-published effect key stays where it was.

## One reconciliation engine

Work signals and repository-model assertions both lower to `SemanticInput` and
reconcile through `reconcile_assertions`, under the same predicate registry.
Downstream cannot tell which producer a statement came from.

That is the point rather than a simplification. A `.docx` plan declaring
`work.status = Complete` and a `.md` plan declaring `work.status = WIP` are one
subject with two competing answers. Two engines would file them as two
internally consistent facts in two collections, and the contradiction — the most
useful thing a corpus can surface — would be reported by neither.

Work predicates are declared in the same registry (`predicate policy 1.1.0`):

* **single-valued**, so divergence is a real conflict: `document.title`,
  `work.status`, `work.kind`;
* **set-valued**, so several are simultaneously true: `document.heading`,
  `work.task.open`, `work.task.completed`, `work.milestone`,
  `work.depends_on`, `work.blocked_by`, `work.references`, `work.supersedes`,
  `work.superseded_by`.

## Exact relations

`DUPLICATE_OF` means byte identity and nothing weaker. It is sourced only from
`exact_duplicate_relations`, the one domain carrying a content hash both
endpoints share, so there is no code path from a similarity score to this edge.

* Symmetric, so identity is computed over the ordered pair and the relation is
  one edge whichever side the producer wrote first.
* Emitted as a **star** per cluster: `n` byte-identical files produce `n-1`
  edges, not `n(n-1)/2`. A corpus with a hundred copies of one licence file
  would otherwise carry 4,950 edges saying one thing.
* Excluded from default impact traversal. Byte identity is not a dependency;
  following it would make every copy of a shared file a dependency hop. Asking
  for it explicitly still works — that is a different question, asked
  deliberately.
* Generates no runtime flows.

Explicit work relations project to `DEPENDS_ON`, `BLOCKED_BY`, `REFERENCES`, and
`SUPERSEDES`. Targets resolve by exact artifact id, exact portable path, or
exact archive path, and only when the match is **unique**. Two files at
`README.md` make a reference to `README.md` ambiguous, and an ambiguous
reference is no evidence at all: it becomes an explicitly external endpoint plus
an unknown naming both possibilities. There is no fuzzy matching, no embedding
input, and no inference from candidate membership.

## Compatibility ingress

`l9-meta-injector` does not emit `l9.corpus-intelligence` as a packet yet, but
it does emit the whole of what such a packet would carry. Until the packet
itself arrives:

```bash
l9-topology adapt-meta-corpus --meta-generation <generation-dir> --out corpus-bundle
l9-topology compile-packet \
  --input-bundle root-a --input-bundle root-b \
  --corpus-bundle corpus-bundle --out topology
```

The adapter reads the generation and never writes to it, emits through
`OutputSink` to a separate destination, and rescans no source tree.

### Two documents, one of them a contract

The producer writes two documents about the same claims, and only one is a
machine contract.

`document-signals.json` is a **report**. Its per-format `records` array is
capped — 50 — and it says so: `signal_count` is what the corpus found,
`listed_signal_count` is what the array holds, `omitted_signal_count` is the
difference. On a real 214-signal generation the report lists 73. A consumer
adapting it would ingest 73 and then report perfect conservation against 73:
every number self-consistent, 141 signals gone, and nothing in the output saying
so. The adapter reads its count for comparison and never as a source of signals,
and refuses a generation whose report claims more than its payload holds.

`document-work-signals.jsonl` is the **payload**: one line per signal, never
sampled, never truncated. `document-work-signals.manifest.json` beside it is
what makes the payload checkable on arrival.

### The manifest is verified, not read back

Every integrity field is recomputed here under the producer's own definitions —
the byte length, the SHA-256 over the exact emitted bytes, and the semantic hash
over the records themselves. A manifest that merely *contains* a hash proves
nothing; one whose hash this reader reproduces proves the payload arrived as it
left. Declared `document_count`, `by_format` and `by_predicate` breakdowns are
checked too, and a payload carrying a format the manifest does not declare is
refused — silence about a format is not the same as declaring zero of it.

A duplicate `signal_id` is refused rather than collapsed. Two records under one
identity are either one record written twice or two claims sharing an identity,
and the payload gives no way to tell which.

### Two identity domains

The producer addresses an artifact two ways: `artifact_id` inside the corpus,
`rmp_artifact_id` inside its root's Repository Model Packet. This compiler
resolves in the second, so that is what becomes `DocumentWorkSignal.artifact_id`;
the corpus id is kept beside it as `corpus_artifact_id` rather than discarded,
because a claim nameable in only one domain is a claim one of its two readers
cannot check.

The duplicate, pair, candidate and reasoning documents name only the corpus id.
The snapshot states each artifact's `virtual_source_id` beside the root and
root-relative path it was observed at, and a root's bundle addresses the same
file by that path, so the translation is exact. An id whose path the bundle does
not carry is left untranslated and the packet boundary refuses it, rather than
the adapter inventing a binding.

### Root identity is read, never derived

`root_identity_class` says whether a root's identity was declared or inferred.
`source_kind` says what sort of thing the root is. They answer different
questions, and reading the first from the second published inferred roots
carrying a declared root's authority — wrong in a way nothing downstream could
detect. A current-mode generation that omits the field is refused rather than
defaulted.

### Signal conservation

The count is carried through every hop and checked at each one:

```
manifest -> parsed -> adapted -> packet -> bundle roundtrip -> semantic inputs -> claim lineages
```

Every record in a verified payload is adapted. There is no path that skips one:
a payload whose count was verified and then silently reduced would conserve its
total against a number that no longer described it.

### Current and legacy modes

Presence of either half of the payload commits a generation to **current** mode.
A manifest without a payload, or a payload without a manifest, fails closed
rather than quietly demoting to legacy and reporting success over a subset
nothing verified.

**Legacy** mode remains for generations predating the payload. It reconstructs
work signals from line-bearing repository-model assertions, reports
binary-document signals as unadaptable rather than giving them an invented
coordinate, labels itself in `adaptation_mode`, and — stated plainly — does not
qualify the current producer contract. It never reads the sampled report as a
source of signals either.

Both modes report `adaptation_mode`, `producer_revision`, the conservation
chain, the per-format and per-predicate tallies, and the root-identity-class
counts, on `MetaAdaptationReport` and on the CLI's JSON output.

## Publication

Eligible: semantic claims from work signals, `DUPLICATE_OF`, and exactly
resolved `DEPENDS_ON` / `BLOCKED_BY` / `REFERENCES` / `SUPERSEDES`.

Held: every candidate domain, readiness evidence, and reasoning candidates.

A work relation whose target did not resolve exactly is skipped with
`relation.work_target_not_exactly_resolved`. The declaration is real and stays in
canonical topology; publishing it would state a *resolved* relation downstream,
and a consumer reading only the assertion cannot tell the endpoint was never
observed.

Holds are recorded rather than left implicit. A plan that silently omitted
candidates would be indistinguishable from a plan over a corpus that produced
none.
