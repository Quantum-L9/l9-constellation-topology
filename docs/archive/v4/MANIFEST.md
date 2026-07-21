# MANIFEST — l9-constellation-topology v1.0.0

## Package Identity
- **repo:** l9-constellation-topology
- **version:** 1.0.0
- **contract:** l9_constellation_topology_nuclear_coding_contract v4.0.0
- **owner:** igor_beylin
- **status:** production-candidate

## File Inventory

### Root
- README.md — project overview and usage
- MANIFEST.md — this file
- pyproject.toml — build, deps, CLI entry point
- 01_SPEC_ATTACK.md — M1.1 evidence
- 02_IMPLEMENTATION_CONTRACT.md — M1.2 evidence
- 03_DEPENDENCY_DAG.md — M1.3 evidence

### schemas/
- repo_card.schema.json
- edge_card.schema.json
- flow_card.schema.json
- topology_report.schema.json
- risk_register.schema.json
- graph_record.schema.json

### config/
- repo_sources.yaml — operator-populated repo registry
- scanner_rules.yaml — scanner configuration
- topology_roles.yaml — role taxonomy
- report_profiles.yaml — report configuration

### src/l9_constellation_topology/
- __init__.py, cli.py, models.py, evidence.py
- scanners: repo_scanner, manifest_scanner, ci_scanner, adr_scanner, dependency_scanner, governance_scanner, graphiti_scanner
- topology: classifier, graph_builder, impact, maturity, risk
- renderers: markdown_report, json_export, csv_export, mermaid_export
- validation: schema_validator, invariant_validator, validation_report

### tests/
- fixtures/sample_constellation — two sample repos for test coverage
- test_repo_scanner, test_dependency_scanner, test_graph_builder, test_impact, test_maturity, test_renderers, test_validation

### outputs/
- .gitkeep — directory placeholder
