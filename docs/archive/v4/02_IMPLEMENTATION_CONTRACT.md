# M1.2 — Implementation Contract (Sealed)

**Sealed:** 2026-07-05T21:04:00-04:00
**Source of Truth Version:** 4.0.0

---

## Resolved Architecture

### Package Layout
- `src/` layout with `l9_constellation_topology` as the importable package
- `pyproject.toml` uses `[tool.setuptools.packages.find] where = ["src"]`
- CLI entry point: `l9-topology` → `l9_constellation_topology.cli:main`
- All internal imports are absolute: `from l9_constellation_topology.models import ...`

### Data Flow
```
repo_sources.yaml
    └─► RepoSource (models.py)
            └─► RepoScanner → RepoCard (models.py) + EvidenceItems
            └─► ManifestScanner → populates languages, package_managers, entrypoints
            └─► CIScanner → populates ci_workflows
            └─► ADRScanner → populates adr_files
            └─► DependencyScanner → populates upstream_dependencies, downstream_dependents
            └─► GovernanceScanner → populates governance_files, owner
            └─► GraphitiScanner → populates graphiti_memory_topology entries
                        │
                        ▼
                GraphBuilder (topology/graph_builder.py)
                → NodeRecord + EdgeRecord (GraphRecord)
                        │
                        ▼
            ┌───────────┴───────────┐
            │                       │
        ImpactEngine            TopologyReport
      (topology/impact.py)    (renderers/*)
            │                       │
        blast_radius        markdown_report.py
        edge traversal      json_export.py
                            csv_export.py
                            mermaid_export.py
                                    │
                            ValidationReport
                          (validation/schema_validator.py)
                          (validation/invariant_validator.py)
```

### Models (sealed)

**RepoCard** — exactly as contract: repo_id, name, path, primary_role, secondary_roles[], languages[], package_managers[], entrypoints[], ci_workflows[], adr_files[], governance_files[], upstream_dependencies[], downstream_dependents[], evidence[], confidence

**EdgeCard** — source, target, edge_type (7 types), direction (3 types), evidence[], confidence

**GraphRecord** — record_type (node|edge), label, id, properties{}, evidence[], source_file, confidence

**TopologyReport** — constellation_name, generated_at, repo_inventory[], dependency_graph[], intelligence_flows[], governance_topology[], runtime_topology[], graphiti_memory_topology[], neo4j_topology_boundary[], risk_register[], maturity_scorecard[], unknowns[]

**EvidenceItem** — source_file, source_type (file|inference|unknown), excerpt, line_number|None

### Scanner Contracts (sealed)

Each scanner accepts `(repo_path: Path, repo_id: str) -> list[EvidenceItem]` and returns evidence only. Scanners never write files. The `RepoScanner` orchestrates all sub-scanners and assembles the final `RepoCard`.

### CLI Commands (sealed)

| Command | Input | Output |
|---|---|---|
| `scan` | `--repo-root PATH --out DIR` | topology_report.json, graph_records.jsonl, all outputs |
| `scan-many` | `--sources YAML --out DIR` | same, multi-repo |
| `validate` | `--input topology_report.json` | validation_report.json + exit code |
| `render` | `--input topology_report.json --out FILE` | report.md |
| `impact` | `--input graph_records.json --entity ID` | blast radius JSON |
| `export-neo4j` | `--input graph_records.json --out FILE` | neo4j_import.jsonl |

### Evidence Hashing

`evidence.py` implements:
- `canonical_json(obj)` → deterministic JSON (sorted keys, no floats ambiguity)
- `sha256_hash(s: str) -> str` → hex digest
- `deep_freeze(obj)` → immutable nested structure (tuple/frozenset)
- `hash_artifact(path: Path) -> dict` → {path, sha256, size_bytes, frozen_at}

### Maturity Scoring (sealed)

Score per repo 0–100:
- has_pyproject_or_package_json: +15
- has_ci_workflow: +20
- has_adr: +15
- has_governance: +15
- has_readme: +10
- dependency_count > 0: +10
- confidence == high: +15
Bands: 0–39 = nascent, 40–69 = emerging, 70–89 = mature, 90–100 = exemplary

### Risk Rules (sealed)

Emitted as RiskItem(risk_id, repo_id, severity, category, description, evidence[]):
- No CI: severity=high, category=ci_gap
- No governance file: severity=medium, category=governance_gap
- No ADR: severity=low, category=adr_gap
- Confidence low: severity=medium, category=evidence_quality
- Zero dependencies and non-trivial role: severity=low, category=isolation

### Boundaries Enforced

- No network calls anywhere in src/ or tests/
- No Neo4j SDK calls — only JSONL file export
- No Graphiti write calls — scanner reads local files only
- No repo mutation — all operations are read-only on source paths
- No invented facts — all claims carry EvidenceItem or UNKNOWN label

**M1.2 PASSED — sealed implementation contract is the single source of truth**
