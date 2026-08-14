# ADR-0021: Packet bundle sink verifies by bundle kind

- **Status:** Accepted
- **Date:** 2026-08-14
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

`PacketBundleOutputSink` performs a post-write verification: after staging a bundle it re-reads the staged directory and loads it back before the atomic rename, so a corrupt or contract-violating bundle can never be committed. That verification was hard-coded to `load_topology_bundle`, which loads and validates the staged `packet.json` strictly as a Topology Packet (`l9.topology`).

The sink is not used only for Topology Packets. The compatibility ingress path (`l9-topology scan` / `scan-many`, `cli._write_synthetic_bundle`) reuses the same sink to write an intermediate **Repository Model Packet** (`l9.repository-model`) bundle into a temporary directory before compiling it. Because the post-write verifier assumed Topology Packets, committing a structurally valid Repository Model bundle failed with `6 validation errors for TopologyPacket`, the commit receipt became `failed`, and the CLI aborted with `direct observation bundle commit failed`. The result: `scan` and `scan-many` were broken at runtime for every input, a documented contract with no working runtime path. No test exercised the sink commit of a Repository Model bundle (existing tests only asserted the synthetic bundle's destination paths), so CI stayed green.

This conflated two distinct concerns — "commit an immutable packet bundle" and "the bundle is a Topology Packet" — inside one write boundary.

## Decision

- `PacketBundleOutputSink` accepts an optional `bundle_verifier: Callable[[Path], object]` that performs the pre-rename verification of the staged bundle.
- The default remains `load_topology_bundle`, so every existing Topology Packet caller is unchanged and Topology Packet verification is not weakened.
- Callers that commit a different canonical bundle kind pass the matching loader. The scan compatibility path passes `load_repository_model_bundle`, which fully validates the Repository Model Packet, its manifest, and its validation receipt.
- The atomic stage-verify-rename contract, immutability, collision policy, and truthful receipts are preserved; only the identity of the verifier is made explicit.

This refines ADR-0007 (OutputSink is the only write boundary); it does not supersede it. The single write boundary is unchanged — the sink's post-write verification is made bundle-kind-aware rather than silently Topology-Packet-specific.

## Consequences

### Positive

- `scan` / `scan-many` compatibility ingress work at runtime and produce a validated Topology Packet bundle.
- Each committed bundle is verified against its own canonical contract, not a single assumed kind.
- Topology Packet commits keep byte-for-byte identical behavior (default verifier).

### Costs and constraints

- Callers writing a non-Topology bundle must supply the correct verifier; omitting it re-applies Topology Packet verification and will reject the bundle. This is intentional fail-closed behavior.
- The sink now depends on a caller-supplied contract for the strongest verification, so new bundle kinds must ship with a matching loader.

## Alternatives considered

- **Rejected:** Make the sink infer the bundle kind from `packet.json`. Inference in the write boundary is fragile and hides the caller's intent; explicit injection is auditable and fail-closed.
- **Rejected:** Give the scan path its own bespoke sink. That would duplicate the atomic stage-verify-rename logic and risk drift from the canonical write boundary (ADR-0007).
- **Rejected:** Relax `load_topology_bundle` to also accept Repository Model Packets. That would weaken Topology Packet verification for every caller.

## Compliance and validation

- `tests/test_runtime_boundaries_v5.py::test_packet_bundle_sink_verifies_by_bundle_kind` proves the default verifier rejects a Repository Model bundle while the Repository Model verifier commits it.
- `tests/test_runtime_boundaries_v5.py::test_scan_compatibility_ingress_produces_valid_topology_bundle` exercises `scan` end to end and loads the result as a passing Topology Packet.
- Existing Topology Packet sink tests continue to pass unchanged (default verifier).

## Related artifacts

- `src/l9_constellation_topology/io/packet_bundle_output_sink.py`
- `src/l9_constellation_topology/cli.py` (`_write_synthetic_bundle`)
- `src/l9_constellation_topology/packets/loader.py` (`load_repository_model_bundle`, `load_topology_bundle`)
- ADR-0007 (OutputSink is the only write boundary)
