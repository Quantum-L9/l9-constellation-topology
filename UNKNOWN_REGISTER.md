# Unknown Register

## Validation and deployment Unknowns

| ID | Unknown | Why unresolved | Required proof |
|---|---|---|---|
| U-001 | Canonical Python 3.12 results for the remediation commit | Local environment provides Python 3.13 and cannot download 3.12 because outbound DNS is unavailable | GitHub Actions `l9-pr-validate` on the exact remediation commit |
| U-002 | Live GHCR/ORAS publication behavior | No registry credentials or live publication target were used locally | Staging push, pull, digest verification, and permission drill |
| U-003 | Live Postgres scheduling, callback reconciliation, and dead-letter operation | Control-plane services are external to this repository | Staging Model B execution plus forced callback-loss and retry-exhaustion recovery |
| U-004 | Live downstream dispatch and durable admission | Upstream compatibility and downstream contract conformance are now proven: a real `l9-meta-injector` Repository Model Packet compiles through this repository, and every eligible lowered intent validates against the bound `l9-graphiti-memory` typed boundary. Dispatch itself is out of scope here and was never performed | Gate dispatch and durable admission executed by `l9-graphiti-memory` against a live memory service |
| U-005 | Local Ruff and mypy results | Tools are not installed locally and cannot be downloaded because outbound DNS is unavailable | Python 3.12 GitHub Actions validation with the frozen development environment |
| U-006 | Approved production callback hostname | The control-plane DNS name is external and was not supplied | Commit the approved hostname and port into `.l9/callback-policy.yaml`, enable the production callback ID, and run the live callback drill |

## Governance and platform Unknowns

- Exact GitHub organization team slugs for `CODEOWNERS` remain unconfirmed. No guessed or invalid ownership entry is included.
- Production signing-key custody, rotation, and revocation remain external security decisions.
- Final control-API hosting and the long-term repository ownership of Model B orchestration remain external platform decisions.
- Publication planning lives here per ADR-0021, but live graph promotion, Gate dispatch, and durable admission remain owned by `l9-graphiti-memory` and are intentionally absent.
- Final public release eligibility remains owner-controlled. The repository includes an explicit proprietary source license and package metadata preventing accidental public publication.

## Corpus intelligence Unknowns

- `l9-meta-injector` does not yet emit `l9.corpus-intelligence`. The canonical
  packet contract is implemented and tested here; production use currently goes
  through the `adapt-meta-corpus` compatibility ingress.
- The current producer generation records work signals only as line spans into the
  text it interpreted. For Word, PDF, PowerPoint, and spreadsheet documents that
  text is the decoded blocks joined by newlines, so the recorded line is not a
  coordinate in the source document. Those signals are declined by the adapter and
  reported by count and reason. No structured locator is derived for them: the
  line-to-block mapping holds only if no decoded block text contains a newline,
  which the generation gives no way to check.
- Whether a corpus root that observed no repository should carry a synthetic
  repository identity is deliberately unresolved. `RootRecord.repository_id` is
  optional, and the root-to-repository containment edge is emitted only when a
  repository was actually observed.

No unsupported value was invented to close these Unknowns.

## Remediation release gates

- The prior `APPROVED_INITIAL_COMMIT_WITH_EXTERNAL_UNKNOWNS` conclusion is superseded because its evidence was not bound to the committed tree.
- Production remains blocked until the exact remediation commit passes GitHub Actions on Python 3.12 and completes a real digest-qualified OCI, Postgres registry, callback-loss, duplicate-delivery, and three-repository staging drill.
- The checked-in production callback entry is intentionally disabled and has an empty host allowlist. It must remain fail-closed until the approved control-plane hostname is committed and independently reviewed.
