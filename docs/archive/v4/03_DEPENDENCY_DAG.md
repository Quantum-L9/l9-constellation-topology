# M1.3 — Dependency DAG

**dependency_dag_valid: true**

---

## Module Arrow List (A → B means A imports from B)

```
cli.py                  → models.py
cli.py                  → scanners/repo_scanner.py
cli.py                  → topology/graph_builder.py
cli.py                  → topology/impact.py
cli.py                  → renderers/markdown_report.py
cli.py                  → renderers/json_export.py
cli.py                  → renderers/csv_export.py
cli.py                  → renderers/mermaid_export.py
cli.py                  → validation/schema_validator.py
cli.py                  → validation/validation_report.py
cli.py                  → evidence.py
scanners/repo_scanner.py       → models.py
scanners/repo_scanner.py       → evidence.py
scanners/repo_scanner.py       → scanners/manifest_scanner.py
scanners/repo_scanner.py       → scanners/ci_scanner.py
scanners/repo_scanner.py       → scanners/adr_scanner.py
scanners/repo_scanner.py       → scanners/dependency_scanner.py
scanners/repo_scanner.py       → scanners/governance_scanner.py
scanners/repo_scanner.py       → scanners/graphiti_scanner.py
scanners/manifest_scanner.py   → models.py
scanners/manifest_scanner.py   → evidence.py
scanners/ci_scanner.py         → models.py
scanners/ci_scanner.py         → evidence.py
scanners/adr_scanner.py        → models.py
scanners/adr_scanner.py        → evidence.py
scanners/dependency_scanner.py → models.py
scanners/dependency_scanner.py → evidence.py
scanners/governance_scanner.py → models.py
scanners/governance_scanner.py → evidence.py
scanners/graphiti_scanner.py   → models.py
scanners/graphiti_scanner.py   → evidence.py
topology/graph_builder.py      → models.py
topology/graph_builder.py      → evidence.py
topology/classifier.py         → models.py
topology/impact.py             → models.py
topology/maturity.py           → models.py
topology/risk.py               → models.py
renderers/markdown_report.py   → models.py
renderers/json_export.py       → models.py
renderers/json_export.py       → evidence.py
renderers/csv_export.py        → models.py
renderers/mermaid_export.py    → models.py
validation/schema_validator.py → models.py
validation/invariant_validator.py → models.py
validation/validation_report.py   → models.py
validation/validation_report.py   → validation/schema_validator.py
validation/validation_report.py   → validation/invariant_validator.py
```

## Adjacency List

```
models.py:                (no internal deps — stdlib + pydantic only)
evidence.py:              (no internal deps — stdlib only)
topology/classifier.py:   [models]
topology/maturity.py:     [models]
topology/risk.py:         [models]
scanners/manifest_scanner.py:   [models, evidence]
scanners/ci_scanner.py:         [models, evidence]
scanners/adr_scanner.py:        [models, evidence]
scanners/dependency_scanner.py: [models, evidence]
scanners/governance_scanner.py: [models, evidence]
scanners/graphiti_scanner.py:   [models, evidence]
scanners/repo_scanner.py:       [models, evidence, manifest_scanner, ci_scanner,
                                 adr_scanner, dependency_scanner, governance_scanner,
                                 graphiti_scanner]
topology/graph_builder.py:      [models, evidence]
topology/impact.py:             [models]
renderers/markdown_report.py:   [models]
renderers/json_export.py:       [models, evidence]
renderers/csv_export.py:        [models]
renderers/mermaid_export.py:    [models]
validation/schema_validator.py: [models]
validation/invariant_validator.py: [models]
validation/validation_report.py:   [models, schema_validator, invariant_validator]
cli.py:                         [models, evidence, repo_scanner, graph_builder,
                                 impact, markdown_report, json_export, csv_export,
                                 mermaid_export, schema_validator, validation_report]
```

## Topological Sort (build order — leaf first)

```
Layer 0 (no deps):
  1. models.py
  2. evidence.py

Layer 1 (depend only on Layer 0):
  3. topology/classifier.py
  4. topology/maturity.py
  5. topology/risk.py
  6. scanners/manifest_scanner.py
  7. scanners/ci_scanner.py
  8. scanners/adr_scanner.py
  9. scanners/dependency_scanner.py
  10. scanners/governance_scanner.py
  11. scanners/graphiti_scanner.py
  12. topology/graph_builder.py
  13. topology/impact.py
  14. renderers/markdown_report.py
  15. renderers/json_export.py
  16. renderers/csv_export.py
  17. renderers/mermaid_export.py
  18. validation/schema_validator.py
  19. validation/invariant_validator.py

Layer 2:
  20. scanners/repo_scanner.py
  21. validation/validation_report.py

Layer 3 (entry point):
  22. cli.py
```

## Cycle Check

Kahn's algorithm run on 22 nodes:
- No node appears in both its own ancestor and descendant sets.
- All 22 nodes were processed; queue never became empty before all nodes were consumed.
- **No cycles detected.**

**dependency_dag_valid: true**
**M1.3 PASSED**
