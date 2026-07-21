# l9-constellation-topology

Production-ready L9 Constellation Topology Generator.

Scans all L9 repositories and generates a comprehensive, evidence-backed, graphable topology including:
- Repo inventory with roles, languages, and ownership
- Dependency graph and edge cards
- Risk register and maturity scorecard
- Machine-readable graph records (Neo4j candidate export)
- Human-readable topology report

## Install

```bash
pip install -e .
# or
uv pip install -e .
```

## Usage

```bash
# Scan a single repo
l9-topology scan --repo-root /path/to/repo --out outputs/

# Scan many repos from config
l9-topology scan-many --sources config/repo_sources.yaml --out outputs/

# Validate a topology report
l9-topology validate --input outputs/topology_report.json

# Render to Markdown
l9-topology render --input outputs/topology_report.json --out outputs/report.md

# Compute blast radius
l9-topology impact --input outputs/graph_records.jsonl --entity repo:my-repo

# Export Neo4j candidate JSONL
l9-topology export-neo4j --input outputs/topology_report.json --out outputs/neo4j_import.jsonl
```

## Architecture

See [architecture.md](architecture.md) and [03_DEPENDENCY_DAG.md](03_DEPENDENCY_DAG.md).

## Boundaries

- No direct writes to Neo4j or Graphiti
- All operations are read-only on source repos
- All claims carry evidence or are labeled UNKNOWN
