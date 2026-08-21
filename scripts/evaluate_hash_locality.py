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
from l9_constellation_topology.domain.confidence import ConfidenceAssessment
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
from l9_constellation_topology.run.evidence import (
    EvidenceRecord,
    EvidenceSourceRef,
    make_evidence_record,
)

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


def _find(
    plan: PublicationPlan,
    entity_ids: tuple[str, ...],
    kind: str = "entity",
) -> PublicationCandidate | None:
    """Return the candidate of this kind lowered from exactly these entities.

    The kind is part of the lookup because several kinds now share a subject: a
    repository entity and every semantic claim about that repository are all
    lowered from the same single topology entity, and sampling "the repository
    fact" must not silently pick up a claim instead.
    """
    for item in sorted(plan.candidates, key=lambda candidate: candidate.candidate_id):
        if item.source_topology_entity_ids == entity_ids and item.candidate_kind == kind:
            return item
    return None


def _sample(
    baseline: PublicationPlan,
    mutated: PublicationPlan,
    entity_ids: tuple[str, ...],
    kind: str = "entity",
) -> dict[str, str]:
    """Compare one deliberately chosen fact across two plans.

    The fact is located by the topology entities it was lowered from rather than
    by candidate id, so a case that legitimately changes candidate identity can
    still report on the same underlying fact instead of losing track of it.
    """
    before = _find(baseline, entity_ids, kind)
    after = _find(mutated, entity_ids, kind)
    if before is None:
        raise ValueError(f"baseline plan has no {kind} candidate for entities {entity_ids}")
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
    sampled_kind: str = "entity",
) -> dict[str, Any]:
    """Record one perturbation and everything it did or did not move."""
    return {
        "case": name,
        "mutation": mutation,
        "expectation": expectation,
        "sample_role": sample_role,
        "topology_semantic_hash": _verdict(baseline_topology, mutated_topology),
        "publication_plan_semantic_hash": _verdict(baseline.semantic_hash, mutated.semantic_hash),
        **_sample(baseline, mutated, sampled_entity_ids, sampled_kind),
        **_shared_effect_keys(baseline, mutated),
    }


def _replace_repository(state: TopologyState, **updates: Any) -> TopologyState:
    records = list(state.repository_records)
    records[0] = records[0].model_copy(update=updates)
    return state.model_copy(update={"repository_records": tuple(records)})


def _rebuild_evidence(record: EvidenceRecord, **source_ref_updates: Any) -> EvidenceRecord:
    """Rebuild one evidence record so its identity is really recomputed.

    Editing ``source_ref`` in place would leave the old ``evidence_id`` attached
    and quietly turn the revision and content cases into no-ops. Rebuilding
    through the canonical constructor gives the record the identity it would
    genuinely have had, which is what makes the verdict meaningful.
    """
    return make_evidence_record(
        subject_id=record.subject_id,
        field=record.field,
        stage=record.stage,
        evidence_class=record.evidence_class,
        source_type=record.source_type,
        source_ref=record.source_ref.model_copy(update=source_ref_updates),
        value=record.value,
        confidence=record.confidence,
        producer=record.producer,
        producer_version=record.producer_version,
        created_at=record.created_at,
    )


_EVIDENCE_BEARING_FIELDS: tuple[str, ...] = (
    "repository_records",
    "artifact_records",
    "capability_records",
    "semantic_claims",
    "edge_records",
    "flow_records",
    "graph_records",
    "risks",
    "maturity",
    "unknowns",
    "conflicts",
    "diagnostics",
)


def _remap_every_evidence_ref(state: TopologyState, remapped: dict[str, str]) -> TopologyState:
    """Re-point every citation in the state at the rebuilt evidence.

    A repository's evidence is cited by more than the repository record: its
    graph node and its edges were derived from the same observation and cite the
    same records. Remapping only the repository would leave those citations
    dangling, and their lowered evidence sets would shrink for a reason the case
    never intended to test. Every citation moves together, so what the matrix
    reports afterwards is the perturbation and nothing else.
    """
    updates: dict[str, Any] = {}
    for field in _EVIDENCE_BEARING_FIELDS:
        updates[field] = tuple(
            record.model_copy(
                update={
                    "evidence_refs": tuple(
                        sorted(remapped.get(ref, ref) for ref in record.evidence_refs)
                    )
                }
            )
            for record in getattr(state, field)
        )
    return state.model_copy(update=updates)


def _remap_repository_evidence(
    state: TopologyState,
    rebuild: Any,
) -> TopologyState:
    """Rebuild the evidence the sampled repository cites, and re-point every citation."""
    cited = set(state.repository_records[0].evidence_refs)
    if not cited:
        raise ValueError("sampled repository cites no evidence")
    remapped: dict[str, str] = {}
    evidence: list[EvidenceRecord] = []
    for record in state.evidence:
        if record.evidence_id in cited:
            replacement = rebuild(record)
            remapped[record.evidence_id] = replacement.evidence_id
            evidence.append(replacement)
        else:
            evidence.append(record)
    updated = _remap_every_evidence_ref(state, remapped)
    return updated.model_copy(
        update={"evidence": tuple(sorted(evidence, key=lambda item: item.evidence_id))}
    )


def _add_repository_evidence(state: TopologyState) -> TopologyState:
    """Add one genuinely new supporting record to the sampled repository."""
    subject = state.repository_records[0]
    extra = make_evidence_record(
        subject_id=subject.repository_id,
        field="languages",
        stage="hash_locality_evaluation",
        evidence_class="observed",
        source_type="file",
        source_ref=EvidenceSourceRef(
            source_path="corroborating-observation.toml",
            line_number=1,
            content_hash="sha256:" + "c" * 64,
        ),
        value="an additional corroborating observation",
        confidence=ConfidenceAssessment.deterministic(corroborated=True),
        producer="hash-locality-evaluation",
        producer_version="1.0.0",
        created_at=subject_evidence_instant(state),
    )
    strengthened = _replace_repository(
        state,
        evidence_refs=tuple(sorted({*subject.evidence_refs, extra.evidence_id})),
    )
    return strengthened.model_copy(
        update={
            "evidence": tuple(sorted((*state.evidence, extra), key=lambda item: item.evidence_id))
        }
    )


def _drop_repository_evidence(state: TopologyState) -> TopologyState:
    """Stop citing one supporting record from the sampled repository.

    The record stays in the pool. Removing it outright would weaken every other
    fact that also rests on it, and the case under test is one fact losing
    support, not the constellation losing an observation.
    """
    subject = state.repository_records[0]
    if len(subject.evidence_refs) < 2:
        raise ValueError("sampled repository must cite more than one evidence record")
    dropped = sorted(subject.evidence_refs)[0]
    return _replace_repository(
        state,
        evidence_refs=tuple(ref for ref in subject.evidence_refs if ref != dropped),
    )


def subject_evidence_instant(state: TopologyState) -> datetime:
    """Return a deterministic instant taken from the state's own evidence."""
    return state.evidence[0].created_at if state.evidence else BASELINE_TIME


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
        sampled_kind: str = "entity",
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
                sampled_kind=sampled_kind,
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
        sampled_kind="relationship",
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
        sampled_kind="relationship",
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
        sampled_kind="relationship",
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
        sampled_kind="relationship",
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
        sampled_kind="relationship",
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
        sampled_kind="relationship",
    )

    # 8. Confidence recalibrated for an otherwise identical fact. The logical fact
    #    is unchanged, so candidate identity holds; the requested durable write is
    #    not the same write, so the effect key must move. Under v2 it did not, and
    #    downstream answered the recalibrated write with DUPLICATE.
    add(
        "unchanged_fact_confidence_change",
        "materially weaken the confidence of one otherwise identical fact",
        "candidate identity holds; the effect key moves",
        _recompile(
            packet,
            _replace_repository(
                state,
                confidence=subject_repository.confidence.model_copy(
                    update={"level": ConfidenceLevel.low}
                ),
            ),
        ),
        policy,
        repository_entities,
        "affected repository entity",
    )

    # 8a. The same fact, the same evidence, the same confidence. Re-deriving the
    #     state changes nothing anyone can observe, so nothing may move.
    add(
        "unchanged_fact_same_evidence_same_confidence",
        "re-derive an identical state and republish the same fact",
        "an identical fact with identical support is the same write",
        _recompile(packet, state.model_copy(update={"evidence": state.evidence})),
        policy,
        repository_entities,
        "affected repository entity",
    )

    # 8b. More evidence for the same fact. The claim is the same claim; the
    #     epistemic state behind it is not, so the write is a different write.
    add(
        "unchanged_fact_stronger_evidence",
        "add a corroborating evidence record to one otherwise identical fact",
        "candidate identity holds; the effect key moves",
        _recompile(packet, _add_repository_evidence(state)),
        policy,
        repository_entities,
        "affected repository entity",
    )

    # 8c. Less evidence for the same fact. Symmetric to 8b: losing support is as
    #     much a change of epistemic state as gaining it.
    add(
        "unchanged_fact_weaker_evidence",
        "drop a supporting evidence record from one otherwise identical fact",
        "candidate identity holds; the effect key moves",
        _recompile(packet, _drop_repository_evidence(state)),
        policy,
        repository_entities,
        "affected repository entity",
    )

    # 8d. Only when the evidence was observed. Nothing about the fact or its
    #     support changed, so re-observing it is a retry, not a new write.
    add(
        "evidence_timestamp_only",
        "re-stamp the observation time of the evidence supporting one fact",
        "observation time is not part of what a write asserts",
        _recompile(
            packet,
            _remap_repository_evidence(
                state,
                lambda record: record.model_copy(update={"created_at": SHIFTED_TIME}),
            ),
        ),
        policy,
        repository_entities,
        "affected repository entity",
    )

    # 8e. A new commit that leaves the supporting bytes untouched. The evidence
    #     ids genuinely move here — they are rebuilt, not edited — and the effect
    #     key must still hold, because the file that supports the claim did not
    #     change.
    add(
        "source_repository_revision_only_with_same_local_content",
        "advance the source revision while the cited file content is unchanged",
        "a new commit that did not touch the supporting bytes is the same write",
        _recompile(
            packet,
            _remap_repository_evidence(
                state,
                lambda record: _rebuild_evidence(record, source_revision="git:" + "f" * 40),
            ),
        ),
        policy,
        repository_entities,
        "affected repository entity",
    )

    # 8f. The supporting bytes changed while the published text did not. The fact
    #     reads identically and the evidence beneath it does not, so the claim is
    #     the same claim resting on different ground.
    add(
        "local_source_content_changes_but_claim_text_remains_same",
        "change the digest of the cited source content, leaving the fact's text alone",
        "candidate identity holds; the effect key moves",
        _recompile(
            packet,
            _remap_repository_evidence(
                state,
                lambda record: _rebuild_evidence(record, content_hash="sha256:" + "e" * 64),
            ),
        ),
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
        sampled_kind="relationship",
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
        sampled_kind="relationship",
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
        sampled_kind="relationship",
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
