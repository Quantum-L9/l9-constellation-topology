"""Adapt a current l9-meta-injector corpus generation into a Corpus Intelligence Packet.

Compatibility ingress, and nothing more. The canonical input to this compiler is
an ``l9.corpus-intelligence`` bundle; the producer does not emit one yet, and its
corpus generation is nonetheless a real, validated output that topology needs to
be testable against. This module reads that generation and produces the canonical
packet, so the compiler's API stays the packet and the raw file layout never
becomes it.

Three rules follow from "compatibility ingress":

**The generation is read, never written.** No file under the generation
directory is opened for writing, moved, or removed, and the packet is emitted
through ``OutputSink`` to a separate destination.

**No source tree is rescanned.** Everything comes from the generation and from
the per-root Repository Model bundles it points at. Re-reading the original
disks would make this a second observer, and two observers of one corpus that
disagree is the failure the packet boundary exists to prevent.

**Nothing is invented.** Where the generation does not carry something the
canonical packet wants, the adapter says so and drops the record rather than
filling it in.

The last rule has one consequence worth stating plainly, because it is the
adapter's main limitation rather than a detail. The current generation records
work signals only as repository-model assertions, which carry a line span. For
Markdown, text, CSV, HTML, and notebooks that span is a real coordinate and
becomes a line locator. For Word, PDF, PowerPoint, and spreadsheets it is not: the
producer joins a document's decoded blocks with newlines and interprets the
result, so "line 7" indexes a derived string and names nothing in the source
document. Those signals are therefore **not adapted**, and are reported by count
and reason in ``MetaAdaptationReport.unadaptable_signals``.

The tempting fix — map line *n* to block *n-1* — is available and wrong. It holds
only if no decoded block text contains a newline, which the generation gives no
way to check, and a locator that is right most of the time is worse than an
absent one: it cannot be distinguished from a correct one afterwards. Closing the
gap properly means the producer emitting per-signal structured locators, which is
the same change that would let it emit ``l9.corpus-intelligence`` directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from l9_constellation_topology.packets.common import (
    PacketValidationRef,
    Producer,
    ProfileRef,
)
from l9_constellation_topology.packets.corpus_bundle import (
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
from l9_constellation_topology.packets.loader import (
    PacketLoadError,
    RepositoryModelBundle,
    load_repository_model_bundle,
)
from l9_constellation_topology.packets.refs import PacketRef
from l9_constellation_topology.packets.repository_model import RepositoryModelAssertion

from .errors import MetaGenerationError
from .meta_work_signals import (
    DOCUMENT_WORK_SIGNALS_FILE,
    DOCUMENT_WORK_SIGNALS_MANIFEST_FILE,
    WorkSignalPayload,
    load_work_signal_payload,
    translate_locator,
)

#: The pointer a published generation writes, naming which generation to read.
CURRENT_FILE = "CURRENT.json"

#: Generation files the adapter consumes when present.
SNAPSHOT_FILE = "corpus-snapshot.json"
COVERAGE_FILE = "corpus-coverage.json"
INDEX_FILE = "corpus-index.json"
CANDIDATES_FILE = "corpus-candidates.json"
DOCUMENT_INDEX_FILE = "document-index.json"
DOCUMENT_SIGNALS_FILE = "document-signals.json"
SEMANTIC_RELATIONS_FILE = "semantic-relations.json"
TOPIC_CANDIDATES_FILE = "topic-candidates.json"
PROJECT_CANDIDATES_FILE = "project-candidates.json"
CONSOLIDATION_CANDIDATES_FILE = "consolidation-candidates.json"
READINESS_FILE = "readiness-evidence.json"
REASONING_CANDIDATES_FILE = "reasoning-candidates.jsonl"
REASONING_PACKS_FILE = "reasoning-evidence-packs.jsonl"

#: Predicates the producer classes as work intelligence. Mirrors
#: ``CORPUS_WORK_PREDICATES`` in the producer; an assertion outside this set is a
#: repository-model assertion and reaches topology through the RMP, not here.
WORK_PREDICATES: frozenset[str] = frozenset(
    {
        "document.heading",
        "document.title",
        "work.blocked_by",
        "work.depends_on",
        "work.kind",
        "work.milestone",
        "work.references",
        "work.status",
        "work.superseded_by",
        "work.supersedes",
        "work.task.completed",
        "work.task.open",
    }
)

#: Formats whose decoded text has lines an operator can open the file and find.
LINE_BEARING_FORMATS: frozenset[str] = frozenset({"text", "markdown", "csv", "html", "ipynb"})

#: Reason recorded for a work signal this generation cannot locate truthfully.
UNADAPTABLE_NO_STRUCTURED_LOCATOR = (
    "the generation records this signal only as a line span into the producer's "
    "joined block text, which is not a coordinate in the source document; adapting "
    "it would require inventing a structured locator"
)

#: Adapter identity, recorded as the producer of the emitted packet so a consumer
#: can tell an adapted packet from one the producer emitted directly.
ADAPTER_NAME = "l9-constellation-topology/meta-generation-adapter"
ADAPTER_VERSION = "1.1.0"

#: The generation carries the complete, manifested work-signal payload.
MODE_CURRENT_COMPLETE = "current_complete"

#: The generation predates that payload. Work signals are reconstructed from
#: line-bearing repository-model assertions, and binary-document signals are
#: reported as unadaptable rather than given an invented coordinate.
MODE_LEGACY_LINE_ASSERTIONS = "legacy_line_assertions"

#: Re-exported so callers keep importing the error from the adapter they call.
__all__ = [
    "ADAPTER_VERSION",
    "MODE_CURRENT_COMPLETE",
    "MODE_LEGACY_LINE_ASSERTIONS",
    "MetaAdaptationReport",
    "MetaGenerationError",
    "UnadaptableSignal",
    "adapt_meta_generation",
    "detect_adaptation_mode",
    "resolve_generation_root",
]


@dataclass(frozen=True)
class UnadaptableSignal:
    """A work signal the generation carries but the packet cannot honestly hold."""

    assertion_id: str
    artifact_id: str
    predicate: str
    document_format: str
    reason: str


@dataclass(frozen=True)
class MetaAdaptationReport:
    """What the adaptation produced, and what it declined to produce.

    ``unadaptable_signals`` is the field to read. Everything else is a count of
    things that worked; that one is the list of things the current generation
    cannot express, and an adapter that reported only its successes would make
    the gap invisible.
    """

    packet: CorpusIntelligencePacket
    generation_root: Path
    root_bundles: tuple[RepositoryModelBundle, ...]
    adapted_signal_count: int = 0
    unadaptable_signals: tuple[UnadaptableSignal, ...] = ()
    missing_files: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    #: Which contract this generation was read under.
    adaptation_mode: str = MODE_LEGACY_LINE_ASSERTIONS
    #: What the producer's manifest declared, and what parsing actually yielded.
    #: Equal in a sound current-mode adaptation; both zero in legacy mode, where
    #: there is no manifest to declare anything.
    manifest_record_count: int = 0
    parsed_signal_count: int = 0
    #: Identity of the producer revision behind the payload, as the generation
    #: states it. Recorded rather than derived so a report can be traced back to
    #: the exact analysis that produced it.
    producer_revision: str = ""
    #: How many signals the *sampled* report lists, when it is present. Carried
    #: only so the two documents can be compared; never a source of signals.
    sampled_report_listed_count: int | None = None
    adapted_by_format: tuple[tuple[str, int], ...] = ()
    adapted_by_predicate: tuple[tuple[str, int], ...] = ()
    root_identity_class_counts: tuple[tuple[str, int], ...] = ()

    @property
    def unadaptable_signal_count(self) -> int:
        return len(self.unadaptable_signals)

    @property
    def unadaptable_by_format(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for signal in self.unadaptable_signals:
            counts[signal.document_format] = counts.get(signal.document_format, 0) + 1
        return dict(sorted(counts.items()))


@dataclass
class _Generation:
    """Every generation file that was present, already parsed."""

    root: Path
    documents: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)

    def get(self, name: str) -> Any:
        return self.documents.get(name)

    def require(self, name: str) -> Any:
        value = self.documents.get(name)
        if value is None:
            raise MetaGenerationError(
                f"Meta generation at {self.root} is missing required file {name}"
            )
        return value


def resolve_generation_root(path: Path) -> Path:
    """Return the directory holding the generation's documents.

    A published output root carries ``CURRENT.json`` naming the generation to
    read. Following it rather than globbing the ``generations/`` directory is the
    point of the pointer: a generation directory that ``CURRENT.json`` does not
    name is either being written or has been superseded, and reading one would
    mix two runs' outputs.
    """
    root = path.resolve()
    if not root.is_dir():
        raise MetaGenerationError(f"Meta generation path is not a directory: {root}")
    pointer = root / CURRENT_FILE
    if not pointer.is_file():
        return root
    try:
        current = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MetaGenerationError(f"cannot read {pointer}: {exc}") from exc
    reference = current.get("generation_ref")
    if not isinstance(reference, str) or not reference:
        raise MetaGenerationError(f"{pointer} does not name a generation_ref")
    resolved = (root / reference).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise MetaGenerationError(f"generation_ref escapes the output root: {reference}") from exc
    if not resolved.is_dir():
        raise MetaGenerationError(f"generation_ref names no directory: {reference}")
    return resolved


def detect_adaptation_mode(root: Path) -> str:
    """Decide which contract this generation is read under.

    Presence of *either* half of the complete payload commits the generation to
    current mode. A generation carrying a manifest with no payload, or a payload
    with no manifest, is refused rather than quietly demoted to legacy: falling
    back would read an unverifiable subset of the signals and report success,
    which is the exact failure the manifest exists to prevent.
    """
    has_payload = (root / DOCUMENT_WORK_SIGNALS_FILE).is_file()
    has_manifest = (root / DOCUMENT_WORK_SIGNALS_MANIFEST_FILE).is_file()
    if has_payload or has_manifest:
        return MODE_CURRENT_COMPLETE
    return MODE_LEGACY_LINE_ASSERTIONS


def _read_generation(root: Path) -> _Generation:
    generation = _Generation(root=root)
    for name in (
        SNAPSHOT_FILE,
        COVERAGE_FILE,
        INDEX_FILE,
        CANDIDATES_FILE,
        DOCUMENT_INDEX_FILE,
        DOCUMENT_SIGNALS_FILE,
        SEMANTIC_RELATIONS_FILE,
        TOPIC_CANDIDATES_FILE,
        PROJECT_CANDIDATES_FILE,
        CONSOLIDATION_CANDIDATES_FILE,
        READINESS_FILE,
    ):
        path = root / name
        if not path.is_file():
            generation.missing.append(name)
            continue
        try:
            generation.documents[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MetaGenerationError(f"cannot read {path}: {exc}") from exc
    for name in (REASONING_CANDIDATES_FILE, REASONING_PACKS_FILE):
        path = root / name
        if not path.is_file():
            generation.missing.append(name)
            continue
        rows: list[Any] = []
        # The line number is tracked outside the loop so a decode failure can name
        # the offending line: a JSONL file that fails to parse at line 4,000 is a
        # very different report from "this file did not parse".
        number = 0
        try:
            for number, line in enumerate(  # noqa: B007
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if line.strip():
                    rows.append(json.loads(line))
        except (OSError, json.JSONDecodeError) as exc:
            raise MetaGenerationError(f"cannot read {path} line {number}: {exc}") from exc
        generation.documents[name] = rows
    return generation


def _root_identity_class(
    entry: dict[str, Any], root_id: Any, *, mode: str
) -> Literal["declared", "inferred"]:
    """Return what the producer said the root's identity is.

    ``root_identity_class`` is the producer's own answer to "was this root's
    identity declared, or did we infer it?". ``source_kind`` answers a different
    question — what sort of thing the root is — and reading one as the other was
    wrong in a way no downstream consumer could detect: an inferred root would
    have been published carrying a declared root's authority.

    A current-mode generation that omits the field fails closed. Defaulting it
    would reintroduce exactly the guess this function exists to remove.
    """
    declared = entry.get("root_identity_class")
    if declared == "declared":
        return "declared"
    if declared == "inferred":
        return "inferred"
    if declared is not None:
        raise MetaGenerationError(
            f"root {root_id!r} declares root_identity_class {declared!r}, which is "
            "neither 'declared' nor 'inferred'"
        )
    if mode == MODE_CURRENT_COMPLETE:
        raise MetaGenerationError(
            f"root {root_id!r} carries no root_identity_class; a generation emitting "
            "the complete work-signal payload is expected to state it, and inferring "
            "it here would be a guess wearing the producer's authority"
        )
    # A generation predating the field cannot be asked. The lower of the two
    # classes is the honest reading: 'inferred' claims less.
    return "inferred"


def _root_ref(
    entry: dict[str, Any], generation: _Generation, *, mode: str
) -> tuple[CorpusRootRef, RepositoryModelBundle]:
    """Bind one observed root to the exact bundle it produced.

    The bundle is *loaded*, not trusted: the snapshot's recorded packet id and
    semantic hash are checked against what the bundle actually carries, so a
    generation whose snapshot has drifted from its own bundles fails here rather
    than producing a packet that binds a hash nothing holds.
    """
    root_id = entry.get("root_id")
    reference = entry.get("bundle_ref")
    if not isinstance(reference, str) or not reference:
        raise MetaGenerationError(f"observed root {root_id!r} names no bundle_ref")
    bundle_path = (generation.root / reference).resolve()
    try:
        bundle_path.relative_to(generation.root)
    except ValueError as exc:
        raise MetaGenerationError(f"bundle_ref escapes the generation root: {reference}") from exc
    try:
        bundle = load_repository_model_bundle(bundle_path)
    except PacketLoadError as exc:
        raise MetaGenerationError(f"root {root_id!r} bundle did not load: {exc}") from exc

    packet = bundle.packet
    declared_id = entry.get("rmp_packet_id")
    if declared_id and declared_id != packet.packet_id:
        raise MetaGenerationError(
            f"root {root_id!r} snapshot names packet {declared_id}, "
            f"but its bundle carries {packet.packet_id}"
        )
    declared_hash = entry.get("rmp_semantic_hash")
    if declared_hash and declared_hash != packet.semantic_hash:
        raise MetaGenerationError(
            f"root {root_id!r} snapshot names semantic hash {declared_hash}, "
            f"but its bundle carries {packet.semantic_hash}"
        )
    return (
        CorpusRootRef(
            root_id=str(root_id),
            identity_class=_root_identity_class(entry, root_id, mode=mode),
            source_revision=str(entry.get("source_revision") or ""),
            repository_model_packet=PacketRef(
                packet_id=packet.packet_id,
                packet_type=packet.packet_type,
                packet_version=packet.packet_version,
                uri=f"packet://{packet.packet_id}",
                semantic_hash=packet.semantic_hash,
                artifact_hash=packet.artifact_hash,
                validation_status=packet.validation.status,
                subject_id=packet.subject.repository_id,
                source_revision=packet.source_snapshot.revision,
            ),
            repository_id=packet.subject.repository_id,
        ),
        bundle,
    )


def _load_root_bundles(
    generation: _Generation, *, mode: str
) -> tuple[tuple[CorpusRootRef, ...], tuple[RepositoryModelBundle, ...]]:
    """Bind every observed root to the exact bundle it produced."""
    snapshot = generation.require(SNAPSHOT_FILE)
    roots = snapshot.get("roots")
    if not isinstance(roots, list) or not roots:
        raise MetaGenerationError("corpus snapshot declares no roots")

    refs: list[CorpusRootRef] = []
    bundles: list[RepositoryModelBundle] = []
    for entry in roots:
        # A root that failed or was missing produced no packet. Recording it as a
        # corpus root would bind a reference with nothing behind it.
        if entry.get("observation_status") != "observed":
            continue
        reference, bundle = _root_ref(entry, generation, mode=mode)
        refs.append(reference)
        bundles.append(bundle)
    if not refs:
        raise MetaGenerationError("no root in this generation observed successfully")
    return tuple(refs), tuple(bundles)


def _coverage(generation: _Generation) -> CorpusCoverage:
    coverage = generation.get(COVERAGE_FILE) or {}
    scope = coverage.get("corpus", {})
    documents = coverage.get("documents", {})
    semantics = coverage.get("semantics", {})
    snapshot_counts = (generation.require(SNAPSHOT_FILE)).get("counts", {})

    def count(*candidates: Any, default: int = 0) -> int:
        for value in candidates:
            if isinstance(value, int):
                return max(0, value)
        return default

    return CorpusCoverage(
        root_count_requested=count(
            scope.get("root_count_requested"), snapshot_counts.get("root_count_requested")
        ),
        root_count_observed=count(
            scope.get("root_count_observed"), snapshot_counts.get("root_count_observed")
        ),
        root_count_failed=count(
            scope.get("root_count_failed"), snapshot_counts.get("root_count_failed")
        ),
        artifact_count=count(
            snapshot_counts.get("artifact_count"),
            scope.get("total_physical_artifacts"),
        ),
        archive_count=count(scope.get("archive_count"), snapshot_counts.get("archive_count")),
        archive_member_count=count(
            scope.get("archive_member_count"), snapshot_counts.get("archive_member_count")
        ),
        decoder_eligible_count=count(documents.get("decoder_eligible_count")),
        normalized_document_count=count(documents.get("normalized_document_count")),
        interpreted_artifact_count=count(semantics.get("interpreted_artifact_count")),
        unsupported_format_count=count(documents.get("unsupported_format_count")),
        coverage_gap_count=count(
            (coverage.get("hashing") or {}).get("unhashed_count"),
        ),
    )


def _document_formats(generation: _Generation) -> dict[str, str]:
    """Return ``artifact_id`` -> decoded format, from the document index.

    ``format`` is the field that holds a format. ``decoder_id`` names the
    decoder that produced it — ``l9.docx-decoder`` rather than ``docx`` — and
    reading one as the other compares a tool against a file type. Older
    generations that carry only the decoder id fall back to it, since for those
    the two were written as the same string.
    """
    index = generation.get(DOCUMENT_INDEX_FILE) or {}
    formats: dict[str, str] = {}
    for entry in index.get("documents", ()):
        artifact_id = entry.get("artifact_id")
        if not isinstance(artifact_id, str):
            continue
        declared = entry.get("format")
        if not isinstance(declared, str) or not declared:
            declared = entry.get("decoder_id")
        if isinstance(declared, str) and declared:
            formats[artifact_id] = declared
    return formats


def _normalized_document_ids(generation: _Generation) -> frozenset[str]:
    """Every decoding the document index recorded."""
    index = generation.get(DOCUMENT_INDEX_FILE) or {}
    return frozenset(
        entry["normalized_document_id"]
        for entry in index.get("documents", ())
        if isinstance(entry.get("normalized_document_id"), str)
    )


def _artifact_paths(generation: _Generation) -> dict[str, str]:
    index = generation.get(DOCUMENT_INDEX_FILE) or {}
    paths: dict[str, str] = {}
    for entry in index.get("documents", ()):
        artifact_id = entry.get("artifact_id")
        path = entry.get("root_relative_path")
        if isinstance(artifact_id, str) and isinstance(path, str):
            paths[artifact_id] = path
    return paths


def _corpus_to_rmp_ids(
    generation: _Generation,
    root_refs: tuple[CorpusRootRef, ...],
    bundles: tuple[RepositoryModelBundle, ...],
) -> dict[str, str]:
    """Map the corpus's artifact identities onto the packet domain's.

    The producer works in two identity domains. Its work-signal payload carries
    both ids per record, but the duplicate, pair and candidate documents name
    only the corpus one — so every identity in those domains has to be
    translated before it can resolve against a Repository Model Packet.

    The snapshot is what makes that possible: it states each artifact's
    ``virtual_source_id`` beside the root and root-relative path it was observed
    at, and a root's bundle addresses the same file by that path. An id whose
    path the bundle does not carry is left untranslated, so the packet boundary
    refuses it rather than this function inventing a binding.
    """
    by_root: dict[str, dict[str, str]] = {}
    for reference, bundle in zip(root_refs, bundles, strict=True):
        payload = bundle.packet.payload
        if payload is None:
            continue
        by_root[reference.root_id] = {
            record.source_path: record.artifact_id for record in payload.artifacts
        }

    snapshot = generation.require(SNAPSHOT_FILE)
    translated: dict[str, str] = {}
    for entry in snapshot.get("artifacts", ()):
        corpus_id = entry.get("virtual_source_id")
        root_id = entry.get("root_id")
        relative = entry.get("root_relative_path")
        if not (isinstance(corpus_id, str) and isinstance(root_id, str)):
            continue
        if not isinstance(relative, str):
            continue
        resolved = by_root.get(root_id, {}).get(relative)
        if resolved is not None:
            translated[corpus_id] = resolved
    return translated


def _translate(identity: Any, mapping: dict[str, str]) -> str:
    """Return the packet-domain identity, or the original when unmapped."""
    text = str(identity)
    return mapping.get(text, text)


def _artifact_index(
    bundles: tuple[RepositoryModelBundle, ...],
) -> dict[str, tuple[str, str]]:
    """Return ``artifact_id`` -> (content hash, portable path) over every input.

    An id appearing in two packets is dropped rather than resolved to one of
    them: an ambiguous identity is not evidence, and picking a side here would
    bind a claim to whichever bundle happened to load first.
    """
    index: dict[str, tuple[str, str]] = {}
    duplicated: set[str] = set()
    for bundle in bundles:
        payload = bundle.packet.payload
        if payload is None:
            continue
        for record in payload.artifacts:
            if record.artifact_id in index:
                duplicated.add(record.artifact_id)
                continue
            index[record.artifact_id] = (record.content_hash, record.source_path)
    for artifact_id in duplicated:
        index.pop(artifact_id, None)
    return index


def _resolve_record_artifact(
    record: dict[str, Any], index: dict[str, tuple[str, str]], context: str
) -> tuple[str, str, str]:
    """Bind one record to the artifact it claims, or refuse it.

    Identity comes from ``rmp_artifact_id`` rather than ``artifact_id``. The
    producer emits both because it works in two identity domains — the corpus
    addresses an artifact within the corpus, a Repository Model Packet addresses
    it within its root's bundle — and this compiler resolves in the second.
    """
    rmp_artifact_id = record.get("rmp_artifact_id")
    if not isinstance(rmp_artifact_id, str) or not rmp_artifact_id:
        raise MetaGenerationError(f"{context}: carries no rmp_artifact_id")
    resolved = index.get(rmp_artifact_id)
    if resolved is None:
        raise MetaGenerationError(
            f"{context}: names artifact {rmp_artifact_id!r}, which no input Repository "
            "Model Packet carries unambiguously"
        )
    content_hash, portable_path = resolved

    declared_hash = record.get("raw_content_hash")
    if declared_hash is not None and declared_hash != content_hash:
        raise MetaGenerationError(
            f"{context}: cites content hash {declared_hash!r} and the artifact carries "
            f"{content_hash!r}; the claim is bound to bytes the corpus did not observe"
        )

    source_path = record.get("source_path")
    if not isinstance(source_path, str) or not source_path:
        raise MetaGenerationError(f"{context}: carries no source_path")
    if source_path != portable_path:
        raise MetaGenerationError(
            f"{context}: cites path {source_path!r} and the artifact is at {portable_path!r}"
        )
    return rmp_artifact_id, content_hash, source_path


def _record_format(record: dict[str, Any], formats: dict[str, str], context: str) -> str:
    document_format = record.get("format")
    if not isinstance(document_format, str) or not document_format:
        raise MetaGenerationError(f"{context}: carries no format")
    indexed = formats.get(str(record.get("artifact_id") or ""))
    if indexed is not None and indexed != document_format:
        raise MetaGenerationError(
            f"{context}: declares format {document_format!r} and the document index "
            f"records {indexed!r}"
        )
    return document_format


def _adapt_record(
    record: dict[str, Any],
    index: dict[str, tuple[str, str]],
    formats: dict[str, str],
    decodings: frozenset[str],
) -> DocumentWorkSignal:
    """Translate one verified payload record into a work signal."""
    signal_id = str(record.get("signal_id"))
    context = f"work signal {signal_id}"
    normalized_document_id = _optional_text(record, "normalized_document_id")
    if normalized_document_id is not None and normalized_document_id not in decodings:
        raise MetaGenerationError(
            f"{context}: cites decoding {normalized_document_id!r}, which the document "
            "index does not record"
        )
    rmp_artifact_id, content_hash, source_path = _resolve_record_artifact(record, index, context)
    document_format = _record_format(record, formats, context)
    block_kind = record.get("block_kind")
    block_kind_text = block_kind if isinstance(block_kind, str) else ""
    locator = translate_locator(
        record.get("structured_locator"),
        document_format=document_format,
        block_kind=block_kind_text,
        context=context,
    )
    return DocumentWorkSignal(
        signal_id=signal_id,
        artifact_id=rmp_artifact_id,
        # The producer's signal is artifact-scoped. Naming the artifact as the
        # subject is a schema translation, not an inference about what the claim
        # is about.
        subject_id=rmp_artifact_id,
        predicate=_required_text(record, "predicate", context),
        object=str(record.get("object") or ""),
        source_path=source_path,
        locator=locator,  # type: ignore[arg-type]
        source_content_hash=content_hash,
        document_format=document_format,
        evidence_excerpt=str(record.get("bounded_excerpt") or ""),
        extractor_id=_required_text(record, "extractor_id", context),
        decoder_id=_required_text(record, "decoder_id", context),
        decoder_version=_required_text(record, "decoder_version", context),
        evidence_class=_evidence_class(record, context),
        authority=_required_text(record, "authority", context),
        confidence=_required_text(record, "confidence", context),
        corpus_artifact_id=str(record.get("artifact_id") or ""),
        normalized_document_id=normalized_document_id,
        block_id=str(record.get("block_id") or ""),
        block_kind=block_kind_text,
        extractor_profile_version=str(record.get("extractor_profile_version") or ""),
    )


def _current_work_signals(
    payload: WorkSignalPayload,
    bundles: tuple[RepositoryModelBundle, ...],
    generation: _Generation,
) -> tuple[DocumentWorkSignal, ...]:
    """Adapt every record in the complete payload, or refuse the generation.

    Every record is adapted. There is no path here that skips one: a payload
    whose count was verified against its manifest and then silently reduced
    would conserve its total against a number that no longer described it.
    """
    index = _artifact_index(bundles)
    formats = _document_formats(generation)
    decodings = _normalized_document_ids(generation)
    signals = [_adapt_record(record, index, formats, decodings) for record in payload.records]
    return tuple(sorted(signals, key=lambda item: item.signal_id))


def _required_text(record: dict[str, Any], key: str, context: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise MetaGenerationError(f"{context}: {key} is missing or empty")
    return value


def _optional_text(record: dict[str, Any], key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) and value else None


def _evidence_class(record: dict[str, Any], context: str) -> Literal["declared", "observed"]:
    value = record.get("evidence_class")
    if value == "declared":
        return "declared"
    if value == "observed":
        return "observed"
    raise MetaGenerationError(
        f"{context}: evidence_class is {value!r}, not 'declared' or 'observed'"
    )


def _work_signals(
    generation: _Generation,
    bundles: tuple[RepositoryModelBundle, ...],
) -> tuple[tuple[DocumentWorkSignal, ...], tuple[UnadaptableSignal, ...]]:
    """Adapt every work assertion this generation can locate truthfully.

    Artifact identity comes from the document index by source path, because a
    repository-model assertion names the path it read and the corpus knows which
    artifact that path is. A path the index does not carry means the assertion
    came from a file no decoder opened, which is an ordinary repository-model
    assertion and reaches topology through the RMP rather than here.
    """
    formats = _document_formats(generation)
    paths = _artifact_paths(generation)
    artifact_by_path = {path: artifact_id for artifact_id, path in paths.items()}

    signals: list[DocumentWorkSignal] = []
    unadaptable: list[UnadaptableSignal] = []
    for bundle in bundles:
        payload = bundle.packet.payload
        if payload is None or not payload.assertions:
            continue
        for assertion in payload.assertions:
            if assertion.predicate not in WORK_PREDICATES:
                continue
            artifact_id = artifact_by_path.get(assertion.source_path)
            if artifact_id is None:
                continue
            document_format = formats.get(artifact_id, "text")
            if document_format not in LINE_BEARING_FORMATS:
                unadaptable.append(
                    UnadaptableSignal(
                        assertion_id=assertion.assertion_id,
                        artifact_id=artifact_id,
                        predicate=assertion.predicate,
                        document_format=document_format,
                        reason=UNADAPTABLE_NO_STRUCTURED_LOCATOR,
                    )
                )
                continue
            signals.append(_line_signal(assertion, artifact_id, document_format))
    return (
        tuple(sorted(signals, key=lambda item: item.signal_id)),
        tuple(sorted(unadaptable, key=lambda item: item.assertion_id)),
    )


def _line_signal(
    assertion: RepositoryModelAssertion, artifact_id: str, document_format: str
) -> DocumentWorkSignal:
    return DocumentWorkSignal(
        signal_id=assertion.assertion_id,
        artifact_id=artifact_id,
        subject_id=assertion.subject_id,
        predicate=assertion.predicate,
        object=assertion.object,
        source_path=assertion.source_path,
        locator={
            "kind": "line",
            "start_line": assertion.source_range.start_line,
            "end_line": assertion.source_range.end_line,
        },  # type: ignore[arg-type]
        source_content_hash=assertion.source_content_hash,
        document_format=document_format,
        evidence_excerpt=assertion.evidence_excerpt,
        extractor_id=assertion.extractor_id,
        # The generation does not record which decoder produced a line-bearing
        # document's text, because for those formats the producer reads the
        # file's own bytes rather than the decoder's blocks. Recorded as the
        # format itself rather than invented.
        decoder_id=document_format,
        decoder_version="unknown",
        evidence_class=assertion.evidence_class,
        authority=assertion.authority,
        confidence=assertion.confidence,
    )


def _duplicate_relations(
    generation: _Generation, identities: dict[str, str]
) -> tuple[ExactDuplicateRelation, ...]:
    candidates = generation.get(CANDIDATES_FILE) or {}
    relations: list[ExactDuplicateRelation] = []
    for entry in candidates.get("relations", ()):
        if entry.get("type") != "DUPLICATE_OF":
            continue
        relations.append(
            ExactDuplicateRelation(
                relation_id=str(entry["relation_id"]),
                duplicate_cluster_id=str(entry["duplicate_cluster_id"]),
                artifact_a_id=_translate(entry["source_artifact_id"], identities),
                artifact_b_id=_translate(entry["target_artifact_id"], identities),
                content_hash=str(entry["content_hash"]),
            )
        )
    return tuple(sorted(relations, key=lambda item: item.relation_id))


def _analysis_profile(document: Any, fallback: str) -> CorpusAnalysisProfileRef:
    profile = (document or {}).get("analysis_profile") or {}
    return CorpusAnalysisProfileRef(
        profile_id=str(profile.get("fusion_profile_id") or fallback),
        profile_version=str(profile.get("fusion_profile_version") or "unknown"),
        profile_hash=str(profile.get("fusion_profile_hash") or "unknown"),
    )


def _pair_relations(
    generation: _Generation, identities: dict[str, str]
) -> tuple[SemanticPairRelation, ...]:
    document = generation.get(SEMANTIC_RELATIONS_FILE) or {}
    profile = _analysis_profile(document, "semantic-fusion")
    classifications = {entry.get("pair_id"): entry for entry in document.get("classifications", ())}
    relations: list[SemanticPairRelation] = []
    for pair in document.get("pairs", ()):
        pair_id = pair.get("pair_id")
        classification = classifications.get(pair_id) or {}
        signals = pair.get("signals", ())
        relations.append(
            SemanticPairRelation(
                relation_id=str(pair_id),
                source_artifact_id=_translate(pair["artifact_a_id"], identities),
                target_artifact_id=_translate(pair["artifact_b_id"], identities),
                methods=tuple(
                    sorted({str(signal["method"]) for signal in signals if "method" in signal})
                ),
                method_scores=tuple(
                    sorted(
                        (
                            PairMethodScore(
                                method=str(signal["method"]),
                                score=max(0.0, min(1.0, float(signal.get("score", 0.0)))),
                            )
                            for signal in signals
                            if "method" in signal
                        ),
                        key=lambda item: item.method,
                    )
                ),
                evidence_refs=tuple(sorted(set(pair.get("evidence_refs", ())))),
                confidence_class=classification.get("confidence_class", "weak"),
                analysis_profile=profile,
                upstream_candidate_id=str(pair_id),
            )
        )
    return tuple(sorted(relations, key=lambda item: item.relation_id))


def _candidates(
    generation: _Generation,
    filename: str,
    candidate_type: str,
    identities: dict[str, str],
) -> tuple[CandidateCluster, ...]:
    document = generation.get(filename) or {}
    profile = _analysis_profile(document, candidate_type.lower())
    clusters: list[CandidateCluster] = []
    for entry in document.get("candidates", ()):
        supporting = tuple(
            sorted(
                {
                    *entry.get("supporting_pair_ids", ()),
                    *entry.get("exact_duplicate_cluster_ids", ()),
                    *entry.get("near_duplicate_candidate_ids", ()),
                }
            )
        )
        clusters.append(
            CandidateCluster(
                candidate_id=str(entry["candidate_id"]),
                candidate_type=candidate_type,  # type: ignore[arg-type]
                member_artifact_ids=tuple(
                    sorted(
                        {
                            _translate(member, identities)
                            for member in entry.get("member_artifact_ids", ())
                        }
                    )
                ),
                supporting_relation_ids=supporting,
                evidence_refs=tuple(sorted(set(entry.get("evidence_refs", ())))),
                confidence_class=entry.get("confidence_class", "weak"),
                ambiguity_flags=tuple(
                    sorted(
                        {
                            *entry.get("ambiguity_flags", ()),
                            *entry.get("ambiguity_class", ()),
                        }
                    )
                ),
                cross_root=bool(entry.get("cross_root", False)),
                cross_archive=bool(entry.get("cross_archive", False)),
                analysis_profile=profile,
                upstream_candidate_id=str(entry["candidate_id"]),
            )
        )
    return tuple(sorted(clusters, key=lambda item: item.candidate_id))


#: How the producer's grouped metrics map onto the canonical readiness fields.
#:
#: A table rather than twenty hand-written lookups: the producer groups its
#: counts by the question each answers, the canonical record is flat, and the
#: whole of that translation is worth being able to read in one place. Written as
#: ``(metric group, producer key) -> canonical field``.
_READINESS_FIELD_MAP: tuple[tuple[str, str, str], ...] = (
    ("implementation", "source_artifact_count", "source_artifact_count"),
    ("implementation", "manifest_count", "build_manifest_count"),
    ("validation", "structural_test_artifact_count", "test_artifact_count"),
    ("validation", "ci_definition_count", "ci_definition_count"),
    ("delivery", "deployment_definition_count", "deployment_definition_count"),
    ("knowledge", "specification_count", "specification_count"),
    ("knowledge", "documentation_count", "documentation_count"),
    ("knowledge", "plan_count", "plan_count"),
    ("knowledge", "roadmap_count", "roadmap_count"),
    ("work_state", "wip_count", "wip_count"),
    ("work_state", "draft_count", "draft_count"),
    ("work_state", "blocked_count", "blocked_count"),
    ("work_state", "open_task_count", "open_task_count"),
    ("work_state", "completed_task_count", "completed_task_count"),
    ("work_state", "milestone_count", "milestone_count"),
    ("reuse_and_duplication", "exact_duplicate_artifact_count", "exact_duplicate_count"),
    ("reuse_and_duplication", "near_duplicate_candidate_count", "near_duplicate_count"),
    (
        "reuse_and_duplication",
        "consolidation_candidate_count",
        "consolidation_candidate_count",
    ),
    ("uncertainty", "coverage_gap_count", "coverage_gap_count"),
)


def _readiness_counts(metrics: dict[str, Any]) -> dict[str, int]:
    """Return the canonical counts, defaulting anything absent to zero.

    A missing group or key means the producer recorded nothing of that kind,
    which is zero rather than unknown — every one of these is a count of things
    observed, and observing none is a real answer.
    """
    counts: dict[str, int] = {}
    for group, source_key, canonical_field in _READINESS_FIELD_MAP:
        value = (metrics.get(group) or {}).get(source_key)
        counts[canonical_field] = max(0, value) if isinstance(value, int) else 0
    return counts


def _readiness(generation: _Generation) -> tuple[ReadinessEvidence, ...]:
    """Adapt each body of work's metrics into one readiness record.

    The producer's metrics are grouped by the question each group answers;
    flattening them here loses the grouping and nothing else, because the
    canonical record's fields are the same counts under the same names. What is
    deliberately not carried across is anything the producer computed as a
    ratio — there is nothing of that kind to carry, which is the point.
    """
    document = generation.get(READINESS_FILE) or {}
    profile = document.get("profile") or {}
    records = [
        ReadinessEvidence.model_validate(
            {
                "readiness_id": str(body["body_id"]),
                # The body is derived from a candidate, so the readiness subject
                # is that candidate: it is what the counts are about, and what a
                # topology candidate record can attach them to.
                "subject_id": str(body.get("origin_ref") or body["body_id"]),
                "profile_id": str(profile.get("profile_id") or "readiness"),
                "profile_version": str(profile.get("profile_version") or "unknown"),
                **_readiness_counts(body.get("metrics") or {}),
            }
        )
        for body in document.get("bodies_of_work", ())
    ]
    return tuple(sorted(records, key=lambda item: item.readiness_id))


def _reasoning(
    generation: _Generation, identities: dict[str, str]
) -> tuple[tuple[ReasoningCandidateRequest, ...], tuple[str, ...]]:
    rows = generation.get(REASONING_CANDIDATES_FILE) or []
    packs = generation.get(REASONING_PACKS_FILE) or []
    pack_by_candidate = {
        str(pack.get("reasoning_candidate_id")): str(pack.get("evidence_pack_id"))
        for pack in packs
        if pack.get("reasoning_candidate_id") and pack.get("evidence_pack_id")
    }
    requests = tuple(
        sorted(
            (
                ReasoningCandidateRequest(
                    reasoning_candidate_id=str(row["reasoning_candidate_id"]),
                    candidate_id=str(row["candidate_id"]),
                    recommended_reasoning_type=row.get("reasoning_type", "NONE"),
                    reason=str(row.get("reason") or ""),
                    member_artifact_ids=tuple(
                        sorted(
                            {
                                _translate(member, identities)
                                for member in row.get("member_artifact_ids", ())
                            }
                        )
                    ),
                    evidence_pack_ref=pack_by_candidate.get(str(row["reasoning_candidate_id"])),
                )
                for row in rows
            ),
            key=lambda item: item.reasoning_candidate_id,
        )
    )
    return requests, tuple(sorted(set(pack_by_candidate.values())))


def _drop_orphan_reasoning(
    reasoning: tuple[ReasoningCandidateRequest, ...],
    known_candidates: frozenset[str],
) -> tuple[tuple[ReasoningCandidateRequest, ...], tuple[str, ...]]:
    """Drop reasoning rows naming a candidate this generation did not write.

    A cross-file inconsistency in the generation. Dropped with a diagnostic
    rather than carried: the packet's own integrity check would refuse it anyway,
    and failing there would report a generation defect as a topology one.
    """
    kept = tuple(request for request in reasoning if request.candidate_id in known_candidates)
    dropped = tuple(
        sorted(
            request.reasoning_candidate_id
            for request in reasoning
            if request.candidate_id not in known_candidates
        )
    )
    return kept, dropped


def _build_payload(
    generation: _Generation,
    bundles: tuple[RepositoryModelBundle, ...],
    *,
    mode: str,
    work_signals: WorkSignalPayload | None,
    identities: dict[str, str],
) -> tuple[CorpusIntelligencePayload, tuple[UnadaptableSignal, ...], tuple[str, ...]]:
    """Assemble every payload domain, plus what could not be carried.

    The declines are returned alongside the payload rather than logged: an
    adapter that reported only its successes would make the gap invisible. In
    current mode there are none — every record in a verified payload is adapted
    or the whole adaptation fails.
    """
    if mode == MODE_CURRENT_COMPLETE:
        if work_signals is None:  # pragma: no cover - guarded by the caller
            raise MetaGenerationError("current mode requires a verified work-signal payload")
        signals = _current_work_signals(work_signals, bundles, generation)
        unadaptable: tuple[UnadaptableSignal, ...] = ()
    else:
        signals, unadaptable = _work_signals(generation, bundles)
    topic = _candidates(generation, TOPIC_CANDIDATES_FILE, "TOPIC_CANDIDATE", identities)
    project = _candidates(generation, PROJECT_CANDIDATES_FILE, "PROJECT_CANDIDATE", identities)
    consolidation = _candidates(
        generation, CONSOLIDATION_CANDIDATES_FILE, "CONSOLIDATION_CANDIDATE", identities
    )
    reasoning, pack_refs = _reasoning(generation, identities)
    reasoning, dropped = _drop_orphan_reasoning(
        reasoning,
        frozenset(candidate.candidate_id for candidate in (*topic, *project, *consolidation)),
    )
    payload = CorpusIntelligencePayload(
        document_work_signals=signals,
        exact_duplicate_relations=_duplicate_relations(generation, identities),
        semantic_pair_relations=_pair_relations(generation, identities),
        topic_candidates=topic,
        project_candidates=project,
        consolidation_candidates=consolidation,
        readiness_evidence=_readiness(generation),
        reasoning_candidates=reasoning,
        reasoning_evidence_pack_refs=pack_refs,
    )
    return payload, unadaptable, dropped


def _tally_signals(
    signals: tuple[DocumentWorkSignal, ...], attribute: str
) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for signal in signals:
        key = str(getattr(signal, attribute))
        counts[key] = counts.get(key, 0) + 1
    return tuple(sorted(counts.items()))


def _tally_identity_classes(roots: tuple[CorpusRootRef, ...]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for root in roots:
        counts[root.identity_class] = counts.get(root.identity_class, 0) + 1
    return tuple(sorted(counts.items()))


def _sampled_report_listed_count(generation: _Generation) -> int | None:
    """How many evidence records the *report* lists, for comparison only.

    Never a source of signals. It is read so the adapter can say out loud that
    the report is a sample of the payload rather than a second copy of it.
    """
    document = generation.get(DOCUMENT_SIGNALS_FILE)
    if not isinstance(document, dict):
        return None
    block_signals = document.get("block_signals")
    if not isinstance(block_signals, dict):
        return None
    formats = block_signals.get("by_format")
    if not isinstance(formats, list):
        return None
    total = 0
    for entry in formats:
        if isinstance(entry, dict) and isinstance(entry.get("listed_signal_count"), int):
            total += int(entry["listed_signal_count"])
    return total


def _diagnostics(
    mode: str,
    unadaptable: tuple[UnadaptableSignal, ...],
    dropped_reasoning: tuple[str, ...],
) -> tuple[str, ...]:
    """What the caller should know that the counts alone do not say."""
    notes: list[str] = []
    if dropped_reasoning:
        notes.append(
            "dropped reasoning candidates naming a candidate this generation did not "
            f"write: {', '.join(dropped_reasoning)}"
        )
    if unadaptable:
        notes.append(
            f"{len(unadaptable)} work signal(s) were not adapted because this generation "
            "records them only as line spans into joined block text"
        )
    if mode == MODE_LEGACY_LINE_ASSERTIONS:
        notes.append(
            "read in legacy mode: this generation predates the complete work-signal "
            "payload, so binary-document signals are reported rather than adapted. "
            "It does not qualify the current producer contract."
        )
    return tuple(notes)


def adapt_meta_generation(path: Path) -> MetaAdaptationReport:
    """Read a Meta corpus generation and return the packet it maps to.

    Purely a read. Nothing under ``path`` is written, and the returned packet is
    the caller's to commit through an ``OutputSink``.
    """
    root = resolve_generation_root(path)
    generation = _read_generation(root)
    mode = detect_adaptation_mode(root)
    work_signal_payload = load_work_signal_payload(root) if mode == MODE_CURRENT_COMPLETE else None
    root_refs, bundles = _load_root_bundles(generation, mode=mode)
    snapshot = generation.require(SNAPSHOT_FILE)
    analysis = snapshot.get("analysis") or {}

    payload, unadaptable, dropped_reasoning = _build_payload(
        generation,
        bundles,
        mode=mode,
        work_signals=work_signal_payload,
        identities=_corpus_to_rmp_ids(generation, root_refs, bundles),
    )
    packet = CorpusIntelligencePacket(
        packet_id="packet:pending",
        producer=Producer(name=ADAPTER_NAME, version=ADAPTER_VERSION),
        profile=ProfileRef(
            id=str(analysis.get("corpus_profile") or "l9-meta-injector-corpus-intelligence"),
            version=str(analysis.get("interpretation_profile") or "unknown"),
            hash=str(analysis.get("corpus_analysis_id") or "unknown"),
        ),
        inputs=CorpusIntelligenceInputs(
            repository_model_packets=tuple(
                sorted(
                    (root.repository_model_packet for root in root_refs),
                    key=lambda ref: ref.packet_id,
                )
            )
        ),
        corpus=CorpusDescriptor(
            corpus_id=str(snapshot.get("corpus_id") or "corpus"),
            corpus_source_snapshot_id=str(snapshot["corpus_source_snapshot_id"]),
            corpus_analysis_id=str(analysis.get("corpus_analysis_id") or "unknown"),
            root_refs=root_refs,
            coverage=_coverage(generation),
        ),
        # The generation is a validated producer output, but this adapter did not
        # run the producer's validator and will not claim it did.
        validation=PacketValidationRef(status="not_run"),
        schema_hash=str(snapshot.get("schema") or "l9.corpus-snapshot/v1"),
        semantic_hash="sha256:pending",
        payload=payload,
    )
    diagnostics = _diagnostics(mode, unadaptable, dropped_reasoning)
    signals = payload.document_work_signals
    manifest = work_signal_payload.manifest if work_signal_payload is not None else {}
    sampled = _sampled_report_listed_count(generation)
    if mode == MODE_CURRENT_COMPLETE and sampled is not None and sampled > len(signals):
        raise MetaGenerationError(
            f"the sampled report lists {sampled} signal(s) and the complete payload "
            f"carries {len(signals)}; the report cannot exceed the payload it samples"
        )

    return MetaAdaptationReport(
        packet=finalize_corpus_intelligence_packet(packet),
        generation_root=root,
        root_bundles=bundles,
        adapted_signal_count=len(signals),
        unadaptable_signals=unadaptable,
        adaptation_mode=mode,
        manifest_record_count=int(manifest.get("record_count") or 0),
        parsed_signal_count=(
            work_signal_payload.record_count if work_signal_payload is not None else 0
        ),
        producer_revision=str(analysis.get("corpus_analysis_id") or ""),
        sampled_report_listed_count=sampled,
        adapted_by_format=_tally_signals(signals, "document_format"),
        adapted_by_predicate=_tally_signals(signals, "predicate"),
        root_identity_class_counts=_tally_identity_classes(root_refs),
        missing_files=tuple(sorted(generation.missing)),
        diagnostics=tuple(diagnostics),
    )
