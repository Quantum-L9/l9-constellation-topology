# Current validation report

Evidence for the corpus-intelligence ingress, bound to the exact revisions it
was produced against. Regenerate rather than amend: a report that outlives the
heads it names is a report about nothing.

## Bound revisions

| Role | Repository | Revision |
|---|---|---|
| Consumer (this PR) | `Quantum-L9/l9-constellation-topology` | `d1c6ee8fa9f9233f026e6867e3154363b10df597` |
| Base | `Quantum-L9/l9-constellation-topology` `main` | `17f7453c402eb715790466699c759d98dabd3811` |
| Producer | `Quantum-L9/l9-meta-injector` PR #83 | `d387c5e312403a219921af9aadf0e97cfc377ad2` |
| Downstream contract | `Quantum-L9/l9-graphiti-memory` | `f690d3f928391264cbffb8f507ad9acbba339603` |

Environment: Python 3.12.3, uv 0.8.17, Linux-6.18.44-fc-v21-x86_64-with-glibc2.39.

The producer revision moved during this work: an earlier head, `d60d8f8`,
carried no complete work-signal payload at all, and the ingress was correctly
refused against it. Everything below is against `d387c5e`.

## Suite results

| Check | Result |
|---|---|
| `uv run pytest` | 543 passed, 1 skipped |
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | clean |
| `uv run mypy src/l9_constellation_topology` | no issues, 150 source files |
| `scripts/validate_release_readiness.py` | 0 blocking findings |
| `scripts/architecture_boundary_check.py` | passed |
| `make validate` | exit 0 on a clean tree |

## Real producer/consumer qualification

Not synthesized. A two-root corpus was built with genuine bytes in every format
the decoders claim — the document fixtures are the producer's own test helpers
used unmodified, so an OOXML fixture is a real ZIP of real parts and the PDF is
a real PDF with a FlateDecode stream and a correct xref. It includes a DOCX
inside a ZIP and a byte-identical file under both roots.

The producer's canonical CLI (`scripts/local-source-cli.js` at `d387c5e`) then
produced a generation, which was read and never written to.

### Signal conservation

| Stage | Count |
|---|---|
| producer manifest `record_count` | 214 |
| parsed from `document-work-signals.jsonl` | 214 |
| adapted to `DocumentWorkSignal` | 214 |
| carried in the corpus-intelligence packet | 214 |
| unadaptable | **0** |

`adaptation_mode: current_complete`.
`producer_revision: corpus-analysis:e07a53d1a8576640d972d3211e6651e4315e1f14…`.

### The sample boundary

The sampled report lists **73** of those 214, because `docx` is capped at 50
with 141 stated as omitted. This is the measurement that makes
"`document-signals.json` is not the machine contract" a testable claim rather
than a stylistic preference: adapting the report would have ingested 73 signals
and then reported perfect conservation against 73 — every number
self-consistent, 141 signals gone, nothing in the output saying so.

Below the cap the two documents agree exactly, which is why a smaller corpus
cannot demonstrate this.

### Per-format results

| Format | Signals | Locator kind |
|---|---|---|
| docx | 191 | `docx` |
| html | 5 | `html` |
| pdf | 5 | `pdf` |
| pptx | 5 | `pptx` |
| csv | 4 | `csv` |
| ipynb | 3 | `notebook` |
| xlsx | 1 | `spreadsheet` |

Predicates observed: `document.heading`, `document.title`, `work.depends_on`,
`work.kind`, `work.milestone`, `work.references`, `work.status`,
`work.task.open`.

Every signal carries the coordinate the producer stated. None was given an
invented one, and none was declined.

Markdown produced **zero** document work signals in this generation: the
producer records markdown work claims as ordinary repository-model assertions,
which reach topology through the RMP rather than through this boundary. Stated
because a reader comparing the format table against the corpus would otherwise
notice the gap and have to guess at it.

### Corpus packet

`adapt-meta-corpus` emitted a packet that passes integrity validation:
214 document work signals, 1 exact duplicate relation, 64 semantic pair
relations, 2 topic candidates, 1 project candidate, 2 consolidation candidates,
5 reasoning candidates. The generation's bytes are unchanged across the
adaptation.

### Compilation

Assertion conservation through reconciliation, from the compiled receipt:

```
input_assertion_count:     230   (16 repository-model + 214 work signals)
evidenced_assertion_count: 230
claimed_assertion_count:   230
semantic_claim_count:      141
assertions_without_claim:    []
assertions_without_evidence: []
```

Every schema check, every invariant check, and every cross-reference check
passed.

## Open blocker: unbacked producer repository records

**The end-to-end compile does not complete**, on one check:

```
evidence-canonical-claims-backed  FAILED
Canonical claims without evidence: repo:rootA, repo:rootA, repo:rootB, repo:rootB
```

The producer's Repository Model Packet declares:

```json
"repository_id": "repo:rootA",
"confidence": { "authority": "validated-machine", … },
"evidence_refs": []
```

Topology requires any record claiming `source`, `validated-machine` or
`derived` authority to carry evidence. The producer is asserting machine-validated
authority with nothing behind it.

**This is not caused by the corpus work.** Compiling the two Repository Model
Packet bundles *alone*, with no corpus bundle at all, fails identically. It
blocks any real Meta generation from compiling in topology, corpus or not.

It is not fixed here, for two independent reasons:

- `l9-meta-injector` is read-only under this contract.
- Relaxing the check would be weakening a validator to force a pass. That check
  exists precisely to stop unbacked authority claims propagating, and an
  evidence-less `validated-machine` record is what it is for.

Resolving it needs the producer either to attach evidence to its repository
records or to emit them at an authority that does not claim machine validation.

## What this report does not claim

- The final compile step is **not** green; see the blocker above.
- Publication containment, hash locality and effect identity are covered by the
  suite but have **not** been re-measured against this real generation, because
  they run on a compiled topology packet and no packet was committed.
- Legacy-mode adaptation is exercised by the suite against a synthesized
  generation only. It does not qualify the current producer contract, and says
  so in its own `adaptation_mode`.

## Standing assertions

- The current Meta document-work-signals machine payload is consumed in full;
  `document-signals.json` is not used as the canonical ingestion source.
- Current-producer unadaptable document work signal count is zero.
- `root_identity_class` is read directly from the producer and is not inferred
  from `source_kind`.
- Candidate analysis was not promoted to canonical truth.
- No Meta source or generation output was mutated.
- No LLM reasoning was performed.
- Zero durable dispatches occurred.
- Merge is not authorized.
