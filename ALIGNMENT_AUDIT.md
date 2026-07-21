# Alignment Audit

## Authority checked

- v5 `SPECIFICATION.md`
- packet-first compiler and read-only source boundaries
- OutputSink-only effect policy
- GitHub Actions exact-revision worker model
- existing public CLI, schemas, profiles, tests, and documentation

## Findings

| ID | Area | Finding | Resolution |
|---|---|---|---|
| ALN-001 | CI | The hardening contract was not a required pull-request gate | Added and contract-tested the release-readiness validator |
| ALN-002 | validation | Root release artifacts required by the operating contract were absent from the Git tree | Added evidence-backed artifacts and exact inventory |
| ALN-003 | scanner behavior | Invalid `package.json` could disappear without a diagnostic or failure | Made malformed input fail closed |
| ALN-004 | documentation | README and runbook omitted the no-stub and manifest-drift gate | Added runnable command and behavior description |
| ALN-005 | versioning | Hardening and enrichment needed an explicit release record without falsely changing packet contracts | Kept runtime and packet identities at `2.0.0`; documented all unreleased initial-commit changes in `CHANGELOG.md` |

## No-drift conclusion

No new architecture layer, external service, transport shape, graph client, or feature family was introduced. Public packet and CLI contracts remain intact.

## Initial repository enrichment alignment

The enriched root surface now covers architecture, full specification authority,
governance, maintainership, contribution conduct, support, roadmap, release,
development, threat, dependency, licensing, notice, and initial-commit operation.
Twenty accepted ADRs make the highest-risk design decisions explicit and testable.
No parallel runtime, packet shape, or ownership system was introduced.

## Executive-audit remediation alignment

| ID | Confirmed finding | Resolution |
|---|---|---|
| REM-001 | Public commit omitted `.github` and `.l9` while evidence claimed them | Restored complete hidden surfaces and added exact Git-tree/manifest validation |
| REM-002 | Reuse identity omitted output-affecting policies | Complete compilation fingerprint now covers all semantic profiles, schemas, adapters, inputs, and compiler build identity |
| REM-003 | Packet could select callback destination and worker secret | Dispatch carries only a callback ID; worker-local policy owns destination, credential, redirects, DNS, and address safety |
| REM-004 | Publication verification accepted any valid bundle at a URI | Digest-qualified references and exact expected packet/manifest verification |
| REM-005 | Input diagnostics were normalized and then discarded | Typed diagnostics payload and conservation invariant |
| REM-006 | Bundle publication and local registry lacked transaction scope | Atomic staged-directory publication and SQLite WAL registry |
| REM-007 | Validation receipts overstated independent schema validation | Separate runtime model, JSON Schema, invariant, evidence, and cross-packet layers |

The unsafe callback payload shape is intentionally rejected. This is a security correction, not an architecture expansion.
