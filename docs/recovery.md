# Recovery

## Idempotency

The topology idempotency key is derived from sorted parent semantic hashes, compiler version, topology profile hash, schema-contract hash, and output packet type.

A semantically identical retry carries the same key. The production control plane must resolve that key before dispatch and return the existing validated packet when present.

## Local registry

`LocalPacketRegistry` stores:

- idempotency key;
- output `PacketRef`;
- Validation Receipt URI;
- Commit Receipt URI;
- publication or acknowledgement state;
- run and stage metadata.

It supports deterministic local tests and same-host recovery. It is not a substitute for Postgres because GitHub-hosted runners are ephemeral.

## Callback loss

Publication occurs before callback delivery. If the packet is published and callback delivery fails:

1. the worker reports a retryable callback failure;
2. the control-plane reconciler searches the packet registry or immutable store by idempotency key;
3. the published bundle is fetched and verified;
4. stage completion is repaired atomically;
5. duplicate publication is avoided.

## Retry classes

Retryable:

- packet download timeout;
- temporary OCI registry failure;
- runner capacity failure;
- callback timeout;
- temporary control API failure.

Non-retryable:

- invalid signature;
- invalid schema;
- non-object target revision;
- unsupported packet version;
- failed parent Validation Receipt;
- semantic hash mismatch;
- repository or profile mismatch;
- topology invariant failure.

## Dead letters

After retry exhaustion, the external control plane must preserve run ID, stage ID, input packet references, last TransportPacket, error classification, attempt count, GitHub run references, and required operator action.

## Manual replay

`l9-manual-replay.yml` emits a signed `l9.replay-request/1.0.0`. Replay is submitted to the control plane rather than directly executing the worker. The control plane remains responsible for authorization, lineage, idempotency, and dry-run policy.
