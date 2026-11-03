# Producer-emitted Corpus Intelligence bundle

This bundle was **not built by this repository**. It is the output of the real
producer, committed here so the boundary between the two is tested by something
that actually crossed it.

## Why it exists

Every other corpus fixture in this repository is constructed in Python, with
this repository's own models, by `tests/corpus_fixtures.py`. That is the right
shape for testing what the compiler does with a packet, and it cannot test
whether the producer and the consumer agree — a bundle built with the
consumer's own canonicalizer will always verify against it. It proves the
Python side self-consistent and nothing more.

Two divergences were live at the moment this fixture was first generated, both
invisible to every existing test, and both fatal to every bundle the producer
could emit:

- the producer declared payload hashes computed over the canonical form with no
  trailing newline, while the consumer hashes the exact bytes of the file;
- the producer wrote `"root_packet_id":null` where the consumer, canonicalizing
  through `model_dump(mode="json", exclude_none=True)`, writes nothing at all —
  so the semantic hash disagreed after every byte-level hash had verified.

A third was structural: the producer's canonical renderer refused non-integer
numbers, so no pair score could be serialized, and the two runtimes format
floats differently in three ways even when their shortest round-trip digits
agree.

## What it contains

    corpus-intelligence/    the l9.corpus-intelligence bundle: packet, manifest,
                            and one file per payload domain
    roots/<root>/           the Repository Model bundle each observed root
                            produced, which the packet's identities resolve against

The corpus behind it is the multi-root fixture the producer's own CLI tests use,
plus a root of block-bearing documents — DOCX, PPTX, XLSX, notebook, PDF, HTML.
That root is deliberate: the multi-root corpus is Markdown, JSON and TypeScript,
whose claims travel as repository-model assertions and leave
`document_work_signals` correctly empty. Work signals are the channel for
formats a block decoder reads, and their locators — six coordinate systems, each
renamed on the way across — are the part of this boundary most likely to be got
wrong and were the part no test crossed.

## Regenerating

In a checkout of `Quantum-L9/l9-meta-injector`:

    npx tsx tests/helpers/emit_corpus_intelligence_fixture.ts <destination>

then copy the result over this directory and update the revision below.

Regenerate when the contract changes on either side, or when the producer's
canonicalization does. Do **not** hand-edit any file here: every one of them is
bound by hash to the others, and an edited byte fails the load rather than
changing what the fixture says.

## Recorded provenance

| | |
|---|---|
| Producer repository | `Quantum-L9/l9-meta-injector` |
| Producer revision | `c53ef3aa0ccea04af2adfe67800ad09843b6e0fe` (tag `v4.3.0`, maintained `v4`) |
| Producer version | `l9-meta-injector.corpus-intelligence` 4.3.0 over `l9.repository-model` 1.1.0 roots |
| Packet type | `l9.corpus-intelligence` 1.1.0 |
| Packet id | `packet:52c365061ae6e0a5f0dfd2746d50f53e64f1d7c3e58342849c8beea8e08c24e5` |
| Generated | 2026-11-03 |

Regenerated at the v4.3.0 release so the fixture is bound to a released
producer rather than a PR head. Against the `ebc0dd30` emit, the
`python-route-observation/v1` extractor moved 1.1.0 → 1.2.0 (so the
interpretation profile hash and every derived artifact, evidence, block and
relation id moved with it) and the validator version reads 4.3.0. Every payload
domain keeps its record count (42 work signals with the same per-format split,
188 semantic pairs, 26 exact duplicates, 22 consolidation, 36 reasoning,
14 topic and 4 project candidates); work-signal order follows the moved
artifact ids. Two emits at that revision differ only in the wall-clock
`created_at` of the corpus-intelligence packet and manifest; packet ids and
semantic hashes are identical. Emitted from a `git archive` snapshot of the tag
with `npm ci --ignore-scripts`; `npx` resolved `tsx` 4.23.15, which is not in
the producer's lockfile.

Generated at `ebc0dd30d8527ac8812da2995181306458ee5dde` before that (PR-113
head, producer 4.2.0, packet `packet:ef022aac…ec62090`, 2026-10-29).

Previously generated at `79bd7a31f56958095a275b2fda7380df8e1ec69a` (producer 4.0.0,
packet `packet:a4a2b6d4…bff34517`, 2026-08-30). Regenerated at v4.2.0 because the
producer's repository-model contract changed on its side: every repository
record now carries an observed evidence record (`artifact_ids` over the
inventory walk), which is what lets these five roots and the corpus bundle
compile here with `evidence-canonical-claims-backed` passing instead of the
refusal `CURRENT_VALIDATION_REPORT.md` recorded against 4.0.0.
