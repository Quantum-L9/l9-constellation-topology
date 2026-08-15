"""Deterministic identity for publication plans, candidates, and idempotency.

Every identity here is a pure function of canonical topology meaning, the
publication policy, and nothing else. Wall-clock time, checkout paths, and
artifact hashes never participate.
"""

from __future__ import annotations

import re
from typing import Any

from l9_constellation_topology.run.evidence import semantic_hash

_SHA_PREFIX = "sha256:"
_BARE_SHA256 = re.compile(r"^[a-f0-9]{64}$")

IDEMPOTENCY_NAMESPACE = "l9-topology-publication"

#: Timestamp-bearing fields of the mirrored memory contract. They carry no
#: semantic meaning for plan identity, so they are stripped before hashing in
#: addition to the volatile fields the base ``semantic_hash`` already removes.
VOLATILE_PUBLICATION_FIELDS: frozenset[str] = frozenset(
    {
        "calibrated_at",
        "observed_at",
        "published_at",
        "source_observed_at",
        "transformed_at",
        "valid_from",
        "plan_id",
    }
)

_BASE_EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {
        "created_at",
        "checked_at",
        "generated_at",
        "committed_at",
        "frozen_at",
        "run_id",
        "stage_id",
        "trace_id",
        "workflow_id",
        "artifact_hash",
        "semantic_hash",
        "packet_id",
        "receipt_id",
    }
)

PUBLICATION_EXCLUDED_FIELDS: frozenset[str] = _BASE_EXCLUDED_FIELDS | VOLATILE_PUBLICATION_FIELDS


def publication_semantic_hash(value: Any) -> str:
    """Hash publication data with every volatile timestamp removed."""
    return semantic_hash(value, excluded_fields=set(PUBLICATION_EXCLUDED_FIELDS))


def bare_digest(value: str | None) -> str | None:
    """Return a bare 64-character hex digest, or ``None`` when unavailable.

    The downstream provenance and evidence contracts accept only bare lowercase
    sha256 hex. Topology carries ``sha256:``-prefixed digests, and some evidence
    source references carry no digest at all; both are handled without inventing
    a digest that was never observed.
    """
    if value is None:
        return None
    candidate = value.removeprefix(_SHA_PREFIX).strip().lower()
    return candidate if _BARE_SHA256.match(candidate) else None


def candidate_identity(
    *,
    candidate_kind: str,
    namespace: str,
    memory_class: str,
    content: str,
    assertion: dict[str, str | None] | None,
    source_topology_entity_ids: tuple[str, ...],
) -> dict[str, Any]:
    """Return the canonical semantic identity of a single publication fact."""
    return {
        "candidate_kind": candidate_kind,
        "namespace": namespace,
        "memory_class": memory_class,
        "content": content,
        "assertion": assertion,
        "source_topology_entity_ids": tuple(source_topology_entity_ids),
    }


def candidate_id(identity: dict[str, Any]) -> str:
    """Return a stable candidate identifier for a semantic fact."""
    digest = publication_semantic_hash(identity).removeprefix(_SHA_PREFIX)
    return f"publication-candidate:{digest}"


def idempotency_key(
    identity: dict[str, Any],
    *,
    topology_semantic_hash: str,
    policy_hash: str,
) -> str:
    """Bind a fact to the topology and policy identity that produced it.

    The key changes when the source topology packet changes, which is the
    contract this program requires. Downstream therefore treats a fact
    republished from a newer Topology Packet as a distinct admission rather than
    a duplicate.
    """
    digest = publication_semantic_hash(
        {
            "fact": identity,
            "topology_semantic_hash": topology_semantic_hash,
            "policy_hash": policy_hash,
        }
    ).removeprefix(_SHA_PREFIX)
    return f"{IDEMPOTENCY_NAMESPACE}:{digest}"


def plan_id(semantic_digest: str) -> str:
    """Return the plan identifier derived from the plan semantic hash."""
    return f"publication-plan:{semantic_digest.removeprefix(_SHA_PREFIX)}"
