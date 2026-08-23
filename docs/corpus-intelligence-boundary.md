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
| `docx` | `block_index`, `block_kind` | Word |
| `pptx` | `slide_number`, `shape_index` | PowerPoint |
| `spreadsheet` | `sheet`, `cell_or_range` | Excel |
| `notebook` | `cell_index`, `cell_type` | Jupyter |
| `csv` | `row` | delimited text |
| `html` | `stable_node_index` | HTML |

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

`l9-meta-injector` does not emit `l9.corpus-intelligence` yet. Until it does:

```bash
l9-topology adapt-meta-corpus --meta-generation <generation-dir> --out corpus-bundle
l9-topology compile-packet \
  --input-bundle root-a --input-bundle root-b \
  --corpus-bundle corpus-bundle --out topology
```

The adapter reads the generation and never writes to it, emits through
`OutputSink` to a separate destination, and rescans no source tree.

### Its limitation, stated

The current generation records work signals only as repository-model assertions
carrying a line span. For Markdown, text, CSV, HTML, and notebooks that span is a
real coordinate and becomes a line locator. For Word, PDF, PowerPoint, and
spreadsheets it is not: the producer joins a document's decoded blocks with
newlines before interpreting, so the recorded line indexes a derived string.

Those signals are **declined**, and the count and reason come back in
`MetaAdaptationReport.unadaptable_signals` and on the CLI's JSON output.

Mapping line *n* to block *n-1* is available and wrong. It holds only if no
decoded block text contains a newline, which the generation gives no way to
check, and a locator right most of the time cannot be distinguished from a
correct one afterwards.

Closing the gap means the producer emitting per-signal structured locators —
which is the same change that would let it emit `l9.corpus-intelligence`
directly, at which point this adapter can be retired.

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
