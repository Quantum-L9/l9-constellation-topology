# Deployment

## Deployment shape

```text
GitHub event
    ↓
l9-ingress workflow
    ↓ signed GitHub ingress TransportPacket
control API / Postgres Model B state machine
    ↓ signed stage-dispatch TransportPacket
l9-stage-worker workflow at exact revision
    ↓ validated Topology Packet in immutable packet store
signed stage-result callback
    ↓
Postgres packet registry + dependency activation
```

GitHub Actions is the ephemeral exact-revision worker. Postgres remains the durable scheduler, lease owner, retry engine, packet registry, outbox, reconciliation surface, and dead-letter authority.

## Required GitHub configuration

### Secrets

- `L9_DISPATCH_HMAC_KEY`
- `L9_CALLBACK_TOKEN`
- `L9_CONTROL_API_URL`
- `L9_CONTROL_API_TOKEN`

### Variables

- `L9_DISPATCH_HMAC_KEY_ID`, default `foundational-hmac-v1`
- `L9_RESULT_HMAC_KEY_ID`, default `foundational-hmac-v1`

GHCR publication uses the job-scoped `GITHUB_TOKEN` with `packages: write`. No human PAT, database owner credential, GitHub App private key, or static cloud key belongs in this repository.

## Control API obligations

The external control API must:

1. authenticate ingress and replay requests;
2. validate TransportPacket signatures and allowlists;
3. create or resolve workflow and stage identities;
4. require passed parent packet validation;
5. calculate or verify the topology idempotency key;
6. dispatch the worker with the complete signed packet encoded as base64;
7. receive signed result or failure packets;
8. atomically register packet metadata and commit stage state before acknowledging success;
9. suppress duplicate work or return the existing packet reference;
10. reconcile published packets whose callbacks were lost;
11. move exhausted work to a queryable dead-letter store.

The repository supplies the worker-side contract. It intentionally does not invent the control API's database schema or hosting platform.

## Packet publication

For GHCR-compatible storage, dispatch `output_uri` must be an immutable `oci://ghcr.io/...` reference authorized for the job. The worker:

- commits the complete bundle locally;
- includes packet, payloads, validation receipt, manifest, and commit receipt;
- pushes through ORAS;
- pulls the artifact into a clean verification directory;
- reloads and validates the published packet before callback success.

## Deployment gates

Production activation requires all of the following:

- branch protection requires `l9-pr-validate`;
- exact action SHAs remain pinned;
- dispatch and result keys are in an external secret store;
- the control API enforces atomic packet registration and stage completion;
- GHCR package permissions are restricted to required repositories;
- callback endpoints require HTTPS and authenticated bearer tokens;
- a real `l9-meta-injector` packet passes through the compiler;
- `l9-topology-ingestion-bridge` consumes the resulting packet without report-file dependencies;
- retry, dropped-callback reconciliation, dead-letter, and manual replay drills are executed.

Local tests prove the worker contract and file-store vertical slice. They do not substitute for the external control-plane and GHCR drills.
