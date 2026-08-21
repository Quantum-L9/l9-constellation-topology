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

#: Algorithm version for memory-effect identity.
#:
#: v1 bound each key to the whole Topology Packet semantic hash and the whole
#: publication policy hash. That conflated two different things: the identity of
#: a *snapshot* and the identity of a *fact*. Any semantic change anywhere in
#: any source repository moved the topology hash and therefore re-keyed every
#: effect in the plan, including the ones whose facts had not changed at all.
#:
#: v2 keys an effect by the effect's own semantics. A fact that did not change
#: keeps its key across unrelated snapshot movement; a fact that did change gets
#: a new one. Global snapshot hashes remain on the intent as provenance, which
#: is what they actually describe.
IDEMPOTENCY_ALGORITHM_VERSION = "v2"
#: Alias used by the hash-locality evaluator and its contract tests.
EFFECT_IDENTITY_ALGORITHM_VERSION = IDEMPOTENCY_ALGORITHM_VERSION

#: Domain separator, so an effect identity can never collide with another
#: digest computed over similarly-shaped data.
_EFFECT_IDENTITY_DOMAIN = "l9.memory-effect-id/v2"

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
    operation: str,
    candidate_kind: str,
    namespace: str,
    memory_class: str,
    content: str,
    assertion: dict[str, str | None] | None,
    source_topology_entity_ids: tuple[str, ...],
) -> dict[str, Any]:
    """Return the canonical semantic identity of a single publication fact.

    Everything here describes the effect itself: what operation it performs,
    where it lands, and what it asserts. Nothing here describes the snapshot
    that happened to carry it — no packet id, no topology hash, no plan hash,
    no wall clock. Those live on the intent as provenance instead.
    """
    return {
        "operation": operation,
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
    lowering_contract_version: str,
) -> str:
    """Return the fact-local identity of a single memory effect.

    The key is a function of the fact and of the contract used to lower it,
    and of nothing else. Two consequences follow, and both are intended:

    * An unrelated edit somewhere else in the constellation moves the RMP,
      topology, and plan hashes but leaves this key alone, so downstream sees
      the unchanged fact as the duplicate it is.
    * A change to what this fact actually asserts — its content, assertion,
      namespace, memory class, or operation — produces a new key, so
      downstream admits it as the new fact it is.

    The lowering contract version participates because a different lowering
    of the same topology fact is a different effect.
    """
    digest = publication_semantic_hash(
        {
            "domain": _EFFECT_IDENTITY_DOMAIN,
            "candidate_id": candidate_id(identity),
            "lowering_contract_version": lowering_contract_version,
        }
    ).removeprefix(_SHA_PREFIX)
    return f"{IDEMPOTENCY_NAMESPACE}/{IDEMPOTENCY_ALGORITHM_VERSION}:{digest}"


def plan_id(semantic_digest: str) -> str:
    """Return the plan identifier derived from the plan semantic hash."""
    return f"publication-plan:{semantic_digest.removeprefix(_SHA_PREFIX)}"
