# Architecture — l9-constellation-topology

## Overview

This repo implements the L9 Constellation Topology Generator: a deterministic, evidence-backed scanner that maps all L9 repositories into a graphable topology suitable for Neo4j ingestion, Graphiti memory enrichment, and governance automation.

## Design Principles

1. **Evidence over inference** — every claim in the output carries an `EvidenceItem` with `source_file`, `source_type`, and `excerpt`. Claims without file-backed evidence are labeled `inference` or `UNKNOWN`.
2. **Read-only** — no source repo is mutated. No Neo4j SDK calls. No Graphiti write calls.
3. **Deterministic** — given the same input files, the output is bit-for-bit reproducible (via canonical JSON with sorted keys).
4. **Fail-closed** — missing paths, missing manifests, and missing evidence produce low-confidence outputs, not exceptions or invented data.

## Component Map

```
RepoSource (config/repo_sources.yaml)
    │
    ▼
RepoScanner (orchestrator)
    ├── ManifestScanner   → languages, package_managers, entrypoints
    ├── CIScanner         → ci_workflows
    ├── ADRScanner        → adr_files
    ├── DependencyScanner → upstream_dependencies
    ├── GovernanceScanner → governance_files, owner
    └── GraphitiScanner   → graphiti_memory_topology (read-only)
    │
    ▼
RepoCard (per-repo evidence container)
    │
    ▼
GraphBuilder → GraphRecord[] (nodes + edges) + EdgeCard[]
    │
    ├── ImpactEngine → blast_radius traversal
    ├── MaturityScorer → MaturityScore per repo
    └── RiskAssessor → RiskItem[] per repo
    │
    ▼
TopologyReport
    │
    ├── MarkdownRenderer  → topology_report.md
    ├── JSONExporter      → topology_report.json, graph_records.jsonl
    ├── CSVExporter       → maturity_scorecard.csv, repo_inventory.yaml
    ├── MermaidExporter   → architecture_diagrams.mmd
    └── Neo4jExporter     → neo4j_import.jsonl (candidate only, no SDK)
    │
    ▼
ValidationReport (schema + invariants) → 07_VALIDATION_REPORT.md
EvidenceHashes → evidence_hashes.json (SHA-256 per artifact)
```

## Boundary Enforcement

| Boundary | Enforcement |
|---|---|
| No Neo4j writes | Only JSONL file export; no neo4j SDK import |
| No Graphiti writes | GraphitiScanner reads only; no graphiti_client write calls |
| No repo mutation | All Path operations are read-only |
| No invented facts | All fields default to UNKNOWN; no inference without file evidence |
| No network in tests | All tests use local fixture; no HTTP in test suite |

## DAG

See [03_DEPENDENCY_DAG.md](03_DEPENDENCY_DAG.md) for the full module dependency DAG and topological sort.
