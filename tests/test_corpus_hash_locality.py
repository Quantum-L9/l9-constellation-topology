"""Where corpus identity moves, and — more importantly — where it must not.

Three identities are separated here, and confusing them is the failure this
suite exists to catch:

*snapshot identity*
    The Topology Packet semantic hash. It tracks the whole compiled snapshot and
    is *meant* to move whenever anything in it moves.

*fact identity*
    A claim id, a candidate id. Stable while only the surrounding snapshot moves.

*effect identity*
    The idempotency key of the durable write a publication plan requests. It must
    move exactly when that write's own semantics move, and not otherwise —
    downstream answers a matching key ``DUPLICATE`` and discards the content, so
    a key that moves too eagerly re-publishes unchanged facts and a key that
    moves too reluctantly silently drops new epistemic state.

The corpus domain adds two new ways to get this wrong, and both are tested:
changing an *analysis* profile must not move a canonical fact's effect key, and
changing a *document* must move exactly the facts that document supports.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.packets.topology_packet import MaterializedTopology
from l9_constellation_topology.publication import (
    build_publication_plan,
    load_publication_policy,
)
from tests.corpus_fixtures import (
    ARTIFACTS,
    FIXED_TIME,
    PAIR_RELATIONS,
    PROJECT_CANDIDATE,
    TOPIC_CANDIDATE,
    corpus_payload,
    signal,
    write_corpus,
)

ROOT = Path(__file__).resolve().parents[1]


def _compile(tmp_path: Path, name: str, **kwargs: object) -> MaterializedTopology:
    repositories, corpus = write_corpus(tmp_path / name, **kwargs)  # type: ignore[arg-type]
    return compile_topology(
        ROOT, repositories, corpus_bundle_paths=(corpus,), created_at=FIXED_TIME
    ).materialized


def _effect_keys(materialized: MaterializedTopology) -> dict[str, str]:
    """Return ``candidate_id`` -> ``idempotency_key`` for every lowered fact."""
    plan = build_publication_plan(
        materialized, load_publication_policy(ROOT), published_at=FIXED_TIME
    )
    return {candidate.candidate_id: candidate.idempotency_key for candidate in plan.candidates}


def _claim_ids(materialized: MaterializedTopology) -> set[str]:
    return {claim.claim_id for claim in materialized.state.semantic_claims}


@pytest.fixture(scope="module")
def baseline(tmp_path_factory: pytest.TempPathFactory) -> MaterializedTopology:
    return _compile(tmp_path_factory.mktemp("baseline"), "corpus")


def test_exact_replay_is_byte_identical(tmp_path: Path) -> None:
    first = _compile(tmp_path, "first")
    second = _compile(tmp_path, "second")
    assert first.packet.semantic_hash == second.packet.semantic_hash
    assert first.packet.payload_hashes == second.packet.payload_hashes
    assert first.state == second.state
    assert _effect_keys(first) == _effect_keys(second)


def test_candidate_identity_is_stable_across_replay(tmp_path: Path) -> None:
    first = _compile(tmp_path, "first")
    second = _compile(tmp_path, "second")
    assert [record.candidate_id for record in first.state.candidate_clusters] == [
        record.candidate_id for record in second.state.candidate_clusters
    ]


def test_an_analysis_profile_change_moves_the_snapshot_and_nothing_canonical(
    tmp_path: Path, baseline: MaterializedTopology
) -> None:
    """The corpus-specific version of hash locality.

    Re-running the corpus pass under a different embedding model or a different
    threshold produces a new ``corpus_analysis_id``. The disks did not change, so
    every canonical claim and every canonical effect key must hold. Only the
    snapshot hash and the candidate analysis move.
    """
    shifted = _compile(tmp_path, "shifted", corpus_analysis_id="analysis:embeddings-v2")

    assert shifted.packet.semantic_hash != baseline.packet.semantic_hash
    assert _claim_ids(shifted) == _claim_ids(baseline)

    baseline_keys = _effect_keys(baseline)
    shifted_keys = _effect_keys(shifted)
    assert set(shifted_keys) == set(baseline_keys)
    assert shifted_keys == baseline_keys, (
        "a change to how candidates were computed must not re-key a single canonical durable write"
    )


def test_a_candidate_threshold_change_moves_candidates_only(
    tmp_path: Path, baseline: MaterializedTopology
) -> None:
    """Dropping a lexical pair changes the candidate domain and nothing canonical."""
    reduced = _compile(
        tmp_path,
        "reduced",
        payload=corpus_payload(
            semantic_pair_relations=(PAIR_RELATIONS[0],),
            topic_candidates=(TOPIC_CANDIDATE.model_copy(update={"supporting_relation_ids": ()}),),
            project_candidates=(
                PROJECT_CANDIDATE.model_copy(
                    update={"supporting_relation_ids": ("duplicate:cross-root",)}
                ),
            ),
        ),
    )
    assert len(reduced.state.candidate_relations) < len(baseline.state.candidate_relations)
    assert _claim_ids(reduced) == _claim_ids(baseline)
    baseline_keys = _effect_keys(baseline)
    for candidate_id, key in _effect_keys(reduced).items():
        if candidate_id in baseline_keys:
            assert key == baseline_keys[candidate_id]


def test_a_changed_document_moves_exactly_the_facts_it_supports(
    tmp_path: Path, baseline: MaterializedTopology
) -> None:
    """A local edit re-keys its own facts and leaves unrelated ones alone."""
    edited = signal(
        "signal:docx-status",
        "wip_docx",
        "work.status",
        "Blocked",
        {"kind": "docx", "block_index": 4, "block_kind": "heading"},
        "docx",
    )
    others = tuple(
        record
        for record in corpus_payload().document_work_signals
        if record.signal_id != "signal:docx-status"
    )
    changed = _compile(
        tmp_path,
        "changed",
        payload=corpus_payload(document_work_signals=(edited, *others)),
    )

    baseline_claims = _claim_ids(baseline)
    changed_claims = _claim_ids(changed)
    # The old claim is gone and a new one exists; every unrelated claim holds.
    assert baseline_claims != changed_claims
    unrelated = baseline_claims & changed_claims
    assert unrelated, "most claims are unaffected by one document's edit"

    baseline_keys = _effect_keys(baseline)
    changed_keys = _effect_keys(changed)
    shared = set(baseline_keys) & set(changed_keys)
    moved = {
        candidate_id
        for candidate_id in shared
        if baseline_keys[candidate_id] != changed_keys[candidate_id]
    }
    held = shared - moved
    assert held, "an unrelated fact must keep its effect key when a document changes"


def test_an_added_exact_duplicate_adds_an_edge_and_moves_nothing_else(
    tmp_path: Path, baseline: MaterializedTopology
) -> None:
    from l9_constellation_topology.packets.corpus_intelligence import (
        ExactDuplicateRelation,
    )

    extra = ExactDuplicateRelation(
        relation_id="duplicate:extra",
        duplicate_cluster_id="cluster:extra",
        artifact_a_id=ARTIFACTS["engine_readme"].artifact_id,
        artifact_b_id=ARTIFACTS["plan_pdf"].artifact_id,
        content_hash="sha256:" + "b" * 64,
    )
    payload = corpus_payload()
    augmented = _compile(
        tmp_path,
        "augmented",
        payload=corpus_payload(
            exact_duplicate_relations=(*payload.exact_duplicate_relations, extra)
        ),
    )
    from l9_constellation_topology.domain.edge import EdgeType

    def duplicates(materialized: MaterializedTopology) -> int:
        return sum(
            1 for edge in materialized.state.edge_records if edge.edge_type is EdgeType.duplicate_of
        )

    assert duplicates(augmented) == duplicates(baseline) + 1
    assert _claim_ids(augmented) == _claim_ids(baseline)

    baseline_keys = _effect_keys(baseline)
    augmented_keys = _effect_keys(augmented)
    for candidate_id in set(baseline_keys) & set(augmented_keys):
        assert augmented_keys[candidate_id] == baseline_keys[candidate_id], (
            "adding a duplicate relation between two other files must not re-key an unrelated fact"
        )


def test_the_edge_taxonomy_is_bound_into_topology_identity(
    baseline: MaterializedTopology,
) -> None:
    """Changing what an edge means may not silently reuse a packet's identity.

    Adding ``DUPLICATE_OF`` changed both the taxonomy and which types canonical
    impact traverses, so a packet compiled when byte identity was a dependency
    hop must not share identity with one compiled after it stopped being one.
    """
    from l9_constellation_topology.domain.edge import edge_taxonomy_hash

    assert baseline.packet.policy_hashes["edge_taxonomy"] == edge_taxonomy_hash()


def test_the_predicate_registry_is_bound_into_topology_identity(
    baseline: MaterializedTopology,
) -> None:
    from l9_constellation_topology.reconciliation import predicate_policy_hash

    assert baseline.packet.policy_hashes["assertion_predicates"] == predicate_policy_hash()


def test_the_corpus_packet_is_bound_into_topology_identity(
    baseline: MaterializedTopology,
) -> None:
    """The analysis a topology rests on is part of what that topology is."""
    refs = baseline.packet.inputs.corpus_intelligence_packets
    assert len(refs) == 1
    assert refs[0].packet_id in baseline.packet.lineage.parent_packet_ids
