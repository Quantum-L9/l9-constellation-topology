"""The corpus intelligence packet boundary: what it accepts, and what it refuses.

A packet whose identities do not resolve is refused rather than partially
compiled, and each test below is one way a producer can get that wrong. The
refusals matter more than the acceptances: compiling the resolvable subset of a
broken packet produces a topology that looks complete and silently omits
whatever the producer got wrong, which is the failure this boundary exists to
make impossible.
"""

from __future__ import annotations

import json

import pytest

from l9_constellation_topology.packets.common import PacketFileEntry
from l9_constellation_topology.packets.corpus_bundle import (
    build_corpus_intelligence_bundle_artifacts,
    calculate_corpus_semantic_hash,
    finalize_corpus_intelligence_packet,
    load_corpus_intelligence_bundle,
)
from l9_constellation_topology.packets.corpus_intelligence import (
    CORPUS_PAYLOAD_FIELDS,
    CandidateCluster,
    CorpusIntelligencePayload,
    ExactDuplicateRelation,
    ReadinessEvidence,
    ReasoningCandidateRequest,
    SemanticPairRelation,
)
from l9_constellation_topology.packets.corpus_validator import (
    CorpusIntelligenceValidationError,
    validate_corpus_intelligence_packet,
)
from l9_constellation_topology.packets.loader import PacketLoadError
from l9_constellation_topology.run.evidence import artifact_hash, semantic_hash
from tests.corpus_fixtures import (
    ANALYSIS_PROFILE,
    ARTIFACTS,
    DUPLICATE_DIGEST,
    PROJECT_CANDIDATE,
    REPOSITORY_PACKETS,
    corpus_packet,
    corpus_payload,
    signal,
    write_corpus_bundle,
)


def _validate(payload: CorpusIntelligencePayload) -> None:
    """Validate a payload, with the packet built outside the assertion.

    ``CorpusIntelligenceValidationError`` is a ``ValueError``, and so is every
    payload and packet model validator. Constructing either *inside* a
    ``pytest.raises`` block would let a test pass because the fixture was
    rejected rather than because validation found what it was meant to find —
    which is a test that cannot fail for the reason it was written. So the
    fixture is built first, and only the call under test sits in the block.
    """
    packet = corpus_packet(payload)
    validate_corpus_intelligence_packet(packet, REPOSITORY_PACKETS)


def test_a_well_formed_corpus_packet_validates() -> None:
    _validate(corpus_payload())


def test_every_payload_domain_is_serialized_to_its_own_file() -> None:
    """A domain without a file would be dropped by a bundle round-trip.

    ``reasoning_evidence_pack_refs`` is the one that nearly was: optional to
    populate, and therefore easy to leave off the payload-file list, where it
    would have survived in memory and vanished on read-back.
    """
    packet = corpus_packet(corpus_payload(reasoning_evidence_pack_refs=("pack:1", "pack:2")))
    written = {
        artifact.destination_path for artifact in build_corpus_intelligence_bundle_artifacts(packet)
    }
    for field in CORPUS_PAYLOAD_FIELDS:
        assert f"payload/{field.replace('_', '-')}.json" in written


def test_a_bundle_round_trip_preserves_every_domain(tmp_path) -> None:
    packet = corpus_packet(corpus_payload(reasoning_evidence_pack_refs=("pack:1", "pack:2")))
    reloaded = load_corpus_intelligence_bundle(
        write_corpus_bundle(packet, tmp_path / "corpus")
    ).packet
    assert reloaded.packet_id == packet.packet_id
    assert reloaded.payload == packet.payload
    assert calculate_corpus_semantic_hash(reloaded) == packet.semantic_hash


def test_a_tampered_payload_file_fails_the_hash_check(tmp_path) -> None:
    root = write_corpus_bundle(corpus_packet(), tmp_path / "corpus")
    target = root / "payload" / "topic-candidates.json"
    target.write_bytes(target.read_bytes().replace(b"TOPIC_CANDIDATE", b"tampered"))
    with pytest.raises(PacketLoadError):
        load_corpus_intelligence_bundle(root)


def test_identity_excludes_the_payload_and_the_wall_clock() -> None:
    """Two packets over one analysis are one packet, whatever the clock said."""
    first = corpus_packet()
    second = corpus_packet()
    assert first.packet_id == second.packet_id
    assert first.semantic_hash == second.semantic_hash


def test_a_changed_payload_moves_packet_identity() -> None:
    baseline = corpus_packet()
    reduced = corpus_packet(corpus_payload(topic_candidates=()))
    assert reduced.semantic_hash != baseline.semantic_hash


def test_a_corpus_packet_referencing_a_missing_repository_model_fails() -> None:
    packet = corpus_packet()
    with pytest.raises(CorpusIntelligenceValidationError) as caught:
        validate_corpus_intelligence_packet(packet, (REPOSITORY_PACKETS[0],))
    assert any("did not resolve" in error for error in caught.value.errors)


def test_a_document_signal_naming_an_unobserved_artifact_fails() -> None:
    stray = signal(
        "signal:stray",
        "plan_md",
        "work.status",
        "WIP",
        {"kind": "line", "start_line": 1, "end_line": 1},
        "markdown",
    ).model_copy(update={"artifact_id": "artifact:never-observed"})
    payload = corpus_payload(document_work_signals=(stray,))
    with pytest.raises(CorpusIntelligenceValidationError) as caught:
        _validate(payload)
    assert any("no input packet carries" in error for error in caught.value.errors)


def test_a_duplicate_relation_with_a_missing_endpoint_fails() -> None:
    stray = ExactDuplicateRelation(
        relation_id="duplicate:stray",
        duplicate_cluster_id="cluster:stray",
        artifact_a_id=ARTIFACTS["plan_md"].artifact_id,
        artifact_b_id="artifact:never-observed",
        content_hash=DUPLICATE_DIGEST,
    )
    payload = corpus_payload(exact_duplicate_relations=(stray,))
    with pytest.raises(CorpusIntelligenceValidationError) as caught:
        _validate(payload)
    assert any("no input packet carries" in error for error in caught.value.errors)


def test_a_duplicate_cluster_carrying_two_hashes_fails() -> None:
    """Byte equality admits exactly one hash per cluster.

    Two hashes under one cluster id means the producer's clustering and its
    hashes disagree, and there is no reading under which both are true.
    """
    relations = (
        ExactDuplicateRelation(
            relation_id="duplicate:a",
            duplicate_cluster_id="cluster:split",
            artifact_a_id=ARTIFACTS["plan_md"].artifact_id,
            artifact_b_id=ARTIFACTS["engine_plan"].artifact_id,
            content_hash="sha256:" + "1" * 64,
        ),
        ExactDuplicateRelation(
            relation_id="duplicate:b",
            duplicate_cluster_id="cluster:split",
            artifact_a_id=ARTIFACTS["plan_md"].artifact_id,
            artifact_b_id=ARTIFACTS["engine_v1"].artifact_id,
            content_hash="sha256:" + "2" * 64,
        ),
    )
    payload = corpus_payload(exact_duplicate_relations=relations)
    with pytest.raises(CorpusIntelligenceValidationError) as caught:
        _validate(payload)
    assert any("more than one content hash" in error for error in caught.value.errors)


def test_a_duplicate_relation_needs_two_distinct_artifacts() -> None:
    with pytest.raises(ValueError, match="needs two artifacts"):
        ExactDuplicateRelation(
            relation_id="duplicate:self",
            duplicate_cluster_id="cluster:self",
            artifact_a_id=ARTIFACTS["plan_md"].artifact_id,
            artifact_b_id=ARTIFACTS["plan_md"].artifact_id,
            content_hash=DUPLICATE_DIGEST,
        )


def test_a_pair_relation_with_a_missing_endpoint_fails() -> None:
    stray = SemanticPairRelation(
        relation_id="pair:stray",
        source_artifact_id=ARTIFACTS["plan_md"].artifact_id,
        target_artifact_id="artifact:never-observed",
        confidence_class="weak",
        analysis_profile=ANALYSIS_PROFILE,
    )
    payload = corpus_payload(semantic_pair_relations=(stray,))
    with pytest.raises(CorpusIntelligenceValidationError) as caught:
        _validate(payload)
    assert any("no input packet carries" in error for error in caught.value.errors)


def test_a_candidate_naming_a_missing_member_fails() -> None:
    stray = PROJECT_CANDIDATE.model_copy(
        update={"member_artifact_ids": ("artifact:never-observed",)}
    )
    payload = corpus_payload(project_candidates=(stray,))
    with pytest.raises(CorpusIntelligenceValidationError) as caught:
        _validate(payload)
    assert any("no input packet carries" in error for error in caught.value.errors)


def test_a_candidate_citing_an_absent_supporting_relation_fails() -> None:
    stray = PROJECT_CANDIDATE.model_copy(
        update={"supporting_relation_ids": ("pair:never-emitted",)}
    )
    payload = corpus_payload(project_candidates=(stray,))
    with pytest.raises(CorpusIntelligenceValidationError) as caught:
        _validate(payload)
    assert any("this packet does not carry" in error for error in caught.value.errors)


def test_a_candidate_filed_under_the_wrong_domain_fails() -> None:
    """The field and the type tag must agree.

    A consolidation candidate sitting in ``topic_candidates`` would be enriched,
    reported, and routed as a topic candidate while declaring itself something
    else, and every downstream reading of it would be wrong in a way no single
    record makes visible.
    """
    misfiled = PROJECT_CANDIDATE.model_copy(update={"candidate_type": "TOPIC_CANDIDATE"})
    with pytest.raises(ValueError, match="project_candidates carries"):
        corpus_payload(project_candidates=(misfiled,))


def test_a_candidate_with_no_members_is_refused() -> None:
    with pytest.raises(ValueError, match="names no members"):
        CandidateCluster(
            candidate_id="candidate:empty",
            candidate_type="TOPIC_CANDIDATE",
            member_artifact_ids=(),
            confidence_class="weak",
            analysis_profile=ANALYSIS_PROFILE,
        )


def test_readiness_for_an_unknown_subject_fails() -> None:
    stray = ReadinessEvidence(
        readiness_id="readiness:stray",
        subject_id="candidate:never-emitted",
        profile_id="readiness",
        profile_version="1.0.0",
    )
    payload = corpus_payload(readiness_evidence=(stray,))
    with pytest.raises(CorpusIntelligenceValidationError) as caught:
        _validate(payload)
    assert any("neither a candidate" in error for error in caught.value.errors)


def test_a_reasoning_candidate_naming_an_absent_candidate_fails() -> None:
    stray = ReasoningCandidateRequest(
        reasoning_candidate_id="upstream:stray",
        candidate_id="candidate:never-emitted",
        recommended_reasoning_type="CONSOLIDATION_ANALYSIS",
    )
    payload = corpus_payload(reasoning_candidates=(stray,))
    with pytest.raises(CorpusIntelligenceValidationError) as caught:
        _validate(payload)
    assert any("this packet does not carry" in error for error in caught.value.errors)


def test_a_reasoning_candidate_citing_an_undeclared_pack_fails() -> None:
    stray = ReasoningCandidateRequest(
        reasoning_candidate_id="upstream:project",
        candidate_id=PROJECT_CANDIDATE.candidate_id,
        recommended_reasoning_type="PROJECT_IDENTITY_ADJUDICATION",
        evidence_pack_ref="pack:never-declared",
    )
    payload = corpus_payload(reasoning_candidates=(stray,), reasoning_evidence_pack_refs=())
    with pytest.raises(CorpusIntelligenceValidationError) as caught:
        _validate(payload)
    assert any("does not declare" in error for error in caught.value.errors)


def test_a_packet_with_no_materialized_payload_is_refused() -> None:
    packet = corpus_packet().model_copy(update={"payload": None})
    with pytest.raises(CorpusIntelligenceValidationError) as caught:
        validate_corpus_intelligence_packet(packet, REPOSITORY_PACKETS)
    assert any("no materialized payload" in error for error in caught.value.errors)


# ── bundle rendering and loading refusals ───────────────────────────────────


def test_a_bundle_cannot_be_rendered_from_an_unfinalized_packet() -> None:
    """Payload hashes are derived, so a caller cannot declare ones that disagree.

    ``finalize_corpus_intelligence_packet`` computes them from the payload it is
    handed. Rendering a packet whose declared hashes do not match its contents
    would publish a bundle that fails its own verification on read-back.
    """
    packet = corpus_packet()
    drifted = packet.model_copy(update={"payload": corpus_payload(topic_candidates=())})
    with pytest.raises(ValueError, match="do not match the carried payload"):
        build_corpus_intelligence_bundle_artifacts(drifted)


def test_a_packet_without_a_payload_cannot_be_finalized_or_rendered() -> None:
    empty = corpus_packet().model_copy(update={"payload": None})
    with pytest.raises(ValueError, match="without a payload"):
        finalize_corpus_intelligence_packet(empty)
    with pytest.raises(ValueError, match="without a payload"):
        build_corpus_intelligence_bundle_artifacts(empty)


def test_loading_a_file_rather_than_a_bundle_directory_is_refused(tmp_path) -> None:
    root = write_corpus_bundle(corpus_packet(), tmp_path / "corpus")
    with pytest.raises(PacketLoadError, match="must be a packet bundle directory"):
        load_corpus_intelligence_bundle(root / "packet.json")


def test_a_manifest_naming_a_different_packet_is_refused(tmp_path) -> None:
    """The manifest and the packet must agree about which packet this is."""
    root = write_corpus_bundle(corpus_packet(), tmp_path / "corpus")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["packet_id"] = "packet:someone-else"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PacketLoadError):
        load_corpus_intelligence_bundle(root)


def test_a_packet_declaring_no_ref_for_a_domain_is_refused(tmp_path) -> None:
    """An absent payload ref is a defect, not an empty domain.

    Unlike the Topology Packet — where a 1.0.0 bundle legitimately declares no
    ref for a domain 1.1.0 added — every corpus domain is mandatory to carry, so
    a missing ref means the bundle is incomplete rather than older.
    """
    packet = corpus_packet()
    root = write_corpus_bundle(packet, tmp_path / "corpus")
    packet_path = root / "packet.json"
    document = json.loads(packet_path.read_text(encoding="utf-8"))
    del document["payload_refs"]["topic_candidates"]
    packet_path.write_text(json.dumps(document), encoding="utf-8")
    # The manifest now disagrees with the edited bytes, which is caught first;
    # rewrite it so the missing-ref path is what actually fails.
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    content = packet_path.read_bytes()
    for entry in manifest["files"]:
        if entry["path"] == "packet.json":
            entry["content_hash"] = artifact_hash(content)
            entry["size_bytes"] = len(content)
    manifest["artifact_hash"] = semantic_hash(
        tuple(PacketFileEntry.model_validate(entry) for entry in manifest["files"])
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PacketLoadError, match="missing payload ref"):
        load_corpus_intelligence_bundle(root)
