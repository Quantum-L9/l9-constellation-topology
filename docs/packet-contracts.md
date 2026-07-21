# Packet Contracts

Machine-readable JSON Schemas live in `contracts/`. The compiler does not define a competing transport container. It validates the TransportPacket fields needed by the topology worker and treats its payload schema as the stage contract.

Repository Model Packets are normalized through versioned adapters. Unsupported versions fail closed. Topology Packets reference deterministic payload documents stored in the same immutable bundle. Validation Receipts remain separate and reference the exact topology semantic hash.

A packet bundle contains:

```text
manifest.json
packet.json
payload/*.json
receipts/validation-receipt.json
```

The bundle manifest lists exact byte hashes and sizes for every member.

Diagnostics from Repository Model Packets are normalized into typed `DiagnosticRecord` payloads. The topology validator enforces conservation: each accepted input diagnostic must remain represented in the output or be rejected through explicit validation.

Validation Receipts distinguish runtime model construction, independent checked-in JSON Schema evaluation, semantic invariants, evidence rules, and cross-packet checks.
