# Acceptance Matrix

Status values: `PASS_LOCAL`, `CONTRACT_IMPLEMENTED`, `BLOCKED_EXTERNAL`, `NOT_RUN`, `FAIL`.

| # | Criterion | Evidence | Status |
|---:|---|---|---|
| 1 | Consume validated Repository Model Packets | loader, adapter, ingress tests | PASS_LOCAL |
| 2 | Two repositories produce two repository nodes | compiler fixture integration | PASS_LOCAL |
| 3 | Preserve artifact and capability relationships | graph and capability tests | PASS_LOCAL |
| 4 | Emit one validated Topology Packet | compiler and bundle round-trip tests | PASS_LOCAL |
| 5 | Bridge can consume packet without neighboring reports | packet contract and canonical bundle | CONTRACT_IMPLEMENTED |
| 6 | Reports regenerate from packet | lazy renderer tests | PASS_LOCAL |
| 7 | Impact, risk, and maturity remain available | assessment tests | PASS_LOCAL |
| 8 | Identical semantic inputs produce identical semantic hash | determinism script | PASS_LOCAL |
| 9 | Machine-local paths do not affect semantic identity | evidence and normalization tests | PASS_LOCAL |
| 10 | Timestamps do not affect semantic identity | compiler determinism test | PASS_LOCAL |
| 11 | Graph entity and edge IDs are stable | graph tests | PASS_LOCAL |
| 12 | Every canonical claim references evidence | fail-closed evidence validation | PASS_LOCAL |
| 13 | Inference is explicitly labeled | evidence taxonomy tests | PASS_LOCAL |
| 14 | Unknowns are explicit | aggregation tests | PASS_LOCAL |
| 15 | Conflicts are preserved | reconciliation and validation tests | PASS_LOCAL |
| 16 | Evidence references resolve | invariant validation | PASS_LOCAL |
| 17 | No production module outside `io/` mutates files | architecture boundary check | PASS_LOCAL |
| 18 | Invalid topology commits zero canonical outputs | failed-validation sink test | PASS_LOCAL |
| 19 | Dry-run performs no prohibited writes | OutputSink tests | PASS_LOCAL |
| 20 | Unchanged outputs are skipped | OutputSink tests | PASS_LOCAL |
| 21 | Every committed artifact appears in a receipt | bundle and sink tests | PASS_LOCAL |
| 22 | Postgres activates topology from validated parent packet | external Model B control plane | BLOCKED_EXTERNAL |
| 23 | GitHub Actions executes the signed exact revision | preflight, revision, and worker tests | PASS_LOCAL |
| 24 | Stage success requires publication and validation | worker vertical-slice test | PASS_LOCAL |
| 25 | Repeated identical input reuses prior packet | local registry and reuse callback test | PASS_LOCAL |
| 26 | Transient failures retry | callback and packet-store retry contracts | CONTRACT_IMPLEMENTED |
| 27 | Non-retryable validation failures block | worker failure tests | PASS_LOCAL |
| 28 | Reconciliation repairs dropped callback | external Postgres reconciler | BLOCKED_EXTERNAL |
| 29 | Dead-lettered work is queryable | external Postgres dead-letter store | BLOCKED_EXTERNAL |
| 30 | Manual replay preserves lineage | signed replay workflow and contract | CONTRACT_IMPLEMENTED |
| 31 | No human PAT is used | workflow and security inspection | PASS_LOCAL |
| 32 | No database credentials are stored here | secret and source inspection | PASS_LOCAL |
| 33 | No GitHub App private key is stored here | secret and source inspection | PASS_LOCAL |
| 34 | Cross-repository packets are signed | signature and tamper tests | PASS_LOCAL |
| 35 | Packet attachment and bundle hashes are verified | packet-store and loader tests | PASS_LOCAL |
| 36 | Source repositories remain read-only | scanner boundary and architecture tests | PASS_LOCAL |
| 37 | Legacy scan commands remain or have replacements | CLI compatibility tests | PASS_LOCAL |
| 38 | Valid legacy analytical behavior is preserved | donor regression tests | PASS_LOCAL |
| 39 | Graph, risk, maturity, impact, and reports remain supported | regression and v5 tests | PASS_LOCAL |
| 40 | Migration from v4 to v5 is documented | `docs/migration-v4-to-v5.md` | PASS_LOCAL |
| 41 | Callback policy enforces exact host, port, and path-segment boundaries | adversarial callback tests | PASS_LOCAL |
| 42 | Release evidence binds tracked modes and blob IDs to the exact commit | `GIT_TREE_MANIFEST.json` and Git-integrity tests | PASS_LOCAL |
| 43 | OCI publication uses unique staging and independent descriptor verification | packet-store tests | PASS_LOCAL |

## Release interpretation

The repository is locally execution-ready and contract-complete for the compiler and worker boundary. Full production deployment remains blocked on external control-plane, GHCR, callback reconciliation, dead-letter, and cross-repository integration drills.
