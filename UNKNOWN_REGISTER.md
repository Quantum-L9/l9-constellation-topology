# Unknown Register

## Validation and deployment Unknowns

| ID | Unknown | Why unresolved | Required proof |
|---|---|---|---|
| U-001 | Canonical Python 3.12 results for this initial commit | Local environment provides Python 3.13 and cannot download 3.12 because outbound DNS is unavailable | GitHub Actions `l9-pr-validate` on the pushed initial commit |
| U-002 | Live GHCR/ORAS publication behavior | No registry credentials or live publication target were used locally | Staging push, pull, digest verification, and permission drill |
| U-003 | Live Postgres scheduling, callback reconciliation, and dead-letter operation | Control-plane services are external to this repository | Staging Model B execution plus forced callback-loss and retry-exhaustion recovery |
| U-004 | Real upstream and downstream packet compatibility | Only checked-in packet fixtures were available locally | Real `l9-meta-injector` Repository Model Packet through topology into `l9-topology-ingestion-bridge` |
| U-005 | Local Ruff and mypy results | Tools are not installed locally and cannot be downloaded because outbound DNS is unavailable | Python 3.12 GitHub Actions validation with the frozen development environment |

## Governance and platform Unknowns

- Exact GitHub organization team slugs for `CODEOWNERS` remain unconfirmed. No guessed or invalid ownership entry is included.
- Production signing-key custody, rotation, and revocation remain external security decisions.
- Final control-API hosting and the long-term repository ownership of Model B orchestration remain external platform decisions.
- Live graph promotion policy remains owned by `l9-topology-ingestion-bridge` and is intentionally absent here.
- Final public release eligibility remains owner-controlled. The repository includes an explicit proprietary source license and package metadata preventing accidental public publication.

No unsupported value was invented to close these Unknowns.
