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
#: publication policy hash. That conflated the identity of a *snapshot* with the
#: identity of a *fact*: a semantic change anywhere in any source repository
#: moved the topology hash and re-keyed every effect in the plan, including the
#: ones whose facts had not changed at all.
#:
#: v2 fixed that by keying an effect by the fact alone. It then made the mirror
#: mistake. Downstream, ``idempotency_key`` names an *operation*: a request whose
#: key matches an existing record is answered ``DUPLICATE`` and its content is
#: not admitted. Under v2 a re-publication of the same fact with materially
#: stronger evidence, weaker evidence, or a recalibrated confidence carried the
#: previous key, so downstream read a genuinely new epistemic state as a retry of
#: the old one and discarded it.
#:
#: v3 separates the two identities that were being conflated in both directions:
#:
#: ``candidate_id``
#:     the logical fact. Stable while only evidence strength moves.
#:
#: the effect key
#:     the exact durable admission being requested — the fact, the contract used
#:     to lower it, the local evidence supporting it, and the confidence claimed
#:     for it. Two calls carrying one v3 key request the same durable operation,
#:     which is what the downstream contract means by a retry.
#:
#: Global snapshot hashes remain on the intent as provenance, which is what they
#: actually describe.
IDEMPOTENCY_ALGORITHM_VERSION = "v3"
#: Alias used by the hash-locality evaluator and its contract tests.
EFFECT_IDENTITY_ALGORITHM_VERSION = IDEMPOTENCY_ALGORITHM_VERSION

#: Domain separator, so an effect identity can never collide with another
#: digest computed over similarly-shaped data.
_EFFECT_IDENTITY_DOMAIN = "l9.memory-effect-id/v3"

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


def confidence_semantics(
    *,
    score: float,
    method: str,
    evidence_count: int,
    confidence_policy_version: str,
) -> dict[str, Any]:
    """Return the confidence claim this write is making.

    A recalibrated score, a different derivation method, a different supporting
    count, or a different confidence policy all change what is being asserted
    about how strongly the fact is known — which makes the write a different
    write. ``calibrated_at`` is absent: when a score was computed is not part of
    what the score claims.
    """
    return {
        "score": score,
        "method": method,
        "evidence_count": evidence_count,
        "confidence_policy_version": confidence_policy_version,
    }


def evidence_semantics(
    *,
    evidence_kind: str,
    source_content_digest: str | None,
    stable_source_locator: str | None,
) -> dict[str, Any]:
    """Return one supporting evidence item as it bears on the requested write.

    Three things only: what kind of evidence it is, the digest of the bytes it
    reads, and where those bytes live. Deliberately absent are the observation
    timestamp, the parent packet identity, the repository revision, and the
    topology evidence id — all of which move when the surrounding snapshot moves
    while the local bytes supporting this fact stay exactly the same.
    """
    return {
        "evidence_kind": evidence_kind,
        "source_content_digest": source_content_digest,
        "stable_source_locator": stable_source_locator,
    }


def effect_identity(
    identity: dict[str, Any],
    *,
    lowering_contract_version: str,
    local_evidence: tuple[dict[str, Any], ...],
    confidence: dict[str, Any],
    derivation_kind: str | None = None,
) -> dict[str, Any]:
    """Return the canonical identity of the exact durable admission requested."""
    return {
        "domain": _EFFECT_IDENTITY_DOMAIN,
        "candidate_id": candidate_id(identity),
        "lowering_contract_version": lowering_contract_version,
        # Sorted so that the order evidence happened to be resolved in cannot
        # change the key. Two writes supported by the same evidence are one write.
        "local_evidence_semantics": sorted(
            local_evidence, key=lambda item: publication_semantic_hash(item)
        ),
        "derivation_kind": derivation_kind,
        "confidence_semantics": confidence,
    }


def idempotency_key(
    identity: dict[str, Any],
    *,
    lowering_contract_version: str,
    local_evidence: tuple[dict[str, Any], ...] = (),
    confidence: dict[str, Any] | None = None,
    derivation_kind: str | None = None,
) -> str:
    """Return the identity of the exact durable write this intent requests.

    Downstream, a matching key means "this is the same operation you already
    performed", and the request is answered ``DUPLICATE`` without admitting its
    content. So the key must move exactly when the requested operation differs,
    and three groups of inputs follow from that:

    * The **fact** — via ``candidate_id``: content, structured assertion,
      namespace, memory class, operation. A different fact is a different write.
    * The **lowering contract** — the same topology fact lowered by different
      rules is a different write.
    * The **local epistemic state** — the evidence supporting this fact and the
      confidence claimed for it. Re-publishing a fact with stronger evidence, or
      weaker, or a recalibrated score, requests a genuinely different durable
      admission; keying it as a retry of the previous write is what causes
      downstream to answer ``DUPLICATE`` and silently drop the new state.

    Everything that describes the *snapshot* rather than this write stays out:
    the topology packet id and semantic hash, the plan id and hash, the whole-RMP
    hash, the repository revision when the local source bytes are unchanged, the
    evidence of unrelated facts, the checkout path, and every timestamp.
    """
    return f"{IDEMPOTENCY_NAMESPACE}/{IDEMPOTENCY_ALGORITHM_VERSION}:" + publication_semantic_hash(
        effect_identity(
            identity,
            lowering_contract_version=lowering_contract_version,
            local_evidence=local_evidence,
            confidence=confidence or {},
            derivation_kind=derivation_kind,
        )
    ).removeprefix(_SHA_PREFIX)


def plan_id(semantic_digest: str) -> str:
    """Return the plan identifier derived from the plan semantic hash."""
    return f"publication-plan:{semantic_digest.removeprefix(_SHA_PREFIX)}"
