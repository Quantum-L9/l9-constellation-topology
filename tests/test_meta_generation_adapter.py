"""The Meta generation compatibility adapter.

The generation is synthesized here to the producer's exact on-disk schemas
rather than checked in, because a checked-in copy would drift from the producer
silently and these tests would keep passing against a shape nobody emits.

Two properties matter more than the mapping itself: the generation is never
written to, and nothing the generation cannot express is invented. The second is
why the adapter's honest limitation — binary-document work signals it cannot
locate truthfully — is asserted here as behaviour rather than documented as a
caveat.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.domain.edge import EdgeType
from l9_constellation_topology.packets.adapters.meta_generation import (
    UNADAPTABLE_NO_STRUCTURED_LOCATOR,
    MetaGenerationError,
    _document_formats,
    _Generation,
    adapt_meta_generation,
    resolve_generation_root,
)
from l9_constellation_topology.packets.corpus_validator import (
    validate_corpus_intelligence_packet,
)
from l9_constellation_topology.run.evidence import canonical_json, sha256_text
from tests.corpus_fixtures import (
    ARTIFACTS,
    FIXED_TIME,
    REPO_ENGINE,
    REPO_PLANS,
    REPOSITORY_PACKETS,
    write_corpus_bundle,
    write_repository_bundle,
)

ROOT = Path(__file__).resolve().parents[1]

#: Which decoder the generation records for each fixture artifact. The split is
#: the point: markdown carries real lines, docx and pptx do not.
#: Decoded format per artifact, as the producer's document index records it.
FORMATS = {
    "artifact:plan-md": "markdown",
    "artifact:wip-docx": "docx",
    "artifact:roadmap-pptx": "pptx",
    "artifact:plan-pdf": "pdf",
    "artifact:tracker-xlsx": "xlsx",
    "artifact:proto-ipynb": "ipynb",
}


def decoder_id_for(artifact_id: str) -> str:
    """The producer names decoders, not formats, in ``decoder_id``.

    Written out here because a fixture that puts ``"docx"`` in ``decoder_id``
    lets a consumer compare the two fields interchangeably and pass. The
    producer writes ``l9.docx-decoder`` there and ``docx`` in ``format``, and a
    reader that confuses them fails on every binary document in a real
    generation while every test still goes green.
    """
    return f"l9.{FORMATS.get(artifact_id, 'text')}-decoder"


def _tree_digest(root: Path) -> str:
    """A digest over every file under ``root``, for proving nothing was written."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_generation(root: Path, *, with_current: bool = True) -> Path:
    """Write a generation using the producer's real document shapes."""
    generation = root / "generations" / "g1" if with_current else root
    generation.mkdir(parents=True, exist_ok=True)

    roots = []
    documents = []
    for packet in REPOSITORY_PACKETS:
        name = packet.subject.repository_id.split(":")[1]
        write_repository_bundle(packet, generation / "roots" / name)
        roots.append(
            {
                "root_id": f"root:{name}",
                "root_key": name,
                "source_kind": "declared",
                "source_revision": packet.source_snapshot.revision,
                "rmp_packet_id": packet.packet_id,
                "rmp_semantic_hash": packet.semantic_hash,
                "bundle_ref": f"roots/{name}",
                "observation_status": "observed",
                "failure_reason": None,
            }
        )
        assert packet.payload is not None
        for record in packet.payload.artifacts:
            documents.append(
                {
                    "artifact_id": record.artifact_id,
                    "root_id": f"root:{name}",
                    "corpus_path": f"root:{name}::{record.source_path}",
                    "root_relative_path": record.source_path,
                    "content_hash": record.content_hash,
                    "normalized_document_id": f"nd:{record.artifact_id}",
                    "format": FORMATS.get(record.artifact_id, "text"),
                    "decoder_id": decoder_id_for(record.artifact_id),
                    "decoder_version": "1.0.0",
                    "decoded": True,
                    "undecoded_reason": None,
                    "byte_length": 100,
                    "token_count": 20,
                    "normalized_content_hash": "sha256:" + "9" * 64,
                    "is_archive_member": "!/" in record.source_path,
                    "archive_ancestry": [],
                }
            )

    _write(
        generation / "corpus-snapshot.json",
        {
            "schema": "l9.corpus-snapshot/v1",
            "corpus_id": "corpus:archive",
            "corpus_source_snapshot_id": "snap:abc",
            "analysis": {
                "corpus_analysis_id": "analysis:xyz",
                "corpus_profile": "l9-meta-injector-corpus-intelligence",
                "interpretation_profile": "interp/v1",
            },
            "corpus_status": "complete",
            "missing_root_ids": [],
            "roots": roots,
            "artifacts": [],
            "archives": [],
            "counts": {
                "root_count_requested": 2,
                "root_count_observed": 2,
                "root_count_failed": 0,
                "root_count": 2,
                "artifact_count": len(documents),
                "archive_count": 1,
                "archive_member_count": 1,
                "total_bytes": 1000,
            },
        },
    )
    _write(
        generation / "corpus-coverage.json",
        {
            "schema": "l9.corpus-coverage/v1",
            "corpus_source_snapshot_id": "snap:abc",
            "corpus_analysis_id": "analysis:xyz",
            "corpus": {
                "root_count_requested": 2,
                "root_count_observed": 2,
                "root_count_failed": 0,
                "total_physical_artifacts": len(documents),
                "archive_count": 1,
                "archive_member_count": 1,
            },
            "hashing": {"unhashed_count": 0},
            "documents": {
                "decoder_eligible_count": len(documents),
                "normalized_document_count": len(documents),
                "unsupported_format_count": 0,
            },
            "semantics": {"interpreted_artifact_count": 6},
        },
    )
    # The sampled report, written the way the producer writes it: complete
    # counts beside a listing the producer caps. Present in the fixture because
    # its absence let a consumer read the wrong key and see None forever, which
    # is indistinguishable from a report that agrees with the payload.
    _write(
        generation / "document-signals.json",
        {
            "schema": "l9.document-signals/v1",
            "corpus_source_snapshot_id": "snap:abc",
            "corpus_analysis_id": "analysis:xyz",
            "block_signals": {
                "profile_id": "l9.interpretation",
                "profile_version": "1.0.0",
                "profile_hash": "sha256:" + "4" * 64,
                "extractor_id": "l9.extractor",
                "document_count": 2,
                "signal_count": 191,
                "by_format": [
                    {
                        "format": "docx",
                        "documents_with_signals": 1,
                        "signal_count": 191,
                        "listed_signal_count": 50,
                        "omitted_signal_count": 141,
                        "predicates": [],
                        "records": [],
                    },
                    {
                        "format": "markdown",
                        "documents_with_signals": 1,
                        "signal_count": 3,
                        "listed_signal_count": 3,
                        "omitted_signal_count": 0,
                        "predicates": [],
                        "records": [],
                    },
                ],
            },
        },
    )
    _write(
        generation / "document-index.json",
        {
            "schema": "l9.document-index/v1",
            "corpus_source_snapshot_id": "snap:abc",
            "corpus_analysis_id": "analysis:xyz",
            "documents": documents,
        },
    )
    _write(
        generation / "corpus-candidates.json",
        {
            "schema": "l9.corpus-candidates/v1",
            "relations": [
                {
                    "relation_id": "rel:1",
                    "type": "DUPLICATE_OF",
                    "source_artifact_id": ARTIFACTS["plan_md"].artifact_id,
                    "target_artifact_id": ARTIFACTS["engine_plan"].artifact_id,
                    "duplicate_cluster_id": "dc:1",
                    "content_hash": "sha256:" + "e" * 64,
                    "symmetric": True,
                }
            ],
        },
    )
    profile = {
        "fusion_profile_id": "semantic-fusion/v1",
        "fusion_profile_version": "1.0.0",
        "fusion_profile_hash": "sha256:" + "7" * 64,
    }
    _write(
        generation / "semantic-relations.json",
        {
            "schema": "l9.semantic-relations/v1",
            "analysis_profile": profile,
            "pairs": [
                {
                    "pair_id": "pair:1",
                    "artifact_a_id": ARTIFACTS["plan_md"].artifact_id,
                    "artifact_b_id": ARTIFACTS["roadmap_pptx"].artifact_id,
                    "signals": [
                        {
                            "kind": "keyphrase_overlap",
                            "method": "keyphrase-weighted-overlap/v1",
                            "score": 0.71,
                        }
                    ],
                    "evidence_refs": [],
                }
            ],
            "classifications": [{"pair_id": "pair:1", "confidence_class": "moderate"}],
        },
    )
    for filename, candidate_type in (
        ("topic-candidates.json", "TOPIC_CANDIDATE"),
        ("project-candidates.json", "PROJECT_CANDIDATE"),
        ("consolidation-candidates.json", "CONSOLIDATION_CANDIDATE"),
    ):
        _write(
            generation / filename,
            {
                "schema": f"l9.{filename[:-5]}/v1",
                "analysis_profile": profile,
                "candidates": [
                    {
                        "candidate_id": f"{candidate_type.lower()}:1",
                        "candidate_type": candidate_type,
                        "member_artifact_ids": [
                            ARTIFACTS["plan_md"].artifact_id,
                            ARTIFACTS["roadmap_pptx"].artifact_id,
                        ],
                        "supporting_pair_ids": ["pair:1"],
                        "confidence_class": "strong",
                        "cross_archive": False,
                    }
                ],
            },
        )
    _write(
        generation / "readiness-evidence.json",
        {
            "schema": "l9.readiness-evidence/v1",
            "profile": {
                "profile_id": "l9-meta-injector-readiness-evidence",
                "profile_version": "1.0.0",
            },
            "bodies_of_work": [
                {
                    "body_id": "body:1",
                    "origin": "project_candidate",
                    "origin_ref": "project_candidate:1",
                    "member_ids": [ARTIFACTS["plan_md"].artifact_id],
                    "member_count": 1,
                    "root_ids": ["root:plans"],
                    "metrics": {
                        "implementation": {"source_artifact_count": 9, "manifest_count": 2},
                        "validation": {
                            "structural_test_artifact_count": 4,
                            "ci_definition_count": 1,
                        },
                        "delivery": {"deployment_definition_count": 1},
                        "knowledge": {"documentation_count": 3, "plan_count": 1},
                        "work_state": {"wip_count": 1, "open_task_count": 5},
                        "reuse_and_duplication": {"exact_duplicate_artifact_count": 2},
                        "uncertainty": {"coverage_gap_count": 0},
                    },
                }
            ],
        },
    )
    (generation / "reasoning-candidates.jsonl").write_text(
        json.dumps(
            {
                "reasoning_candidate_id": "rc:1",
                "candidate_id": "project_candidate:1",
                "reasoning_type": "PROJECT_IDENTITY_ADJUDICATION",
                "reason": "declared identifiers matched",
                "member_artifact_ids": [ARTIFACTS["plan_md"].artifact_id],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (generation / "reasoning-evidence-packs.jsonl").write_text(
        json.dumps({"evidence_pack_id": "pack:1", "reasoning_candidate_id": "rc:1"}) + "\n",
        encoding="utf-8",
    )
    if with_current:
        _write(
            root / "CURRENT.json",
            {
                "schema": "l9.corpus-current/v1",
                "generation_id": "gen:1",
                "generation_ref": "generations/g1",
                "committed_at": "1970-01-01T00:00:00Z",
                "files": [],
            },
        )
    return root


@pytest.fixture
def mutable_generation(generation: Path, tmp_path: Path) -> Path:
    """A private copy, for tests that edit the generation to make it wrong.

    The shared generation is module-scoped, so a test that stamps a field on it
    changes what every later test reads. Isolating the mutations keeps each
    refusal a statement about the input it was given rather than about the order
    the suite happened to run in.
    """
    target = tmp_path / "generation"
    shutil.copytree(generation, target)
    return target


@pytest.fixture(scope="module")
def generation(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_generation(tmp_path_factory.mktemp("meta-generation"))


def test_the_pointer_selects_the_generation_to_read(generation: Path) -> None:
    """A directory ``CURRENT.json`` does not name is being written or superseded."""
    assert resolve_generation_root(generation) == (generation / "generations" / "g1").resolve()


def test_a_generation_directory_without_a_pointer_is_read_directly(
    tmp_path: Path,
) -> None:
    root = build_generation(tmp_path / "flat", with_current=False)
    assert resolve_generation_root(root) == root.resolve()


def test_adaptation_never_writes_to_the_generation(generation: Path) -> None:
    """The rule the whole module is built around, checked over the bytes."""
    before = _tree_digest(generation)
    adapt_meta_generation(generation)
    assert _tree_digest(generation) == before


def test_the_adapted_packet_is_referentially_sound(generation: Path) -> None:
    report = adapt_meta_generation(generation)
    validate_corpus_intelligence_packet(report.packet, REPOSITORY_PACKETS)


def test_the_adapter_binds_the_exact_per_root_packets(generation: Path) -> None:
    report = adapt_meta_generation(generation)
    bound = {root.repository_model_packet.packet_id for root in report.packet.corpus.root_refs}
    assert bound == {packet.packet_id for packet in REPOSITORY_PACKETS}
    for root in report.packet.corpus.root_refs:
        expected = next(
            packet
            for packet in REPOSITORY_PACKETS
            if packet.packet_id == root.repository_model_packet.packet_id
        )
        assert root.repository_model_packet.semantic_hash == expected.semantic_hash


def test_a_snapshot_naming_a_hash_its_bundle_does_not_carry_fails(
    tmp_path: Path,
) -> None:
    """A generation whose snapshot has drifted from its own bundles is refused."""
    root = build_generation(tmp_path / "drifted")
    snapshot_path = root / "generations" / "g1" / "corpus-snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["roots"][0]["rmp_semantic_hash"] = "sha256:" + "0" * 64
    _write(snapshot_path, snapshot)
    with pytest.raises(MetaGenerationError, match="semantic hash"):
        adapt_meta_generation(root)


def test_every_domain_the_generation_carries_is_adapted(generation: Path) -> None:
    payload = adapt_meta_generation(generation).packet.payload
    assert payload is not None
    assert len(payload.exact_duplicate_relations) == 1
    assert len(payload.semantic_pair_relations) == 1
    assert len(payload.topic_candidates) == 1
    assert len(payload.project_candidates) == 1
    assert len(payload.consolidation_candidates) == 1
    assert len(payload.readiness_evidence) == 1
    assert len(payload.reasoning_candidates) == 1
    assert payload.reasoning_evidence_pack_refs == ("pack:1",)


def test_readiness_is_carried_as_counts_and_attached_to_its_candidate(
    generation: Path,
) -> None:
    payload = adapt_meta_generation(generation).packet.payload
    assert payload is not None
    readiness = payload.readiness_evidence[0]
    assert readiness.subject_id == "project_candidate:1"
    assert readiness.source_artifact_count == 9
    assert readiness.test_artifact_count == 4
    assert readiness.ci_definition_count == 1


def test_a_reasoning_row_naming_an_absent_candidate_is_dropped_with_a_diagnostic(
    tmp_path: Path,
) -> None:
    """A generation defect is reported as one, not as a topology error.

    Carrying it through would fail the packet's own integrity check, where it
    would read as though topology had produced something unresolvable.
    """
    root = build_generation(tmp_path / "stray")
    path = root / "generations" / "g1" / "reasoning-candidates.jsonl"
    path.write_text(
        path.read_text(encoding="utf-8")
        + json.dumps(
            {
                "reasoning_candidate_id": "rc:stray",
                "candidate_id": "candidate:never-written",
                "reasoning_type": "NONE",
                "member_artifact_ids": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = adapt_meta_generation(root)
    assert report.packet.payload is not None
    assert {
        request.reasoning_candidate_id for request in report.packet.payload.reasoning_candidates
    } == {"rc:1"}
    assert any("rc:stray" in message for message in report.diagnostics)
    validate_corpus_intelligence_packet(report.packet, REPOSITORY_PACKETS)


def test_a_missing_optional_generation_file_is_reported_not_fatal(
    tmp_path: Path,
) -> None:
    root = build_generation(tmp_path / "partial")
    (root / "generations" / "g1" / "topic-candidates.json").unlink()
    report = adapt_meta_generation(root)
    assert "topic-candidates.json" in report.missing_files
    assert report.packet.payload is not None
    assert report.packet.payload.topic_candidates == ()


def test_a_generation_with_no_snapshot_is_refused(tmp_path: Path) -> None:
    root = build_generation(tmp_path / "headless")
    (root / "generations" / "g1" / "corpus-snapshot.json").unlink()
    with pytest.raises(MetaGenerationError, match=r"corpus-snapshot\.json"):
        adapt_meta_generation(root)


def test_a_generation_where_no_root_observed_is_refused(tmp_path: Path) -> None:
    root = build_generation(tmp_path / "unobserved")
    snapshot_path = root / "generations" / "g1" / "corpus-snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    for entry in snapshot["roots"]:
        entry["observation_status"] = "failed"
    _write(snapshot_path, snapshot)
    with pytest.raises(MetaGenerationError, match="observed successfully"):
        adapt_meta_generation(root)


def test_the_adapter_is_deterministic(generation: Path) -> None:
    first = adapt_meta_generation(generation).packet
    second = adapt_meta_generation(generation).packet
    assert first.packet_id == second.packet_id
    assert first.payload == second.payload


def test_an_adapted_generation_compiles_to_a_topology_packet(
    generation: Path, tmp_path: Path
) -> None:
    """The whole point: generation in, Topology Packet 1.1.0 out."""
    report = adapt_meta_generation(generation)
    corpus = write_corpus_bundle(report.packet, tmp_path / "adapted-corpus")
    repositories = tuple(
        (report.generation_root / "roots" / repository.split(":")[1])
        for repository in (REPO_PLANS, REPO_ENGINE)
    )
    result = compile_topology(
        ROOT, repositories, corpus_bundle_paths=(corpus,), created_at=FIXED_TIME
    )
    state = result.materialized.state
    assert result.validation_receipt.status == "passed"
    assert result.materialized.packet.packet_version == "1.1.0"
    assert len(state.corpus_records) == 1
    assert len(state.root_records) == 2
    assert len(state.candidate_clusters) == 3
    assert any(edge.edge_type is EdgeType.duplicate_of for edge in state.edge_records)


# ── the adapter's honest limitation ─────────────────────────────────────────


def _work_assertion(artifact_id: str, source_path: str, predicate: str) -> dict[str, object]:
    return {
        "assertion_id": f"assertion:{artifact_id}:{predicate}",
        "subject_id": REPO_PLANS,
        "predicate": predicate,
        "object": "WIP",
        "source_path": source_path,
        "source_range": {"start_line": 7, "end_line": 7},
        "evidence_excerpt": "Status: WIP",
        "source_content_hash": "sha256:" + "1" * 64,
        "extractor_id": "work/v1",
        "evidence_class": "declared",
        "authority": "source",
        "confidence": "high",
    }


def _generation_with_work_assertions(root: Path) -> Path:
    """Rewrite the plans root's packet to carry two work assertions.

    One is read from Markdown, where a line span is a real coordinate. The other
    is read from a `.docx`, where the producer's line span indexes joined block
    text and names nothing in the source document.
    """
    from l9_constellation_topology.packets.repository_model import (
        RepositoryModelAssertion,
    )
    from l9_constellation_topology.run.evidence import semantic_hash
    from tests.corpus_fixtures import PLANS_PACKET, repository_model_semantic_view

    assert PLANS_PACKET.payload is not None
    assertions = (
        RepositoryModelAssertion.model_validate(
            _work_assertion(ARTIFACTS["plan_md"].artifact_id, "plans/plan.md", "work.kind")
        ),
        RepositoryModelAssertion.model_validate(
            _work_assertion(ARTIFACTS["wip_docx"].artifact_id, "plans/wip.docx", "work.status")
        ),
    )
    packet = PLANS_PACKET.model_copy(
        update={
            "payload": PLANS_PACKET.payload.model_copy(update={"assertions": assertions}),
            "semantic_hash": "sha256:pending",
        }
    )
    packet = packet.model_copy(
        update={"semantic_hash": semantic_hash(repository_model_semantic_view(packet))}
    )

    build_generation(root)
    generation = root / "generations" / "g1"
    write_repository_bundle(packet, generation / "roots" / "plans")
    snapshot_path = generation / "corpus-snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    for entry in snapshot["roots"]:
        if entry["root_id"] == "root:plans":
            entry["rmp_packet_id"] = packet.packet_id
            entry["rmp_semantic_hash"] = packet.semantic_hash
    _write(snapshot_path, snapshot)
    return root


def test_a_line_bearing_work_signal_is_adapted_with_a_line_locator(
    tmp_path: Path,
) -> None:
    root = _generation_with_work_assertions(tmp_path / "work-signals")
    report = adapt_meta_generation(root)
    assert report.packet.payload is not None
    signals = report.packet.payload.document_work_signals
    assert len(signals) == 1
    assert signals[0].predicate == "work.kind"
    assert signals[0].document_format == "markdown"
    assert signals[0].locator.kind == "line"
    assert signals[0].locator.start_line == 7  # type: ignore[union-attr]


def test_a_binary_document_work_signal_is_declined_and_reported(
    tmp_path: Path,
) -> None:
    """The adapter's main limitation, asserted as behaviour.

    Mapping line n to block n-1 would hold only if no decoded block contains a
    newline, which the generation gives no way to check. A locator that is right
    most of the time cannot be told from a correct one afterwards, so the signal
    is declined and the decline is reported.
    """
    root = _generation_with_work_assertions(tmp_path / "unadaptable")
    report = adapt_meta_generation(root)
    assert len(report.unadaptable_signals) == 1
    declined = report.unadaptable_signals[0]
    assert declined.document_format == "docx"
    assert declined.predicate == "work.status"
    assert declined.reason == UNADAPTABLE_NO_STRUCTURED_LOCATOR
    assert report.unadaptable_by_format == {"docx": 1}
    assert any("not adapted" in message for message in report.diagnostics)
    # And nothing was invented in its place.
    assert report.packet.payload is not None
    assert all(
        record.document_format != "docx" for record in report.packet.payload.document_work_signals
    )


def test_the_decoded_format_is_read_from_format_not_from_the_decoder_id(
    generation: Path,
) -> None:
    """A decoder name is not a file type.

    The producer records ``decoder_id: l9.docx-decoder`` and ``format: docx``.
    Reading the first as the second compares a tool against a file type, which
    matches for nothing: in a real generation every binary-document signal was
    refused with "declares format 'docx' and the document index records
    'l9.docx-decoder'", while the whole suite stayed green because the fixture
    had put a format string in the decoder field.

    Asserted on the parsed index rather than through the adapter, because the
    point is which field is authoritative, not what any one signal did with it.
    """
    root = resolve_generation_root(generation)
    index = json.loads((root / "document-index.json").read_text(encoding="utf-8"))
    formats = _document_formats(_Generation(root=root, documents={"document-index.json": index}))
    assert formats["artifact:wip-docx"] == "docx"
    assert all(not value.startswith("l9.") for value in formats.values())


def test_a_generation_recording_only_a_decoder_id_still_resolves_a_format(
    tmp_path: Path,
) -> None:
    """Older generations wrote one string in both places; they still read."""
    index = {
        "documents": [
            {"artifact_id": "artifact:legacy", "decoder_id": "markdown"},
        ]
    }
    formats = _document_formats(
        _Generation(root=tmp_path, documents={"document-index.json": index})
    )
    assert formats == {"artifact:legacy": "markdown"}


def test_the_sampled_report_is_counted_but_never_read_as_the_payload(
    generation: Path,
) -> None:
    """The report's listing is capped; the payload is not.

    53 listed against 194 complete is the whole reason `document-signals.json`
    cannot be the machine contract. A consumer adapting its `records` arrays
    would ingest the listed count and then report perfect conservation against
    it — every number self-consistent, 141 signals gone, and nothing in the
    output saying so.

    The count is read so the two documents can be compared. It is asserted here
    because reading it from the wrong key returns None, and a cross-check that
    never fires looks exactly like one that always passes.
    """
    report = adapt_meta_generation(generation)
    assert report.sampled_report_listed_count == 53
    complete = 191 + 3
    assert report.sampled_report_listed_count < complete


def test_a_report_claiming_more_signals_than_the_payload_is_refused(
    mutable_generation: Path,
) -> None:
    """A sample cannot exceed what it samples.

    If it does, one of the two documents is wrong about how much the corpus
    found, and which one is not knowable from either document alone — so the
    generation is refused rather than adapted under whichever number is smaller.
    """
    root = resolve_generation_root(mutable_generation)
    _write_payload_with_one_signal(root)
    _declare_root_identity(root)
    document = json.loads((root / "document-signals.json").read_text(encoding="utf-8"))
    document["block_signals"]["by_format"][0]["listed_signal_count"] = 999
    (root / "document-signals.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    with pytest.raises(MetaGenerationError, match="cannot exceed the payload"):
        adapt_meta_generation(mutable_generation)


def _write_payload_with_one_signal(root: Path) -> None:
    """Turn a legacy-shaped generation into a current-mode one.

    Built here rather than copied from a real generation so the manifest is
    computed from the payload rather than pasted beside it: a fixture whose
    hashes were transcribed would keep passing if the reader stopped checking
    them.
    """
    record = ARTIFACTS["plan_md"]
    signal = {
        "signal_id": "sig:one",
        "artifact_id": "vsrc:one",
        "rmp_artifact_id": record.artifact_id,
        "source_path": record.source_path,
        "format": "markdown",
        "raw_content_hash": record.content_hash,
        "normalized_document_id": f"nd:{record.artifact_id}",
        "decoder_id": "l9.text-decoder",
        "decoder_version": "1.0.0",
        "block_id": "block:1",
        "block_kind": "paragraph",
        "structured_locator": {"kind": "line_span", "line_start": 1, "line_end": 2},
        "predicate": "work.status",
        "object": "wip",
        "bounded_excerpt": "Status: WIP",
        "evidence_class": "declared",
        "authority": "source",
        "confidence": "high",
        "extractor_id": "l9.extractor",
        "extractor_profile_version": "1.0.0",
    }
    payload = canonical_json(signal) + "\n"
    manifest = {
        "schema": "l9.document-work-signals-manifest/v1",
        "corpus_source_snapshot_id": "snap:abc",
        "corpus_analysis_id": "analysis:xyz",
        "profile_id": "l9.interpretation",
        "profile_version": "1.0.0",
        "profile_hash": "sha256:" + "4" * 64,
        "payload_file": "document-work-signals.jsonl",
        "record_count": 1,
        "document_count": 1,
        "by_format": [{"format": "markdown", "document_count": 1, "signal_count": 1}],
        "by_predicate": [{"predicate": "work.status", "signal_count": 1}],
        "payload_byte_length": len(payload.encode("utf-8")),
        "payload_artifact_hash": sha256_text(payload),
        "payload_semantic_hash": sha256_text(
            canonical_json({"schema": "l9.document-work-signals/v1", "records": [signal]})
        ),
    }
    (root / "document-work-signals.jsonl").write_text(payload, encoding="utf-8")
    _write(root / "document-work-signals.manifest.json", manifest)

    # Keep the report consistent with the payload it samples. A generation whose
    # two documents disagree is refused, which is correct but is a different
    # refusal than the one a caller of this helper is usually testing.
    document = json.loads((root / "document-signals.json").read_text(encoding="utf-8"))
    document["block_signals"]["signal_count"] = 1
    document["block_signals"]["by_format"] = [
        {
            "format": "markdown",
            "documents_with_signals": 1,
            "signal_count": 1,
            "listed_signal_count": 1,
            "omitted_signal_count": 0,
            "predicates": [],
            "records": [],
        }
    ]
    _write(root / "document-signals.json", document)


def _declare_root_identity(root: Path, identity_class: str = "declared") -> None:
    """Stamp what a current-mode generation is required to state."""
    snapshot = json.loads((root / "corpus-snapshot.json").read_text(encoding="utf-8"))
    for entry in snapshot["roots"]:
        entry["root_identity_class"] = identity_class
    _write(root / "corpus-snapshot.json", snapshot)


def test_a_current_generation_without_root_identity_class_is_refused(
    mutable_generation: Path,
) -> None:
    """The producer states it; this compiler does not get to decide it.

    `source_kind` says what sort of thing a root is. `root_identity_class` says
    whether its identity was declared or inferred. Deriving the second from the
    first published inferred roots carrying a declared root's authority, and
    nothing downstream could tell.
    """
    root = resolve_generation_root(mutable_generation)
    _write_payload_with_one_signal(root)
    with pytest.raises(MetaGenerationError, match="carries no root_identity_class"):
        adapt_meta_generation(mutable_generation)


def test_root_identity_class_is_read_rather_than_derived_from_source_kind(
    mutable_generation: Path,
) -> None:
    """A root the producer calls declared stays declared, whatever its kind."""
    root = resolve_generation_root(mutable_generation)
    _write_payload_with_one_signal(root)
    _declare_root_identity(root, "declared")
    report = adapt_meta_generation(mutable_generation)
    assert dict(report.root_identity_class_counts) == {"declared": 2}
    assert all(ref.identity_class == "declared" for ref in report.packet.corpus.root_refs)

    _declare_root_identity(root, "inferred")
    report = adapt_meta_generation(mutable_generation)
    assert dict(report.root_identity_class_counts) == {"inferred": 2}


def test_an_invalid_root_identity_class_is_refused(mutable_generation: Path) -> None:
    root = resolve_generation_root(mutable_generation)
    _write_payload_with_one_signal(root)
    _declare_root_identity(root, "probably-declared")
    with pytest.raises(MetaGenerationError, match="neither 'declared' nor 'inferred'"):
        adapt_meta_generation(mutable_generation)
