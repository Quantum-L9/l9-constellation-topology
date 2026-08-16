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

#: Algorithm version of the downstream effect identity. ``v1`` bound every effect
#: to the whole Topology Packet hash and the whole publication policy hash, so an
#: unrelated change anywhere in a snapshot re-keyed every otherwise unchanged
#: durable write. ``v2`` keys an effect on its own semantics.
EFFECT_IDENTITY_ALGORITHM_VERSION = "v2"

#: Version of the lowering shape itself. A change to how a topology fact becomes a
#: memory write is a change to the requested effect, even when the fact is equal.
LOWERING_CONTRACT_VERSION = "1.0.0"

#: Namespace of a lowered effect key. The algorithm version is encoded in the
#: namespace so a v1 key and a v2 key can never collide or be mistaken for one
#: another downstream.
IDEMPOTENCY_NAMESPACE = f"l9-topology-publication/{EFFECT_IDENTITY_ALGORITHM_VERSION}"

#: Retained for provenance and migration reasoning: the ``v1`` namespace, which
#: no longer keys any effect this repository plans.
LEGACY_IDEMPOTENCY_NAMESPACE_V1 = "l9-topology-publication"

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


def evidence_semantic_identity(
    *,
    kind: str,
    source_digest: str | None,
    source_path: str | None,
    line_number: int | None,
    derivation_id: str | None = None,
) -> dict[str, Any]:
    """Return the local semantic identity of one supporting evidence reference.

    Evidence is bound by what it *is* — its kind, the exact digest of the content
    it was read from, and a bounded locator within that source — never by the
    repository-wide revision it happened to be observed at. An unchanged file
    supporting an unchanged fact keeps the same evidence identity across
    commits that touched other files.

    ``evidence_id`` is deliberately excluded: upstream derives it from a source
    reference that embeds the whole-repository revision, so binding it would
    reintroduce exactly the global coupling this algorithm removes. It remains in
    provenance and in the plan's lineage.
    """
    return {
        "kind": kind,
        "source_digest": source_digest,
        "source_path": source_path,
        "line_number": line_number,
        "derivation_id": derivation_id,
    }


def confidence_semantic_identity(
    *,
    score: float,
    method: str,
    evidence_count: int,
    policy_version: str,
) -> dict[str, Any]:
    """Return the normalized confidence semantics of a requested write.

    Confidence is part of the durable record, so a material confidence change for
    the same fact is a different effect and is meant to re-key.
    """
    return {
        "score": score,
        "method": method,
        "evidence_count": evidence_count,
        "policy_version": policy_version,
    }


def effect_semantic_view(
    *,
    operation: str,
    fact_identity: dict[str, Any],
    namespace: str,
    memory_class: str,
    content: str,
    assertion: dict[str, str | None] | None,
    confidence: dict[str, Any],
    evidence: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Return every local semantic difference that distinguishes one durable write.

    Included is what the downstream store would actually record: the operation,
    where it lands, what it says, how sure it is, and what supports it.

    Excluded — deliberately and by name — is everything global to the snapshot
    that produced it: the Topology Packet id and semantic hash, the Repository
    Model Packet hash, the publication plan id and semantic hash, the whole
    publication policy hash, the repository-wide source revision, wall-clock
    stamps, checkout paths, and any container's artifact hash. Those remain on
    the candidate as provenance, where they belong; they do not decide whether
    two requested writes are the same write.
    """
    return {
        "algorithm": EFFECT_IDENTITY_ALGORITHM_VERSION,
        "lowering_contract_version": LOWERING_CONTRACT_VERSION,
        "operation": operation,
        "fact": fact_identity,
        "namespace": namespace,
        "memory_class": memory_class,
        "content": content,
        "assertion": assertion,
        "confidence": confidence,
        "evidence": list(evidence),
    }


def effect_idempotency_key(view: dict[str, Any]) -> str:
    """Return the deterministic downstream key for one requested effect."""
    digest = publication_semantic_hash(view).removeprefix(_SHA_PREFIX)
    return f"{IDEMPOTENCY_NAMESPACE}:{digest}"


def plan_id(semantic_digest: str) -> str:
    """Return the plan identifier derived from the plan semantic hash."""
    return f"publication-plan:{semantic_digest.removeprefix(_SHA_PREFIX)}"
