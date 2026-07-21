# Support

## Supported requests

Use GitHub issues for reproducible defects, contract inconsistencies, documentation
errors, and bounded enhancement proposals. Include:

- exact repository revision;
- command or workflow used;
- packet type and version;
- sanitized error output;
- expected and actual behavior;
- whether the problem is local, CI, OCI, callback, or control-plane related.

## Security reports

Follow `SECURITY.md`. Do not place credentials, signatures, private packet
contents, or exploit details in a public issue.

## Operational boundaries

This repository supports the topology compiler and its worker-side contracts. The
external Postgres control plane, organization-level GitHub App configuration,
production key custody, and downstream graph infrastructure have separate owners.
Support requests for those systems must be routed to their owning repositories.

## Service expectations

No response-time or availability commitment is created by this file. Production
support terms, if any, are governed by a separate written agreement.
