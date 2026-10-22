# Current validation report

Evidence for the producer/consumer boundary, bound to the exact revisions it
was produced against. Regenerate rather than amend: a report that outlives the
heads it names is a report about nothing.

This report supersedes the one written against producer `d387c5e`, whose open
blocker (unbacked `validated-machine` repository records) is closed on the
producer side by `l9-meta-injector` v4.2.0 (its ADR-055). The end-to-end
compile that report could not complete is green below.

## Bound revisions

| Role | Repository | Revision |
|---|---|---|
| Consumer (this change) | `Quantum-L9/l9-constellation-topology` branch `agent/claude-code/topology-align-meta-v4.2.0` | the commit carrying this report |
| Base | `Quantum-L9/l9-constellation-topology` `main` | `fe85ed919596ce628f96368430b1ae9e09af0b17` |
| Producer | `Quantum-L9/l9-meta-injector` release `v4.2.0` (maintained `v4` line) | `953b7cba7a2a694abf02f73d1261a895c2bbc3d3` |
| Downstream contract | `Quantum-L9/l9-graphiti-memory` | `f690d3f928391264cbffb8f507ad9acbba339603` (unchanged from the prior report; not re-verified in this run) |

Environment: Python 3.12.13, uv 0.11.32, Linux-6.18.44-x86_64-with-glibc2.39.

What this change binds: `.github/workflows/l9-pr-validate.yml` pins the PR
compile proof's `meta_ref` to the producer revision above (it was `e78b3c5`, a
pre-`v4` revision), the producer-emitted corpus fixture is regenerated at that
revision, and `QUALIFICATION.json` is regenerated from v4.2.0 bundles of the same
two external repositories at the same recorded source revisions.

## Suite results

| Check | Result |
|---|---|
| `uv run pytest` | 664 collected: 661 passed, 2 skipped, 1 failed — the failure is `test_release_readiness_has_no_blocking_findings`, and every finding it lists is a `manifest_omission` for a file the agent worktree wiring places in the checkout (`.cursor/`, `.vscode/`, `.l9/uv-environment.lock`); none of those paths exists in a clean checkout, and `l9-pr-validate` runs the same gate on one |
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | clean |
| `uv run mypy src/l9_constellation_topology` | no issues, 154 source files |
| `scripts/validate_workflows.py` | passed (the re-pinned `meta_ref` is a 40-hex revision; every `uses` stays an exact pin) |
| `scripts/validate_contracts.py` | passed |
| `scripts/architecture_boundary_check.py` | passed |
| `scripts/verify_determinism.py` | passed |
| `make generated-check` | passed after `make fixtures-update` and `make hash-locality-update`. On `main` it fails: the `l9-gate-sdk` sample tree changed on 2026-09-05 (`057f040`, #21) after its packet fixture was last generated on 2026-08-24 (`dc25873`), so `fixtures-check` reported the packet, receipt and manifest stale on an untouched `main` checkout too. The regenerated `l9-gate-sdk` packet and the `foundational-two-repo` topology bundle differ only in the sample's content-derived `source_revision` (`tree:c9afc18…` → `tree:2f1b01a…`) and the hashes that follow from it; `HASH_LOCALITY_EVALUATION.json` follows those hashes |
| `tests/test_producer_emitted_corpus_packet.py`, `tests/test_corpus_ingress.py` | 16 passed against the regenerated fixture |

## Real producer/consumer qualification

Not synthesized. All producer bundles below were emitted by the v4.2.0
producer at `953b7cb`, built from its committed `dist/`, and read here through
the same loader a real compile uses.

### The open blocker is closed

The previous report ended on:

```
evidence-canonical-claims-backed  FAILED
Canonical claims without evidence: repo:rootA, repo:rootA, repo:rootB, repo:rootB
```

because the producer's repository record claimed `validated-machine` authority
with `"evidence_refs": []`. At v4.2.0 every repository record carries an
observed evidence record (field `artifact_ids`, source path `.`, the source
revision, the artifact count and the snapshot semantic hash), referenced before
any derived fact. On the regenerated five-root corpus fixture:

```
roots/corpus       repositories[0] repo:corpus  authority validated-machine  evidence_refs 3
roots/Documents    …                            evidence_refs non-empty
roots/OldSSD       …                            evidence_refs non-empty
roots/ArchiveZips  …                            evidence_refs non-empty
roots/Backup       …                            evidence_refs non-empty
```

### End-to-end compile

`l9-topology compile-packet` over all five root bundles with the corpus bundle
(`--corpus-bundle`) under this repository's own topology profile:

```
status:             passed
validation_status:  passed
packet_id:          packet:203c8e492d334b324c5a8bf9dfb2cb3f4395e27f63ac9cfa8eabde0b402daf94
corpus_intelligence_packets: [packet:1165b10de751b2789b53bc9e4aa951fdfc545667f28290c004ae2c2f1e8ace8b]
outputs:            23 written (atomic bundle commit), validation receipt included
```

Every schema check, every invariant check and every cross-reference check
passed. This is the compile the prior report could not complete.

### Producer-emitted corpus fixture

`tests/fixtures/corpus_intelligence/producer-emitted` was regenerated with
`npx tsx tests/helpers/emit_corpus_intelligence_fixture.ts` at `953b7cb`
(producer `l9-meta-injector.corpus-intelligence` 4.2.0 over
`l9.repository-model` 1.1.0 roots, profile
`meta-injector-repository-interpretation` 1.1.0). Its `PROVENANCE.md` records
the revision, the packet id and why it was regenerated. The same file set as
before; every packet, manifest and receipt changed bytes, and the consumer
loads, verifies and resolves all of it (16 tests).

### Assertion activation qualification

`QUALIFICATION.json` was regenerated from v4.2.0 bundles
(`scripts/repository-model-cli.js <tree> --name <name> --revision git:<sha>`)
of the same two external repositories at the same recorded revisions, then
`scripts/qualify_repository_model_assertions.py`:

| Specimen | Source revision | Producer / profile | Assertions in | Lost | Semantic claims out | Topology validation |
|---|---|---|---|---|---|---|
| `golden-repo` | `git:0b9f9202c80fc066e8c23dc1d783b99a2789160b` | 4.2.0 / 1.1.0 | 430 | 0 | 397 | passed |
| `l9-ops-mcp` | `git:70f8bbc3154cc3be277edf43c5c0048c4a2662c6` | 4.2.0 / 1.1.0 | 1312 | 0 | 1299 | passed |

The prior record was produced from 4.0.0 / profile 1.0.0 bundles. The 1.1.0
profile adds the `manifest/v1` extractor's `package.dependency` claims, which is
where most of the new assertions come from; none is lost through
reconciliation, and no dispatch was performed (`dispatches_performed: 0`,
`source_rescan_performed: false`).

## What this report does not claim

- `tests/fixtures/repository_model_packets/l9-assertion-sample` is still the
  4.0.0 / profile 1.0.0 packet. Its source tree is not in either repository, so
  it cannot be regenerated; it remains a valid `l9.repository-model` 1.1.0
  input and the compiler still accepts both profile versions.
- Publication containment, hash locality and effect identity are covered by
  the suite; they were not re-measured against the compiled packet above, which
  was not committed.
- `l9-pr-validate`'s `direct-compile-smoke` has not yet run against the
  re-pinned producer at the time of writing; its result is the CI evidence for
  this change, not this report.
- The downstream contract revision is carried forward, not re-captured.

## Standing assertions

- `compile.yml` keeps `v4` as its released default `meta_ref`; only the PR
  proof pins the exact commit, so a later move of `v4` is a deliberate re-pin
  here rather than a silent change under the proof.
- No producer source or generation output was mutated; the producer was read
  at a release tag and its CLIs were run over trees extracted by `git archive`.
- Candidate analysis was not promoted to canonical truth.
- No LLM reasoning was performed.
- Zero durable dispatches occurred.
- Merge is not authorized by this report.
