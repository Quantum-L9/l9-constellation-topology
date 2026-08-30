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
| Producer revision | `79bd7a31f56958095a275b2fda7380df8e1ec69a` |
| Packet type | `l9.corpus-intelligence` 1.0.0 |
| Packet id | `packet:a4a2b6d4efca458ef462283e1cf4a7a3cf924bbc76e4c7fd3f768d64bff34517` |
| Generated | 2026-08-30 |
