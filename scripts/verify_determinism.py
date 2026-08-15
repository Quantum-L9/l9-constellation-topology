#!/usr/bin/env python3
"""Compile the canonical fixture twice with different execution timestamps.

The same two-run comparison is applied to the derived publication plan, so a
timestamp or ordering leak in publication lowering fails the gate too.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.publication import (
    build_publication_plan,
    load_publication_policy,
)

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

    policy = load_publication_policy(ROOT)
    plan_a = build_publication_plan(
        first.materialized, policy, published_at=datetime(2026, 2, 2, tzinfo=UTC)
    )
    plan_b = build_publication_plan(
        second.materialized, policy, published_at=datetime(2026, 8, 9, tzinfo=UTC)
    )
    plan_semantic_equal = plan_a.semantic_hash == plan_b.semantic_hash
    plan_identity_equal = plan_a.plan_id == plan_b.plan_id
    candidates_equal = [item.candidate_id for item in plan_a.candidates] == [
        item.candidate_id for item in plan_b.candidates
    ]
    idempotency_equal = [item.idempotency_key for item in plan_a.candidates] == [
        item.idempotency_key for item in plan_b.candidates
    ]
    packet_deterministic = semantic_equal and payload_equal
    plan_deterministic = (
        plan_semantic_equal and plan_identity_equal and candidates_equal and idempotency_equal
    )

    result = {
        "status": "passed" if packet_deterministic and plan_deterministic else "failed",
        "semantic_hash_equal": semantic_equal,
        "payload_hashes_equal": payload_equal,
        "semantic_hash": packet_a.semantic_hash,
        "artifact_hash_equal": packet_a.artifact_hash == packet_b.artifact_hash,
        "publication_plan_semantic_hash_equal": plan_semantic_equal,
        "publication_plan_id_equal": plan_identity_equal,
        "publication_candidate_ids_equal": candidates_equal,
        "publication_idempotency_keys_equal": idempotency_equal,
        "publication_plan_semantic_hash": plan_a.semantic_hash,
        "publication_eligible_count": len(plan_a.eligible_candidates),
        "publication_held_count": len(plan_a.held_candidates),
        "publication_rejected_count": len(plan_a.rejected_candidates),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if packet_deterministic and plan_deterministic else 1


if __name__ == "__main__":
    raise SystemExit(main())
