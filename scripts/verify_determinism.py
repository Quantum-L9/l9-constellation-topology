#!/usr/bin/env python3
"""Compile the canonical fixture twice with different execution timestamps."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from l9_constellation_topology.compiler import compile_topology

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)


def main() -> int:
    first = compile_topology(
        ROOT,
        INPUTS,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = compile_topology(
        ROOT,
        INPUTS,
        created_at=datetime(2026, 7, 21, tzinfo=UTC),
    )
    packet_a = first.materialized.packet
    packet_b = second.materialized.packet
    semantic_equal = packet_a.semantic_hash == packet_b.semantic_hash
    payload_equal = packet_a.payload_hashes == packet_b.payload_hashes
    result = {
        "status": "passed" if semantic_equal and payload_equal else "failed",
        "semantic_hash_equal": semantic_equal,
        "payload_hashes_equal": payload_equal,
        "semantic_hash": packet_a.semantic_hash,
        "artifact_hash_equal": packet_a.artifact_hash == packet_b.artifact_hash,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if semantic_equal and payload_equal else 1


if __name__ == "__main__":
    raise SystemExit(main())
