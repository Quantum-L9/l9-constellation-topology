# Migration from v4 to v5

## Preserved engine parts

- Manifest, CI, ADR, dependency, and governance observation logic
- Repository role heuristics, moved into profiles
- Dependency graph construction, generalized to canonical edges
- Reverse-dependency impact traversal
- Maturity and risk logic, moved into versioned profiles
- Canonical JSON and SHA-256 utilities, corrected for semantic identity
- Markdown, JSON, CSV, YAML, Mermaid, and graph export formatting, converted to pure renderers
- Existing tests and fixtures as regression evidence

## Replaced architecture

```text
v4: RepoSource → RepoCard → TopologyReport → neighboring report files
v5: Repository Model Packet(s) → canonical records → Topology Packet + Validation Receipt
```

Retired behavior:

- Directory-coupled downstream handoffs
- Scattered direct writes
- Timestamp- and absolute-path-contaminated semantic identity
- Coarse `low/medium/high` trust as the sole evidence model
- Validation that mutates or writes its subject
- Direct Neo4j candidate files as canonical outputs

## Compatibility

`scan` and `scan-many` remain bounded compatibility ingress paths. They create validated synthetic Repository Model Packet bundles in a temporary workspace and invoke the v5 compiler. They emit a Topology Packet bundle, not a v4 report directory.

Old contracts, outputs, and validation claims remain under `docs/archive/v4/` and `tests/fixtures/legacy_v4_outputs/` for migration evidence only.
