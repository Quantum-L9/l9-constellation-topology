# Worker Contract

## Control entry

The topology worker accepts one signed `TransportPacket` whose payload is `l9.stage-dispatch/1.0.0`.

The dispatch must name:

- run, stage, workflow, trace, and correlation identities;
- action `compile-topology`;
- target repository `Quantum-L9/l9-constellation-topology`;
- an exact lowercase Git object ID;
- one or more validated `l9.repository-model` packet references;
- the exact topology profile identity and hash;
- an immutable output URI;
- an authenticated callback reference.

The foundational profile requires `provenance.resolved_by_gate=false` and resolver `l9-ci-core`.

## Two-step trust sequence

The GitHub stage workflow deliberately separates dispatch authentication from target execution.

1. Check out trusted `main` worker authority.
2. Build a non-editable worker environment from the frozen lockfile.
3. Decode the submitted packet without using any field as control input.
4. Verify signature, key ID, transport version, payload schema, action, repository allowlist, profile, parent validation state, idempotency key, callback, output URI, and exact object-ID syntax.
5. Only after preflight passes, check out the signed target revision.
6. Build a second non-editable environment from that revision's frozen lockfile.
7. Revalidate the packet against the exact checkout and execute the stage.

An unsigned or tampered packet cannot select executable code.

## Execution sequence

```text
signed stage dispatch
        ↓
preflight authentication
        ↓
exact revision checkout
        ↓
parent packet fetch + hash/receipt verification
        ↓
Topology Packet compilation
        ↓
separate fail-closed Validation Receipt
        ↓
OutputSink packet-bundle commit
        ↓
commit receipt persistence
        ↓
packet publication
        ↓
publication re-fetch and verification
        ↓
local recovery registration
        ↓
signed stage-result callback
        ↓
control-plane acknowledgement
```

Stage success is not emitted before publication and verification complete.

## Packet stores

Supported worker URIs:

- `file:///...` for local integration and controlled single-host operation;
- `oci://...` for GHCR-compatible immutable packet artifacts via ORAS.

The worker strips the logical `oci://` prefix only at the ORAS client boundary. Packet references retain the canonical URI.

## Callback contract

The callback body is another signed `TransportPacket`, not a naked JSON result. Payloads are one of:

- `l9.stage-result/1.0.0`;
- `l9.reuse-receipt/1.0.0`;
- `l9.execution-failure/1.0.0`.

A callback token is resolved through `env:VARIABLE` indirection. Raw credentials are never serialized into a packet.

A callback HTTP 2xx response is the control-plane acknowledgement boundary. Production control-plane implementation must atomically register the packet and commit the stage result before returning success.

## Idempotency and recovery

The idempotency key is derived from:

- sorted parent packet semantic hashes;
- compiler version;
- topology profile hash;
- schema-contract hash;
- output packet type.

`LocalPacketRegistry` is a recovery index for tests and single-host runs. It is not the production source of truth. The Postgres control plane owns cross-run registry state, dispatch suppression, reconciliation, retries, leases, and dead letters.

## Runtime variables

| Variable | Required | Purpose |
|---|---:|---|
| `L9_DISPATCH_HMAC_KEY` | yes | Verify dispatch and sign result packets in the foundational HMAC profile |
| `L9_DISPATCH_HMAC_KEY_ID` | ingress/replay | Key identity placed on outbound control packets |
| `L9_RESULT_HMAC_KEY_ID` | worker | Key identity placed on result callbacks |
| `L9_CALLBACK_TOKEN` | when callback token ref uses it | Bearer credential for callback delivery |
| `L9_PACKET_REGISTRY_FILE` | optional | Local recovery index path |

The final signing custody platform remains an external deployment decision. The repository does not store key material.
