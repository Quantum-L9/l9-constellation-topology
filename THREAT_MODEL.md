# Threat Model

## Protected assets

- source-repository declarations and revisions;
- Repository Model Packets and parent Validation Receipts;
- Topology Packets, payloads, manifests, and receipts;
- compiler and profile versions used in semantic identity;
- dispatch, result, replay, and callback control packets;
- packet-store credentials, callback tokens, and signing keys;
- workflow and packet registry state.

## Trust boundaries

1. Source repository to `l9-meta-injector`.
2. Repository Model Packet store to topology worker.
3. Control plane to GitHub Actions dispatch.
4. Trusted `main` preflight to requested exact revision.
5. Compiler domain to OutputSink.
6. Local bundle to immutable OCI packet store.
7. Worker callback to the external Postgres control plane.
8. Topology Packet to the internal publication planner.
9. Publication plan to `l9-graphiti-memory`. This repository plans intents and
   never dispatches them, so no durable memory or graph write crosses this edge
   under its own authority.

## Primary threats and controls

| Threat | Control |
|---|---|
| Tampered dispatch selects attacker code | Verify signature with trusted `main` before exact-revision checkout |
| Mutable branch changes execution | Require an exact Git object ID |
| Parent packet substitution | Verify packet ID, semantic hash, bundle hash, source revision, and passed receipt |
| OCI tag substitution or publisher race | Publish through a semantic-hash-derived staging tag, accept only the returned digest-qualified reference, independently resolve the registry descriptor, and bind re-fetch verification to the expected PacketRef plus manifest digest |
| Local-path identity drift | Normalize source paths and exclude machine-local paths from semantic hashes |
| False canonical claims | Require evidence references, decomposed confidence, and fail-closed validation |
| Direct source mutation | Read-only source providers and architecture boundary checks |
| Output path escape, partial bundle visibility, or overwrite | OutputSink containment, collision policy, immutable bundles, validated staging directories, fsync, and atomic directory replacement |
| Duplicate or stale publication after retry | Complete compilation fingerprint, exact packet verification, reuse receipt, and reconciliation |
| Callback secret exfiltration or destination substitution | Dispatch selects only a callback ID; worker-local policy owns URL and credentials, requires expected host and port, applies segment-bound path matching, rejects encoded separators and redirects, and blocks unsafe resolved addresses |
| Unauthorized graph mutation | No Neo4j or Graphiti write client in this repository |
| Malicious report treated as truth | Reports are projections and cannot serve as stage inputs |
| Dependency or action supply-chain drift | Frozen `uv.lock`, exact action SHAs, clean build, and isolated install smoke |

## Assumptions

- GitHub-hosted runner and GitHub Actions platform integrity are external dependencies.
- Production signing keys and callback credentials are stored outside the repository.
- The external control plane atomically registers packets and commits stage state.
- OCI package permissions prevent unauthorized disclosure; packet identity does not rely on permissions because production references are digest-qualified.

## Residual risks

- Foundational HMAC signing uses shared-secret custody until an approved asymmetric
  profile replaces it.
- Live Postgres reconciliation and dead-letter behavior require external staging proof.
- Source repositories may contain sensitive metadata that propagates into topology
  artifacts; classification and retention policy must follow the source.

## Review triggers

Update this model when packet signing, storage, control-plane hosting, tenancy,
model-assisted inference, or graph publication policy changes.
