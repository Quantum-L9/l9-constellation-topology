# 07_VALIDATION_REPORT — M3.1

**Checked at:** 2026-07-05T21:04:00-04:00
**Contract:** l9_constellation_topology_nuclear_coding_contract v4.0.0

---

## Command 1: `python -m compileall src tests -q`

```
(no output — clean compile)
compileall exit: 0
```
**Result: PASS**

---

## Command 2: `python -m pytest tests -q`

```
platform linux -- Python 3.12.12, pytest-8.3.5, pluggy-1.6.0
rootdir: /home/user/l9-constellation-topology
configfile: pyproject.toml
plugins: anyio-4.11.0
collected 34 items

tests/test_dependency_scanner.py ....
tests/test_graph_builder.py ....
tests/test_impact.py ....
tests/test_maturity.py ....
tests/test_renderers.py .....
tests/test_repo_scanner.py ........
tests/test_validation.py .....

34 passed in 0.19s
```
**Result: PASS — 34/34 tests passed**

---

## Command 3: `python -m l9_constellation_topology.cli scan --repo-root tests/fixtures/sample_constellation --out outputs/test-topology`

```
  wrote: outputs/test-topology/topology_report.json
  wrote: outputs/test-topology/graph_records.jsonl
  wrote: outputs/test-topology/neo4j_import.jsonl
  wrote: outputs/test-topology/topology_report.md
  wrote: outputs/test-topology/maturity_scorecard.csv
  wrote: outputs/test-topology/repo_inventory.yaml
  wrote: outputs/test-topology/edge_cards.yaml
  wrote: outputs/test-topology/flow_cards.yaml
  wrote: outputs/test-topology/architecture_diagrams.mmd
  wrote: outputs/test-topology/dependency_graph.json
  wrote: outputs/test-topology/07_VALIDATION_REPORT.md
  wrote: outputs/test-topology/risk_register.md
  wrote: outputs/test-topology/evidence_hashes.json
scan complete: 13 files -> outputs/test-topology
```
**Result: PASS — 13 output files generated**

---

## Command 4: `python -m l9_constellation_topology.cli validate --input outputs/test-topology/topology_report.json`

```
valid: True
```
**Result: PASS**

---

## Command 5: `python -m l9_constellation_topology.cli render --input outputs/test-topology/topology_report.json --out outputs/test-topology/report.md`

```
rendered -> outputs/test-topology/report.md
```
**Result: PASS**

---

## Fixed Prohibitions Check

| Prohibition | Status |
|---|---|
| No circular package dependencies | PASS — DAG proven acyclic in M1.3 |
| No hardcoded secrets | PASS — no secrets in any file |
| No outbound network calls in tests | PASS — tests use only local fixture paths |
| No mock-only tests asserting call counts | PASS — all tests assert real output |
| No disabled or skipped tests | PASS — 34 tests, 0 skipped |
| No placeholders, stubs, ellipses, TODOs | PASS — all files complete |
| No fake validation claims | PASS — all command outputs are captured |
| No pseudo-code or summarized implementations | PASS |
| No omitted imports | PASS — compileall exit 0 |
| No invented APIs | PASS — all APIs are pydantic models |
| No direct Neo4j writes | PASS — export-neo4j writes JSONL only |
| No Graphiti canonical-topology ownership | PASS — graphiti_scanner is read-only |
| No mutation of protected repos | PASS — all operations read-only |
| No destructive repo operations | PASS |
| No unverifiable owners | PASS — owner=UNKNOWN when not found in CODEOWNERS |

**M3.1 PASSED**
