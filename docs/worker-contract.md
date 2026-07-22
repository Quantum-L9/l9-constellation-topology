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
- an approved callback identifier. The packet never selects a URL, environment variable, or credential.

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

The callback payload contains only `callback_id`. `.l9/callback-policy.yaml` maps that identifier to worker-local URL and credential variables. The client requires an enabled entry, exact expected host and optional port, segment-bound path matching, rejection of encoded slash and backslash ambiguity, redirect rejection, DNS inspection, unsafe-address blocking, and TLS for production destinations. The checked-in production entry is disabled until an approved hostname is committed. Raw credentials and destination URLs are never selected by the packet.

A callback HTTP 2xx response is the control-plane acknowledgement boundary. Production control-plane implementation must atomically register the packet and commit the stage result before returning success.

## Idempotency and recovery

The idempotency key is derived from:

- sorted parent packet semantic hashes;
- compiler version;
- exact compiler build identity;
- aggregate semantic configuration hash covering topology, risk, maturity, report, packet, and output policy;
- schema-contract hash and active contract versions;
- adapter or compatibility mode;
- output packet type and version.

`LocalPacketRegistry` is a SQLite WAL recovery index for tests and single-host runs. Transactions and a unique idempotency-key constraint prevent local concurrent writers from losing updates. It is not the production source of truth. The Postgres control plane owns cross-run registry state, dispatch suppression, reconciliation, retries, leases, and dead letters.

## Runtime variables

| Variable | Required | Purpose |
|---|---:|---|
| `L9_DISPATCH_HMAC_KEY` | yes | Verify dispatch and sign result packets in the foundational HMAC profile |
| `L9_DISPATCH_HMAC_KEY_ID` | ingress/replay | Key identity placed on outbound control packets |
| `L9_RESULT_HMAC_KEY_ID` | worker | Key identity placed on result callbacks |
| `L9_CONTROL_API_URL` | production callback profile | Worker-local callback destination |
| `L9_CALLBACK_TOKEN` | production callback profile | Dedicated Bearer credential for callback delivery |
| `L9_TEST_CALLBACK_URL` | local tests only | Loopback integration-test callback destination |
| `L9_PACKET_REGISTRY_FILE` | optional | Local SQLite recovery index path |

The final signing custody platform remains an external deployment decision. The repository does not store key material.

## Digest-bound publication and reuse

Production OCI input and authoritative output references must be digest-qualified. Publication uses a semantic-hash-derived staging tag, then discards tag authority in favor of the returned digest. The worker independently fetches the registry descriptor by digest, reloads the bundle, and compares packet ID, type, version, semantic hash, artifact hash, validation-receipt subject, bundle-manifest digest, and registry manifest digest with the expected publication. A valid but different packet is rejected.
