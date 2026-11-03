# Current validation report

Evidence for the producer/consumer boundary, bound to the exact revisions it
was produced against. Regenerate rather than amend: a report that outlives the
heads it names is a report about nothing.

This report supersedes the one written against producer `953b7cb` (v4.2.0).
It re-binds the boundary to the v4.3.0 release; `QUALIFICATION.json` is carried
forward unchanged (see below).

## Bound revisions

| Role | Repository | Revision |
|---|---|---|
| Consumer (this change) | `Quantum-L9/l9-constellation-topology` branch `agent/claude-code/topology-align-meta-v4.3.0` | the commit carrying this report |
| Base | `Quantum-L9/l9-constellation-topology` `main` | `abac518a6e74c7ad3373053b70e1e98efb5d0b26` |
| Producer | `Quantum-L9/l9-meta-injector` release `v4.3.0` (maintained `v4` line) | `c53ef3aa0ccea04af2adfe67800ad09843b6e0fe` |
| Downstream contract | `Quantum-L9/l9-graphiti-memory` | `f690d3f928391264cbffb8f507ad9acbba339603` (carried forward; not re-verified in this run) |

Environment: Python 3.12.13, uv 0.11.32, Node 22.23.4, Linux-6.18.44-x86_64-with-glibc2.39.

What this change binds: `.github/workflows/l9-pr-validate.yml` pins the PR
compile proof's `meta_ref` to the producer revision above (it was `953b7cb`,
v4.2.0), and the producer-emitted corpus fixture is regenerated at that
revision. The producer's release workflow created `v4.3.0` and advanced `v4`
to `c53ef3a` on 2026-11-03 (GitHub Release run `41717212599`).

## Suite results

| Check | Result |
|---|---|
| `uv run pytest` | 691 collected: 689 passed, 2 skipped, 0 failed. Skips: `test_fixture_provenance.py:54` (covered by the preceding test) and `test_publication_downstream_conformance.py:228` (needs `L9_GRAPHITI_MEMORY_SRC`) |
| coverage | 86.46% (required 80%) |
| `uv run ruff check .` / `ruff format --check .` | clean |
| `uv run mypy src/l9_constellation_topology` | no issues, 154 source files |
| `scripts/validate_workflows.py` | passed (the re-pinned `meta_ref` is a 40-hex revision) |
| `scripts/validate_contracts.py` | passed |
| `scripts/architecture_boundary_check.py` | passed |
| `scripts/validate_release_readiness.py` | passed |
| `make generated-check` | passed (schemas, fixtures, hash locality) with no update target run |
| `scripts/validate_git_integrity.py` | evaluated on the commit carrying this report, after `GIT_TREE_MANIFEST.json` is regenerated from the staged tree |
| `tests/test_producer_emitted_corpus_packet.py`, `tests/test_corpus_ingress.py` | 18 passed against the regenerated fixture |

## Real producer/consumer qualification

Not synthesized. The producer bundles below were emitted by the v4.3.0
producer at `c53ef3a` and read here through the same loader a real compile uses.

### End-to-end compile

`l9-topology compile-packet` over all five root bundles with the corpus bundle
(`--corpus-bundle`) under this repository's own topology profile:

```
status:             passed
validation_status:  passed
packet_id:          packet:cb5958a8f9b76e9315c26f17d0295eb21d54d9b4249f96278fa72bbc11e94771
corpus_intelligence_packets: [packet:52c365061ae6e0a5f0dfd2746d50f53e64f1d7c3e58342849c8beea8e08c24e5]
outputs:            23 written (atomic bundle commit), validation receipt included
```

Every root's repository record still claims `validated-machine` authority with
non-empty `evidence_refs` (corpus 2, Documents 1, OldSSD 2, ArchiveZips 1,
Backup 2), so `evidence-canonical-claims-backed` holds at v4.3.0.

### Producer-emitted corpus fixture

`tests/fixtures/corpus_intelligence/producer-emitted` was regenerated with
`npx tsx tests/helpers/emit_corpus_intelligence_fixture.ts` at `c53ef3a`
(producer `l9-meta-injector.corpus-intelligence` 4.3.0 over
`l9.repository-model` 1.1.0 roots, profile
`meta-injector-repository-interpretation` 1.2.0). Same file set; every packet,
manifest and receipt changed bytes. Against the prior emit the
`python-route-observation/v1` extractor moved 1.1.0 → 1.2.0, which moves the
profile hash and every derived id; each payload domain keeps its record count.
Two emits at the same revision differ only in wall-clock `created_at`. Its
`PROVENANCE.md` records the revision, the packet id and the comparison.

### Assertion activation qualification

Not regenerated in this change. `QUALIFICATION.json` is carried forward from
the v4.2.0 report: it was produced from v4.2.0 / profile 1.1.0 bundles of
`golden-repo` and `l9-ops-mcp`, and both repositories are outside this
change's scope by operator instruction (2026-11-03). Its numbers therefore
describe the v4.2.0 producer, not v4.3.0.

| Specimen | Source revision | Producer / profile | Assertions in | Lost | Semantic claims out | Topology validation |
|---|---|---|---|---|---|---|
| `golden-repo` | `git:0b9f9202c80fc066e8c23dc1d783b99a2789160b` | 4.2.0 / 1.1.0 | 430 | 0 | 397 | passed |
| `l9-ops-mcp` | `git:70f8bbc3154cc3be277edf43c5c0048c4a2662c6` | 4.2.0 / 1.1.0 | 1312 | 0 | 1299 | passed |

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
- Assertion activation at v4.3.0 is not measured; `QUALIFICATION.json` is the
  v4.2.0 record.
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
