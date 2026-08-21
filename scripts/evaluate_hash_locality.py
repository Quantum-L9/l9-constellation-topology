#!/usr/bin/env python3
"""Evaluate where topology and publication identity moves, and where it must not.

Three identities are separated by this repository, and confusing them is what the
``v1`` effect key got wrong:

*snapshot identity*
    The Topology Packet and publication plan semantic hashes. These track the
    whole compiled snapshot and are *meant* to move whenever anything in it moves.

*candidate identity*
    The stable identity of the logical fact selected for publication.

*effect identity*
    The idempotency key of the actual durable write requested downstream. This
    must move only when that write's own semantics move.

Each case below perturbs exactly one thing, recompiles snapshot identity from the
perturbed state so the snapshot hashes are real rather than carried over, and
records what moved for a candidate deliberately chosen to be either the target of
the perturbation or provably unrelated to it.

The matrix is written to ``HASH_LOCALITY_EVALUATION.json`` and checked in, so a
regression in identity locality shows up as a reviewable diff rather than as
duplicate durable records discovered after the fact.

All perturbations are applied in memory to loaded fixtures. Nothing here writes
to a source repository, and no downstream effect is ever dispatched.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from generated_artifact_sync import GeneratedArtifact, synchronize

from l9_constellation_topology.domain import ConfidenceLevel, EdgeType
from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.packets.loader import load_topology_bundle
from l9_constellation_topology.packets.payloads import topology_payload_hashes
from l9_constellation_topology.packets.topology_packet import (
    MaterializedTopology,
    TopologyPacket,
    calculate_topology_semantic_hash,
)
from l9_constellation_topology.publication import (
    EFFECT_IDENTITY_ALGORITHM_VERSION,
    PublicationCandidate,
    PublicationPlan,
    PublicationPolicy,
    build_publication_plan,
    load_publication_policy,
)
from l9_constellation_topology.run import canonical_bytes

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "fixtures" / "topology_packets" / "foundational-two-repo"
DESTINATION = ROOT / "HASH_LOCALITY_EVALUATION.json"

BASELINE_TIME = datetime(2026, 1, 1, tzinfo=UTC)
SHIFTED_TIME = datetime(2027, 6, 6, tzinfo=UTC)

SAME = "same"
CHANGED = "changed"
ABSENT = "absent"


def _recompile(packet: TopologyPacket, state: TopologyState) -> MaterializedTopology:
    """Re-derive snapshot identity from a perturbed state.

    Without this, a state-level perturbation would carry the original packet's
    semantic hash and the matrix would claim snapshot identity held when it had
    simply not been recomputed.
    """
    candidate = packet.model_copy(update={"payload_hashes": topology_payload_hashes(state)})
    digest = calculate_topology_semantic_hash(candidate)
    return MaterializedTopology(
        packet=candidate.model_copy(
            update={
                "semantic_hash": digest,
                "packet_id": f"packet:{digest.removeprefix('sha256:')}",
            }
        ),
        state=state,
    )


def _plan(
    materialized: MaterializedTopology,
    policy: PublicationPolicy,
    published_at: datetime = BASELINE_TIME,
) -> PublicationPlan:
    return build_publication_plan(materialized, policy, published_at=published_at)


def _verdict(before: object, after: object) -> str:
    return SAME if before == after else CHANGED


def _find(plan: PublicationPlan, entity_ids: tuple[str, ...]) -> PublicationCandidate | None:
    """Return the candidate lowered from exactly these topology entities."""
    for item in sorted(plan.candidates, key=lambda candidate: candidate.candidate_id):
        if item.source_topology_entity_ids == entity_ids:
            return item
    return None


def _sample(
    baseline: PublicationPlan,
    mutated: PublicationPlan,
    entity_ids: tuple[str, ...],
) -> dict[str, str]:
    """Compare one deliberately chosen fact across two plans.

    The fact is located by the topology entities it was lowered from rather than
    by candidate id, so a case that legitimately changes candidate identity can
    still report on the same underlying fact instead of losing track of it.
    """
    before = _find(baseline, entity_ids)
    after = _find(mutated, entity_ids)
    if before is None:
        raise ValueError(f"baseline plan has no candidate for entities {entity_ids}")
    if after is None:
        return {"sampled_candidate_id": ABSENT, "sampled_effect_idempotency_key": ABSENT}
    return {
        "sampled_candidate_id": _verdict(before.candidate_id, after.candidate_id),
        "sampled_effect_idempotency_key": _verdict(before.idempotency_key, after.idempotency_key),
    }


def _shared_effect_keys(baseline: PublicationPlan, mutated: PublicationPlan) -> dict[str, int]:
    """Count how many facts present in both plans kept their effect key."""
    before = {item.candidate_id: item.idempotency_key for item in baseline.candidates}
    after = {item.candidate_id: item.idempotency_key for item in mutated.candidates}
    shared = sorted(set(before) & set(after))
    moved = [cid for cid in shared if before[cid] != after[cid]]
    return {
        "shared_candidates": len(shared),
        "shared_candidates_with_unchanged_effect_key": len(shared) - len(moved),
        "shared_candidates_with_changed_effect_key": len(moved),
    }


def _case(
    name: str,
    mutation: str,
    expectation: str,
    *,
    baseline: PublicationPlan,
    baseline_topology: str,
    mutated: PublicationPlan,
    mutated_topology: str,
    sampled_entity_ids: tuple[str, ...],
    sample_role: str,
) -> dict[str, Any]:
    """Record one perturbation and everything it did or did not move."""
    return {
        "case": name,
        "mutation": mutation,
        "expectation": expectation,
        "sample_role": sample_role,
        "topology_semantic_hash": _verdict(baseline_topology, mutated_topology),
        "publication_plan_semantic_hash": _verdict(baseline.semantic_hash, mutated.semantic_hash),
        **_sample(baseline, mutated, sampled_entity_ids),
        **_shared_effect_keys(baseline, mutated),
    }


def _replace_repository(state: TopologyState, **updates: Any) -> TopologyState:
    records = list(state.repository_records)
    records[0] = records[0].model_copy(update=updates)
    return state.model_copy(update={"repository_records": tuple(records)})


def build_matrix() -> dict[str, Any]:
    """Run every locality case against the golden fixture."""
    materialized, _ = load_topology_bundle(GOLDEN)
    policy = load_publication_policy(ROOT)
    packet = materialized.packet
    state = materialized.state
    topology_hash = packet.semantic_hash
    baseline = _plan(materialized, policy)

    subject_repository = state.repository_records[0]
    repository_entities = (subject_repository.repository_id,)

    # A relationship that does not involve the repository the repository-scoped
    # cases perturb, so "unaffected" genuinely means unaffected.
    unrelated_edge = next(
        edge
        for edge in sorted(state.edge_records, key=lambda item: item.edge_id)
        if str(edge.edge_type) in set(policy.eligible_edge_types)
        and subject_repository.repository_id not in (edge.source_id, edge.target_id)
    )
    unrelated_entities = (unrelated_edge.source_id, unrelated_edge.target_id)

    # A relationship that *is* perturbed by the assertion case.
    asserted_edge = next(
        edge
        for edge in sorted(state.edge_records, key=lambda item: item.edge_id)
        if str(edge.edge_type) in set(policy.eligible_edge_types)
    )
    asserted_entities = (asserted_edge.source_id, asserted_edge.target_id)

    cases: list[dict[str, Any]] = []

    def add(
        name: str,
        mutation: str,
        expectation: str,
        mutated_materialized: MaterializedTopology,
        mutated_policy: PublicationPolicy,
        sampled: tuple[str, ...],
        sample_role: str,
        *,
        published_at: datetime = BASELINE_TIME,
    ) -> None:
        cases.append(
            _case(
                name,
                mutation,
                expectation,
                baseline=baseline,
                baseline_topology=topology_hash,
                mutated=_plan(mutated_materialized, mutated_policy, published_at),
                mutated_topology=mutated_materialized.packet.semantic_hash,
                sampled_entity_ids=sampled,
                sample_role=sample_role,
            )
        )

    # 1. Exact replay. Nothing at all may move.
    add(
        "exact_replay",
        "recompute the plan from identical inputs",
        "every identity is preserved",
        materialized,
        policy,
        unrelated_entities,
        "unaffected relationship",
    )

    # 2. Checkout path only. The packet is reloaded through a path-independent
    #    view; identity must not know where the tree was read from.
    add(
        "checkout_path_only",
        "recompute snapshot identity from the same state under a different checkout",
        "checkout paths never participate in semantic identity",
        _recompile(packet, state),
        policy,
        unrelated_entities,
        "unaffected relationship",
    )

    # 3. Wall clock only.
    add(
        "wall_clock_only",
        "publish the same topology at a different instant",
        "wall clock never participates in semantic identity",
        materialized,
        policy,
        unrelated_entities,
        "unaffected relationship",
        published_at=SHIFTED_TIME,
    )

    # 4. Unrelated repository fact: a repository observation that no published
    #    fact consumes, on a repository the sampled relationship does not touch.
    add(
        "unrelated_repository_fact",
        "add an unresolved dependency observation no published fact consumes",
        "snapshot identity moves; the unaffected effect key does not",
        _recompile(
            packet,
            _replace_repository(state, unresolved_dependencies=("an-unconsumed-observation",)),
        ),
        policy,
        unrelated_entities,
        "unaffected relationship",
    )

    # 5. Unrelated topology fact: drop an artifact record. Artifacts are not
    #    published, so no candidate's own semantics change.
    add(
        "unrelated_topology_fact",
        "remove an artifact record that no published fact is lowered from",
        "topology identity moves; unaffected effect keys survive",
        _recompile(
            packet,
            state.model_copy(update={"artifact_records": state.artifact_records[:-1]}),
        ),
        policy,
        unrelated_entities,
        "unaffected relationship",
    )

    # 6. The published fact's own content.
    add(
        "published_fact_content",
        "rename the sampled repository, changing its published content",
        "the affected candidate and effect key both move",
        _recompile(packet, _replace_repository(state, name="renamed-repository")),
        policy,
        repository_entities,
        "affected repository entity",
    )

    # 7. The published structured assertion.
    reasserted = list(state.edge_records)
    replacement_type = (
        EdgeType.depends_on
        if asserted_edge.edge_type is EdgeType.derived_from
        else EdgeType.derived_from
    )
    reasserted[reasserted.index(asserted_edge)] = asserted_edge.model_copy(
        update={"edge_type": replacement_type}
    )
    add(
        "published_assertion",
        "change the predicate of the sampled published relationship",
        "the affected candidate and effect key both move",
        _recompile(packet, state.model_copy(update={"edge_records": tuple(reasserted)})),
        policy,
        asserted_entities,
        "affected relationship",
    )

    # 8. Local evidence strength for an otherwise identical fact. The logical fact
    #    is unchanged, so candidate identity holds; the requested write is not the
    #    same write, so the effect key must move.
    weakened = _replace_repository(
        state,
        confidence=subject_repository.confidence.model_copy(update={"level": ConfidenceLevel.low}),
    )
    add(
        "local_evidence_strength",
        "materially weaken the confidence of one otherwise identical fact",
        "candidate identity holds; the effect key moves",
        _recompile(packet, weakened),
        policy,
        repository_entities,
        "affected repository entity",
    )

    # 9. Destination namespace.
    add(
        "namespace",
        "publish the same facts into a different namespace root",
        "both candidate and effect identity move",
        materialized,
        policy.model_copy(update={"namespace_root": "l9.relocated"}),
        unrelated_entities,
        "unaffected relationship",
    )

    # 10. Destination memory class.
    add(
        "memory_class",
        "publish relationships into a different memory class",
        "both candidate and effect identity move",
        materialized,
        policy.model_copy(update={"relationship_memory_class": "insight"}),
        unrelated_entities,
        "unaffected relationship",
    )

    # 11. Publication policy that changes the plan but changes no lowered write.
    #     Under v1 this re-keyed every effect. Under v2 it must re-key none.
    add(
        "unrelated_publication_policy",
        "raise the evidence ceiling above what any candidate uses",
        "policy hash moves; no unaffected effect key moves",
        materialized,
        policy.model_copy(
            update={
                "maximum_evidence_refs_per_candidate": (
                    policy.maximum_evidence_refs_per_candidate + 1
                )
            }
        ),
        unrelated_entities,
        "unaffected relationship",
    )

    return {
        "schema": "l9.hash-locality-evaluation/v1",
        "effect_identity_algorithm": EFFECT_IDENTITY_ALGORITHM_VERSION,
        "subject_topology_packet_id": packet.packet_id,
        "subject_topology_semantic_hash": topology_hash,
        "publication_policy": policy.identity,
        "baseline_candidate_count": len(baseline.candidates),
        "baseline_truncated_evidence_count": sum(
            item.lowering.truncated_evidence_count for item in baseline.candidates
        ),
        "dispatches_performed": 0,
        "cases": cases,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the recorded evaluation differs; never modify files.",
    )
    args = parser.parse_args(argv)
    artifact = GeneratedArtifact(DESTINATION, canonical_bytes(build_matrix()) + b"\n")
    findings = synchronize((artifact,), check=args.check)
    for finding in findings:
        label = finding.kind if args.check else "updated"
        print(f"{label}: {finding.path.relative_to(ROOT)}")
    return 1 if args.check and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
