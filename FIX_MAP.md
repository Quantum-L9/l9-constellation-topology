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

## Executive-audit remediation map

| Priority | Confirmed finding | Owner | Applied fix | Regression evidence |
|---:|---|---|---|---|
| P0 | Validated package and committed tree diverged | Git workflows, `.l9`, manifest validation | Restore hidden surfaces; bind every tracked entry to path, mode, object type, and blob ID in `GIT_TREE_MANIFEST.json`; emit commit/tree-bound evidence | Git-integrity tests and CI gate |
| P1 | Reuse key omitted output-changing policies | compiler and worker | Complete semantic compilation fingerprint | policy and schema mutation tests |
| P1 | Dispatch selected callback URL and worker secret | callback transport and worker policy | callback ID plus local credentials, segment-bound path checks, encoded-separator rejection, expected host/port policy, redirect rejection, and DNS/IP controls | adversarial callback-policy tests |
| P1 | Publication verification accepted any valid bundle at a URI | packet store and worker | semantic-hash staging tag, digest-qualified reference, independent registry descriptor resolution, exact expected `PacketRef`, and manifest comparison | substitution and descriptor-mismatch tests |
| P1 | Input diagnostics disappeared | packet adapter, topology state, schemas, validator | typed diagnostics payload plus conservation invariant | diagnostic round-trip and removal-failure tests |
| P2 | Bundle visibility was only atomic per file | packet bundle sink | validate and fsync a staging directory, then atomically rename | injected staging-failure test |
| P2 | Local JSON registry lost concurrent updates | local registry | SQLite WAL transaction and uniqueness constraints | concurrent writer test |
| P2 | Schema receipts overstated independent verification | topology validator | separate model-construction and JSON Schema validation layers | invalid checked-in schema test |
