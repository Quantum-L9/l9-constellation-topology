# M1.1 — Adversarial Spec Attack

**Contract:** l9_constellation_topology_nuclear_coding_contract v4.0.0
**Status:** RESOLVED — all blockers resolved or labeled UNKNOWN

---

## Attack Surface 1: Repo Input Ambiguity

**Issue:** `local_path` in repo_sources may point to nonexistent paths at build time.
**Resolution:** Scanner checks path existence; emits `confidence: low` and `evidence: ["path_missing"]` rather than halting. Labels as UNKNOWN in report.

**Issue:** `remote_url` and `group_id` are `string | Unknown` — scanner must not infer these.
**Resolution:** Fields left as null when not present in source config. Never inferred. Labeled UNKNOWN in output.

## Attack Surface 2: Topology Scope

**Issue:** "all L9 repositories" is not enumerable from inside the build — we have no registry of canonical L9 repos at build time.
**Resolution:** UNKNOWN — scanner operates on `config/repo_sources.yaml` which the operator populates. Fixture provides 2 sample repos for test coverage. The tool does not assume it has seen all repos.

**Issue:** "ownership matrix" requires an authoritative owner mapping that does not exist in a fresh repo.
**Resolution:** Ownership is derived from `CODEOWNERS`, `MANIFEST.md`, and `governance_files` found in each repo. If absent, owner = UNKNOWN. No owners are invented.

## Attack Surface 3: Graph Ownership / Graphiti / Neo4j Boundaries

**Issue:** Contract says "no Graphiti canonical-topology ownership" and "no direct writes to Neo4j topology." Must not conflate export with write.
**Resolution:** `export-neo4j` CLI command produces a `.jsonl` candidate file for human-reviewed import. No SDK calls to Neo4j or Graphiti are made. Graphiti scanner reads only (no write). Both boundaries are enforced by the Fixed Prohibitions.

**Issue:** Graphiti episode ID availability is unknown.
**Resolution:** Labeled UNKNOWN. Scanner emits `graphiti_memory_topology` section with `episode_id: UNKNOWN` when not discoverable.

## Attack Surface 4: Validation Limits

**Issue:** `python -m l9_constellation_topology.cli` requires the package to be importable.
**Resolution:** `pyproject.toml` defines `[project.scripts] l9-topology = "l9_constellation_topology.cli:main"` and `src` layout with proper `__init__.py`. Tests install the package via `pip install -e .` in fixture.

**Issue:** `python -m pytest tests -q` must pass with no network calls.
**Resolution:** All scanner tests use only the local `tests/fixtures/sample_constellation` directory. No HTTP, no subprocess calls to external systems.

**Issue:** `compileall` must compile both `src` and `tests` cleanly.
**Resolution:** No f-string syntax issues, no Python <3.11 incompatibilities. All imports are explicit.

## Attack Surface 5: Evidence vs. Inference

**Issue:** Contract requires distinguishing evidence from inference.
**Resolution:** `EvidenceItem` model carries `source_type: Literal["file","inference","unknown"]`. Scanners only emit `source_type: "file"` for filesystem-backed findings. Inferred fields are labeled `source_type: "inference"` with `confidence: low`.

## Remaining UNKNOWNs (explicit)

| UNKNOWN | Impact | Mitigation |
|---|---|---|
| Actual local paths of all L9 repos | High | Operator fills `config/repo_sources.yaml` |
| Final Neo4j AuraDB schema | Medium | Export uses graph_record schema; operator maps |
| Graphiti episode ID format | Low | Emitted as UNKNOWN string |
| Completeness of L9 repo registry | High | Tool scans what it is given; reports coverage gaps |

**M1.1 PASSED — all blockers resolved or labeled UNKNOWN**
