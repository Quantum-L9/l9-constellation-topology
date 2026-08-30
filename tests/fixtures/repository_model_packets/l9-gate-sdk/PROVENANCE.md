# Repository Model fixture provenance — `l9-gate-sdk`

**This packet was not produced by the current producer.** It is the output of
this repository's own legacy scanner, kept because a large part of the
publication suite compiles against it and its determinism is what makes those
tests stable.

| Field | Value |
|---|---|
| Producer | `l9-constellation-topology.legacy-scanner` 2.0.0 |
| Packet contract | `l9.repository-model` **1.0.0** |
| Profile | `bounded-direct-observation` 1.0.0 |

## What this fixture does and does not qualify

It qualifies **this compiler**: given a Repository Model Packet with these
contents, the topology it compiles and the plan it publishes are what the tests
assert. That is what it is for and it does that well.

It does **not** qualify the current producer. The real producer is
`l9-meta-injector.repository-model` 4.0.0 emitting `l9.repository-model`
**1.1.0**, and a test that passes against this packet says nothing about a
packet that one emits. Reading it as producer qualification is the specific
mistake this file exists to prevent — the two differ by a producer, a contract
minor version, and a profile.

## Where the current producer is qualified

- `tests/fixtures/repository_model_packets/l9-assertion-sample` —
  `l9-meta-injector.repository-model` 4.0.0, contract 1.1.0.
- `tests/fixtures/corpus_intelligence/producer-emitted/roots/*` — five
  Repository Model bundles emitted by the real producer, alongside the
  Corpus Intelligence packet compiled over them.

## Changing it

Do not hand-edit. `packet.json`, its payload and `manifest.json` are bound by
hash, and an edited byte fails the load rather than changing what the fixture
says. Regenerate with `scripts/generate_fixture_packets.py`, and expect every
downstream expectation that names a hash to move with it.
