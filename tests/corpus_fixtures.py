"""A synthetic corpus that exercises every domain the corpus boundary carries.

Two roots, six document formats, and one of each relationship class the contract
names. Built in memory rather than checked in as bytes, because what is under
test is the *compiler's* treatment of these records — a checked-in fixture would
also be testing that a JSON file on disk had not been edited, and would make
adding a case a two-file change.

The corpus is deliberately awkward in specific ways, and each awkwardness is a
case some part of the pipeline has to get right:

* a DOCX declaring ``WIP`` and a PPTX declaring ``Complete`` about one subject,
  so the cross-format conflict has somewhere to be found;
* a plan and a roadmap claiming one ``work.kind``, so single-valued conflict is
  exercised outside the status predicate;
* an exact duplicate across roots, and another inside a ZIP;
* a near-duplicate that must never become ``DUPLICATE_OF``;
* an ambiguous reference — two files sharing a basename — so resolution has
  something it must refuse to guess at;
* a supersession that resolves exactly, and a dependency that does too.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from l9_constellation_topology.domain.artifact import ArtifactRecord
from l9_constellation_topology.domain.confidence import ConfidenceAssessment
from l9_constellation_topology.domain.repository import RepositoryRecord
from l9_constellation_topology.packets.common import (
    PacketBundleManifest,
    PacketFileEntry,
    PacketValidationRef,
    Producer,
    ProfileRef,
    SourceSnapshot,
)
from l9_constellation_topology.packets.corpus_bundle import (
    build_corpus_intelligence_bundle_artifacts,
    finalize_corpus_intelligence_packet,
)
from l9_constellation_topology.packets.corpus_intelligence import (
    CandidateCluster,
    CorpusAnalysisProfileRef,
    CorpusCoverage,
    CorpusDescriptor,
    CorpusIntelligenceInputs,
    CorpusIntelligencePacket,
    CorpusIntelligencePayload,
    CorpusRootRef,
    DocumentWorkSignal,
    ExactDuplicateRelation,
    PairMethodScore,
    ReadinessEvidence,
    ReasoningCandidateRequest,
    SemanticPairRelation,
)
from l9_constellation_topology.packets.refs import PacketRef
from l9_constellation_topology.packets.repository_model import (
    RepositoryModelPacket,
    RepositoryModelPayload,
    RepositorySubject,
)
from l9_constellation_topology.packets.validation_receipt import (
    ValidationReceipt,
    finalize_validation_receipt,
)
from l9_constellation_topology.packets.validator import repository_model_semantic_view
from l9_constellation_topology.run.evidence import (
    EvidenceRecord,
    EvidenceSourceRef,
    artifact_hash,
    canonical_bytes,
    make_evidence_record,
    semantic_hash,
)

FIXED_TIME = datetime(1970, 1, 1, tzinfo=UTC)

#: The two roots. ``plans`` is a folder of documents; ``engine`` is a repository.
ROOT_PLANS = "root:plans"
ROOT_ENGINE = "root:engine"
REPO_PLANS = "repo:plans"
REPO_ENGINE = "repo:engine"

ANALYSIS_PROFILE = CorpusAnalysisProfileRef(
    profile_id="semantic-fusion/v1",
    profile_version="1.0.0",
    profile_hash="sha256:" + "7" * 64,
)


def _digest(seed: str) -> str:
    """A stable, obviously synthetic content hash."""
    return "sha256:" + (seed * 64)[:64]


def artifact(
    artifact_id: str,
    repository_id: str,
    source_path: str,
    *,
    artifact_type: str = "documentation",
    content_hash: str | None = None,
) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=artifact_id,
        repository_id=repository_id,
        source_path=source_path,
        artifact_type=artifact_type,  # type: ignore[arg-type]
        content_hash=content_hash or _digest(artifact_id[-1]),
        packet_ref=f"packet:{repository_id.replace(':', '-')}",
        confidence=ConfidenceAssessment.direct(),
    )


#: Every artifact the corpus observed, keyed for readability in the tests.
ARTIFACTS: dict[str, ArtifactRecord] = {
    # Root: plans. A folder of documents in six formats.
    "plan_md": artifact("artifact:plan-md", REPO_PLANS, "plans/plan.md"),
    "wip_docx": artifact("artifact:wip-docx", REPO_PLANS, "plans/wip.docx"),
    "roadmap_pptx": artifact("artifact:roadmap-pptx", REPO_PLANS, "plans/roadmap.pptx"),
    "plan_pdf": artifact("artifact:plan-pdf", REPO_PLANS, "plans/plan.pdf"),
    "tracker_xlsx": artifact("artifact:tracker-xlsx", REPO_PLANS, "plans/tracker.xlsx"),
    "proto_ipynb": artifact("artifact:proto-ipynb", REPO_PLANS, "plans/prototype.ipynb"),
    # An archive member, addressed by the producer's virtual path form.
    "zipped_plan": artifact("artifact:zipped-plan", REPO_PLANS, "plans/archive.zip!/inner/plan.md"),
    # Deliberately at exactly `README.md`, the same portable path the engine root
    # uses. A reference to `README.md` therefore matches two observed artifacts,
    # which is the ambiguity resolution must refuse to guess its way out of.
    "readme_plans": artifact("artifact:readme-plans", REPO_PLANS, "README.md"),
    # Root: engine. An ordinary repository.
    "engine_main": artifact(
        "artifact:engine-main", REPO_ENGINE, "engine/main.py", artifact_type="source"
    ),
    "engine_readme": artifact("artifact:engine-readme", REPO_ENGINE, "README.md"),
    # Byte-identical to `plan_md`, in the other root.
    "engine_plan": artifact(
        "artifact:engine-plan", REPO_ENGINE, "docs/plan.md", content_hash=_digest("d")
    ),
    "engine_v1": artifact("artifact:engine-v1", REPO_ENGINE, "docs/spec-v1.md"),
    "engine_v2": artifact("artifact:engine-v2", REPO_ENGINE, "docs/spec-v2.md"),
}

#: `plan_md` and `engine_plan` hold the same bytes, in different roots.
DUPLICATE_DIGEST = _digest("d")
#: `zipped_plan` and `readme_plans` hold the same bytes, one inside an archive.
ARCHIVE_DUPLICATE_DIGEST = _digest("a")


def _repository(repository_id: str, name: str, revision: str) -> RepositoryRecord:
    return RepositoryRecord(
        repository_id=repository_id,
        name=name,
        source_revision=revision,
        primary_role="UNKNOWN",
        packet_ref=f"packet:{repository_id.replace(':', '-')}",
        confidence=ConfidenceAssessment.direct(),
    )


def _observation_evidence(
    subject_id: str, field: str, value: object, *, source_path: str | None, digest: str | None
) -> EvidenceRecord:
    """One producer observation, as a real Repository Model Packet carries it.

    Present because the validator requires every source-authoritative record to
    cite evidence, and it is right to: a repository asserted at ``source``
    authority with nothing behind it is indistinguishable from a guess. A fixture
    that dodged the rule would be testing a pipeline the real one is not.
    """
    return make_evidence_record(
        subject_id=subject_id,
        field=field,
        stage="observe_repository",
        evidence_class="observed",
        source_type="file",
        source_ref=EvidenceSourceRef(source_path=source_path, content_hash=digest),
        value=value,
        confidence=ConfidenceAssessment.direct(),
        producer="l9-meta-injector",
        producer_version="1.0.0",
        created_at=FIXED_TIME,
    )


def repository_model_packet(
    repository_id: str, name: str, revision: str, artifact_keys: tuple[str, ...]
) -> RepositoryModelPacket:
    """Build a Repository Model Packet carrying exactly the named artifacts."""
    repository = _repository(repository_id, name, revision)
    repository_evidence = _observation_evidence(
        repository_id, "repository_id", repository_id, source_path=None, digest=None
    )
    records = []
    evidence = [repository_evidence]
    for key in artifact_keys:
        record = ARTIFACTS[key]
        observed = _observation_evidence(
            record.artifact_id,
            "content_hash",
            record.content_hash,
            source_path=record.source_path,
            digest=record.content_hash,
        )
        evidence.append(observed)
        records.append(record.model_copy(update={"evidence_refs": (observed.evidence_id,)}))
    payload = RepositoryModelPayload(
        repositories=(
            repository.model_copy(
                update={
                    "evidence_refs": (repository_evidence.evidence_id,),
                    "artifact_ids": tuple(item.artifact_id for item in records),
                }
            ),
        ),
        artifacts=tuple(records),
        evidence=tuple(evidence),
        assertions=(),
    )
    packet = RepositoryModelPacket(
        packet_version="1.1.0",
        packet_id=f"packet:{repository_id.replace(':', '-')}",
        subject=RepositorySubject(repository_id=repository_id),
        source_snapshot=SourceSnapshot(revision=revision, semantic_hash=_digest("b")),
        validation=PacketValidationRef(status="passed"),
        producer=Producer(name="l9-meta-injector", version="1.0.0"),
        profile=ProfileRef(id="rmp", version="1.0.0", hash=_digest("c")),
        schema_hash=_digest("e"),
        semantic_hash="sha256:pending",
        payload=payload,
    )
    # Derived, never asserted: the loader recomputes it, so a hand-written value
    # would only ever be a way for the fixture to be wrong.
    return packet.model_copy(
        update={"semantic_hash": semantic_hash(repository_model_semantic_view(packet))}
    )


PLANS_PACKET = repository_model_packet(
    REPO_PLANS,
    "plans",
    "sha:" + "1" * 40,
    (
        "plan_md",
        "wip_docx",
        "roadmap_pptx",
        "plan_pdf",
        "tracker_xlsx",
        "proto_ipynb",
        "zipped_plan",
        "readme_plans",
    ),
)
ENGINE_PACKET = repository_model_packet(
    REPO_ENGINE,
    "engine",
    "sha:" + "2" * 40,
    ("engine_main", "engine_readme", "engine_plan", "engine_v1", "engine_v2"),
)
REPOSITORY_PACKETS = (PLANS_PACKET, ENGINE_PACKET)


def packet_ref(packet: RepositoryModelPacket) -> PacketRef:
    return PacketRef(
        packet_id=packet.packet_id,
        packet_type=packet.packet_type,
        packet_version=packet.packet_version,
        uri=f"packet://{packet.packet_id}",
        semantic_hash=packet.semantic_hash,
        validation_status=packet.validation.status,
        subject_id=packet.subject.repository_id,
        source_revision=packet.source_snapshot.revision,
    )


def signal(
    signal_id: str,
    artifact_key: str,
    predicate: str,
    obj: str,
    locator: dict[str, object],
    document_format: str,
    *,
    subject_id: str = REPO_PLANS,
    authority: str = "source",
    confidence: str = "high",
) -> DocumentWorkSignal:
    record = ARTIFACTS[artifact_key]
    return DocumentWorkSignal(
        signal_id=signal_id,
        artifact_id=record.artifact_id,
        subject_id=subject_id,
        predicate=predicate,
        object=obj,
        source_path=record.source_path,
        locator=locator,  # type: ignore[arg-type]
        source_content_hash=record.content_hash or _digest("f"),
        document_format=document_format,
        evidence_excerpt=f"{predicate}: {obj}",
        extractor_id="work-signals/v1",
        decoder_id=document_format,
        decoder_version="1.0.0",
        evidence_class="declared",
        authority=authority,
        confidence=confidence,
    )


#: One work signal per document format, plus the relations the contract names.
WORK_SIGNALS: tuple[DocumentWorkSignal, ...] = (
    # Markdown: a line span is a truthful coordinate here.
    signal(
        "signal:md-kind",
        "plan_md",
        "work.kind",
        "plan",
        {"kind": "line", "start_line": 1, "end_line": 1},
        "markdown",
    ),
    # DOCX: block index, never a line.
    signal(
        "signal:docx-status",
        "wip_docx",
        "work.status",
        "WIP",
        {"kind": "docx", "block_index": 4, "block_kind": "heading"},
        "docx",
    ),
    # PPTX: slide and shape. Contradicts the DOCX above, on purpose.
    signal(
        "signal:pptx-status",
        "roadmap_pptx",
        "work.status",
        "Complete",
        {"kind": "pptx", "slide_number": 3, "shape_index": 1},
        "pptx",
    ),
    # A second single-valued contradiction, on a different predicate.
    signal(
        "signal:pptx-kind",
        "roadmap_pptx",
        "work.kind",
        "roadmap",
        {"kind": "pptx", "slide_number": 1, "shape_index": 0},
        "pptx",
    ),
    # PDF: page and block.
    signal(
        "signal:pdf-milestone",
        "plan_pdf",
        "work.milestone",
        "beta",
        {"kind": "pdf", "page_number": 2, "block_index": 7},
        "pdf",
    ),
    # XLSX: sheet and cell.
    signal(
        "signal:xlsx-task",
        "tracker_xlsx",
        "work.task.open",
        "wire the executor",
        {"kind": "spreadsheet", "sheet": "Tasks", "cell_or_range": "B7"},
        "xlsx",
    ),
    # IPYNB: cell index and type.
    signal(
        "signal:ipynb-task",
        "proto_ipynb",
        "work.task.completed",
        "spike the parser",
        {"kind": "notebook", "cell_index": 3, "cell_type": "markdown"},
        "ipynb",
    ),
    # An exactly resolvable dependency.
    signal(
        "signal:docx-depends",
        "wip_docx",
        "work.depends_on",
        "engine/main.py",
        {"kind": "docx", "block_index": 9, "block_kind": "list_item"},
        "docx",
    ),
    # An exactly resolvable blocker.
    signal(
        "signal:docx-blocked",
        "wip_docx",
        "work.blocked_by",
        "docs/spec-v1.md",
        {"kind": "docx", "block_index": 11, "block_kind": "list_item"},
        "docx",
    ),
    # A reference to a path no artifact carries. Unresolved, not ambiguous: it
    # still produces an edge, pointing at an explicitly external node.
    signal(
        "signal:docx-references",
        "wip_docx",
        "work.references",
        "plan.md",
        {"kind": "docx", "block_index": 13, "block_kind": "paragraph"},
        "docx",
    ),
    # A reference to a path *two* observed artifacts carry. Ambiguous, and
    # resolution must decline rather than pick one.
    signal(
        "signal:pdf-references",
        "plan_pdf",
        "work.references",
        "README.md",
        {"kind": "pdf", "page_number": 4, "block_index": 2},
        "pdf",
    ),
    # An exactly resolvable supersession, declared from the superseded side.
    signal(
        "signal:md-superseded",
        "plan_md",
        "work.superseded_by",
        "docs/spec-v2.md",
        {"kind": "line", "start_line": 12, "end_line": 12},
        "markdown",
    ),
    # A predicate the registry has no rule for. Preserved, never projected.
    signal(
        "signal:md-unsupported",
        "plan_md",
        "work.vibe",
        "optimistic",
        {"kind": "line", "start_line": 20, "end_line": 20},
        "markdown",
    ),
)

DUPLICATE_RELATIONS: tuple[ExactDuplicateRelation, ...] = (
    # Across roots.
    ExactDuplicateRelation(
        relation_id="duplicate:cross-root",
        duplicate_cluster_id="cluster:plan",
        artifact_a_id=ARTIFACTS["plan_md"].artifact_id,
        artifact_b_id=ARTIFACTS["engine_plan"].artifact_id,
        content_hash=DUPLICATE_DIGEST,
    ),
    # Inside a ZIP.
    ExactDuplicateRelation(
        relation_id="duplicate:in-archive",
        duplicate_cluster_id="cluster:archive",
        artifact_a_id=ARTIFACTS["zipped_plan"].artifact_id,
        artifact_b_id=ARTIFACTS["readme_plans"].artifact_id,
        content_hash=ARCHIVE_DUPLICATE_DIGEST,
    ),
)

#: A near-duplicate and a lexical pair. Neither may become a canonical edge.
PAIR_RELATIONS: tuple[SemanticPairRelation, ...] = (
    SemanticPairRelation(
        relation_id="pair:near-duplicate",
        source_artifact_id=ARTIFACTS["engine_v1"].artifact_id,
        target_artifact_id=ARTIFACTS["engine_v2"].artifact_id,
        methods=("text-near-duplicate/v1",),
        method_scores=(PairMethodScore(method="text-near-duplicate/v1", score=0.94),),
        confidence_class="strong",
        analysis_profile=ANALYSIS_PROFILE,
        upstream_candidate_id="pair:near-duplicate",
    ),
    SemanticPairRelation(
        relation_id="pair:lexical",
        source_artifact_id=ARTIFACTS["plan_md"].artifact_id,
        target_artifact_id=ARTIFACTS["roadmap_pptx"].artifact_id,
        methods=("keyphrase-weighted-overlap/v1",),
        method_scores=(PairMethodScore(method="keyphrase-weighted-overlap/v1", score=0.66),),
        confidence_class="moderate",
        analysis_profile=ANALYSIS_PROFILE,
        upstream_candidate_id="pair:lexical",
    ),
)

TOPIC_CANDIDATE = CandidateCluster(
    candidate_id="candidate:topic",
    candidate_type="TOPIC_CANDIDATE",
    member_artifact_ids=(
        ARTIFACTS["plan_md"].artifact_id,
        ARTIFACTS["roadmap_pptx"].artifact_id,
    ),
    supporting_relation_ids=("pair:lexical",),
    confidence_class="moderate",
    analysis_profile=ANALYSIS_PROFILE,
)

#: Spans both roots and holds the contradictory status declarations.
PROJECT_CANDIDATE = CandidateCluster(
    candidate_id="candidate:project",
    candidate_type="PROJECT_CANDIDATE",
    member_artifact_ids=(
        ARTIFACTS["plan_md"].artifact_id,
        ARTIFACTS["wip_docx"].artifact_id,
        ARTIFACTS["roadmap_pptx"].artifact_id,
        ARTIFACTS["engine_main"].artifact_id,
    ),
    supporting_relation_ids=("pair:lexical", "duplicate:cross-root"),
    confidence_class="strong",
    cross_root=True,
    analysis_profile=ANALYSIS_PROFILE,
)

CONSOLIDATION_CANDIDATE = CandidateCluster(
    candidate_id="candidate:consolidation",
    candidate_type="CONSOLIDATION_CANDIDATE",
    member_artifact_ids=(
        ARTIFACTS["engine_v1"].artifact_id,
        ARTIFACTS["engine_v2"].artifact_id,
    ),
    supporting_relation_ids=("pair:near-duplicate",),
    confidence_class="moderate",
    analysis_profile=ANALYSIS_PROFILE,
)

READINESS = ReadinessEvidence(
    readiness_id="readiness:project",
    subject_id=PROJECT_CANDIDATE.candidate_id,
    profile_id="l9-meta-injector-readiness-evidence",
    profile_version="1.0.0",
    source_artifact_count=9,
    test_artifact_count=4,
    build_manifest_count=1,
    ci_definition_count=1,
    documentation_count=3,
    plan_count=1,
    roadmap_count=1,
    wip_count=1,
    open_task_count=5,
    completed_task_count=2,
    milestone_count=1,
    exact_duplicate_count=2,
    near_duplicate_count=1,
    consolidation_candidate_count=1,
    coverage_gap_count=0,
)

REASONING_REQUESTS: tuple[ReasoningCandidateRequest, ...] = (
    ReasoningCandidateRequest(
        reasoning_candidate_id="upstream:project",
        candidate_id=PROJECT_CANDIDATE.candidate_id,
        recommended_reasoning_type="PROJECT_IDENTITY_ADJUDICATION",
        reason="declared identifiers matched across roots",
        member_artifact_ids=PROJECT_CANDIDATE.member_artifact_ids,
    ),
    ReasoningCandidateRequest(
        reasoning_candidate_id="upstream:topic",
        candidate_id=TOPIC_CANDIDATE.candidate_id,
        recommended_reasoning_type="NONE",
        reason="lexical overlap only",
        member_artifact_ids=TOPIC_CANDIDATE.member_artifact_ids,
    ),
)


def corpus_payload(**overrides: object) -> CorpusIntelligencePayload:
    """The full synthetic payload, with any domain replaceable for one test."""
    fields: dict[str, object] = {
        "document_work_signals": WORK_SIGNALS,
        "exact_duplicate_relations": DUPLICATE_RELATIONS,
        "semantic_pair_relations": PAIR_RELATIONS,
        "topic_candidates": (TOPIC_CANDIDATE,),
        "project_candidates": (PROJECT_CANDIDATE,),
        "consolidation_candidates": (CONSOLIDATION_CANDIDATE,),
        "readiness_evidence": (READINESS,),
        "reasoning_candidates": REASONING_REQUESTS,
    }
    fields.update(overrides)
    return CorpusIntelligencePayload(**fields)  # type: ignore[arg-type]


def corpus_packet(
    payload: CorpusIntelligencePayload | None = None,
    *,
    packets: tuple[RepositoryModelPacket, ...] = REPOSITORY_PACKETS,
    corpus_analysis_id: str = "analysis:baseline",
    corpus_source_snapshot_id: str = "snapshot:baseline",
) -> CorpusIntelligencePacket:
    """Build a finalized corpus intelligence packet over the fixture roots."""
    refs = tuple(packet_ref(packet) for packet in packets)
    roots = tuple(
        CorpusRootRef(
            root_id=ROOT_PLANS if reference.subject_id == REPO_PLANS else ROOT_ENGINE,
            identity_class="declared",
            source_revision=reference.source_revision or "",
            repository_model_packet=reference,
            repository_id=reference.subject_id,
        )
        for reference in refs
    )
    packet = CorpusIntelligencePacket(
        packet_id="packet:pending",
        producer=Producer(name="l9-meta-injector", version="1.0.0"),
        profile=ProfileRef(id="corpus", version="1.0.0", hash=_digest("9")),
        inputs=CorpusIntelligenceInputs(repository_model_packets=refs),
        corpus=CorpusDescriptor(
            corpus_id="corpus:test",
            corpus_source_snapshot_id=corpus_source_snapshot_id,
            corpus_analysis_id=corpus_analysis_id,
            root_refs=roots,
            coverage=CorpusCoverage(
                root_count_requested=len(roots),
                root_count_observed=len(roots),
                root_count_failed=0,
                artifact_count=len(ARTIFACTS),
                archive_count=1,
                archive_member_count=1,
                decoder_eligible_count=8,
                normalized_document_count=8,
                interpreted_artifact_count=7,
                unsupported_format_count=0,
                coverage_gap_count=0,
            ),
        ),
        validation=PacketValidationRef(status="passed"),
        schema_hash=_digest("8"),
        semantic_hash="sha256:pending",
        payload=payload if payload is not None else corpus_payload(),
        created_at=FIXED_TIME,
    )
    return finalize_corpus_intelligence_packet(packet)


def write_repository_bundle(packet: RepositoryModelPacket, destination: Path) -> Path:
    """Commit a Repository Model bundle for a hand-built packet.

    Tests compile through the real loader rather than around it, so a fixture
    packet has to reach disk as a bundle a verifier will accept: a manifest whose
    hashes resolve, and a passed validation receipt naming the packet.
    """
    receipt = finalize_validation_receipt(
        ValidationReceipt(
            receipt_id="receipt:pending",
            subject_packet_id=packet.packet_id,
            subject_semantic_hash=packet.semantic_hash,
            validator=Producer(name="fixture-validator", version="1.0.0"),
            status="passed",
            semantic_hash="sha256:pending",
            created_at=FIXED_TIME,
        )
    )
    published = packet.model_copy(
        update={
            "validation": PacketValidationRef(
                status="passed", receipt_ref="receipts/validation-receipt.json"
            )
        }
    )
    members = {
        "packet.json": canonical_bytes(published) + b"\n",
        "receipts/validation-receipt.json": canonical_bytes(receipt) + b"\n",
    }
    entries = tuple(
        PacketFileEntry(
            path=path,
            media_type="application/json",
            content_hash=artifact_hash(content),
            size_bytes=len(content),
        )
        for path, content in sorted(members.items())
    )
    manifest = PacketBundleManifest(
        packet_id=published.packet_id,
        packet_type=published.packet_type,
        packet_version=published.packet_version,
        semantic_hash=published.semantic_hash,
        artifact_hash=semantic_hash(entries),
        files=entries,
        created_at=FIXED_TIME,
    )
    members["manifest.json"] = canonical_bytes(manifest) + b"\n"
    for path, content in members.items():
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return destination


def write_corpus_bundle(packet: CorpusIntelligencePacket, destination: Path) -> Path:
    """Commit a corpus intelligence bundle through the canonical renderer."""
    for rendered in build_corpus_intelligence_bundle_artifacts(packet, created_at=FIXED_TIME):
        target = destination / rendered.destination_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(rendered.content)
    return destination


def write_corpus(
    root: Path,
    *,
    payload: CorpusIntelligencePayload | None = None,
    packets: tuple[RepositoryModelPacket, ...] = REPOSITORY_PACKETS,
    corpus_analysis_id: str = "analysis:baseline",
    corpus_source_snapshot_id: str = "snapshot:baseline",
) -> tuple[tuple[Path, ...], Path]:
    """Write every fixture bundle under ``root`` and return the compile inputs."""
    repository_paths = tuple(
        write_repository_bundle(packet, root / packet.packet_id.replace(":", "-"))
        for packet in packets
    )
    corpus_path = write_corpus_bundle(
        corpus_packet(
            payload,
            packets=packets,
            corpus_analysis_id=corpus_analysis_id,
            corpus_source_snapshot_id=corpus_source_snapshot_id,
        ),
        root / "corpus",
    )
    return repository_paths, corpus_path
