# Fix Map

| Priority | Defect | Owner | Fix | Validation |
|---:|---|---|---|---|
| 1 | Release validation could claim no stubs without AST proof | `scripts/validate_release_readiness.py` | Add executable repository-wide gate | Unit test plus direct script execution |
| 2 | Malformed `package.json` was silently ignored | `scanners/dependency_scanner.py` | Raise explicit validation error | Two negative tests |
| 3 | CI did not enforce hardening artifacts or manifest alignment | PR workflow and workflow validator | Add required gate and anti-removal check | Workflow contract validation |
| 4 | Protocols and exception class looked incomplete to mechanical audits | `io/output_sink.py`, `sources/reader.py`, `packets/loader.py` | Replace placeholder-shaped bodies with explicit contracts | AST gate and full tests |
| 5 | Release handoff lacked required traceability documents | repository root and `validation/` | Add complete evidence-backed artifact set | Manifest validation and manual review |

## Initial repository enrichment fixes

| Finding | Fix | Validation |
|---|---|---|
| Full source-aligned build authority was not preserved as one complete artifact | Added `BUILD_SPECIFICATION.md` | governance test and source-lineage assertions |
| Architecture decisions were implicit across code and docs | Added `ADR_INDEX.md` and 20 accepted ADRs | ADR count, status, section, and index tests |
| Root governance and initial-push posture were incomplete | Added aligned root policy, operator, legal, and handoff files | release-readiness required-file gate |
| Collaboration intake did not encode architecture checks | Added PR and issue templates | YAML parsing and manifest validation |
