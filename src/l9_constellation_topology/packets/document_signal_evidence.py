"""Bind every document work signal to a first-class topology evidence record.

The counterpart of ``assertion_evidence`` for structured documents, and
deliberately shaped the same way: a signal arrives carrying its own proof — an
exact coordinate inside a hashed document, the decoder that opened it, the
extractor that read it, and the excerpt it read — and all of that survives onto
an ``EvidenceRecord``.

One thing differs, and it is the reason this module exists rather than the
assertion path being reused. A repository-model assertion cites a line span,
because the files it reads have lines. A work signal from a Word document, a
slide deck, a workbook, or a notebook does not: it cites a block index, a slide
and shape, a sheet and cell, or a cell ordinal. Reducing any of those to a line
number would not be lossy so much as false — ``line 7`` of a ``.docx`` names
nothing an operator can open — so the locator is carried structurally and
``line_number`` is left unset for every format that has no lines.

Everything else is identical, and identical on purpose: the same authority
mapping, the same refusal to upgrade a producer's confidence, the same fixed
synthetic ``created_at``, and the same reconciliation downstream.
"""

from __future__ import annotations

from l9_constellation_topology.domain.confidence import (
    Completeness,
    ConfidenceAssessment,
    EvidenceStrength,
)
from l9_constellation_topology.reconciliation.inputs import SemanticInput
from l9_constellation_topology.run.evidence import (
    EvidenceRecord,
    EvidenceSourceRef,
    LineLocator,
    make_evidence_record,
)

from .assertion_evidence import (
    ASSERTION_EVIDENCE_CREATED_AT,
    named_authority,
    named_derivation,
    named_level,
)
from .corpus_intelligence import CorpusIntelligencePacket, DocumentWorkSignal

#: Stage recorded on document-signal evidence.
#:
#: Distinct from ``ingest_assertions`` so the two provenances stay separable
#: after the fact: a consumer asking "which of these claims came out of a binary
#: document" can answer it from the evidence pool alone.
DOCUMENT_SIGNAL_EVIDENCE_STAGE = "ingest_document_signals"


def signal_confidence(signal: DocumentWorkSignal) -> ConfidenceAssessment:
    """Return the confidence of one work signal's evidence."""
    return ConfidenceAssessment(
        level=named_level(signal.confidence),
        # The signal cites an exact coordinate in a hashed document. That is
        # direct evidence for the claim, however weak the claim itself is.
        evidence_strength=EvidenceStrength.direct,
        derivation_method=named_derivation(signal.evidence_class),
        authority=named_authority(signal.authority),
        completeness=Completeness.sufficient,
    )


def signal_evidence_value(signal: DocumentWorkSignal) -> dict[str, object]:
    """Return everything about a signal the evidence record must carry.

    ``assertion_id`` rather than ``signal_id``: the assertion-conservation check
    and the reconciliation evidence index both key on that name, and giving the
    same concept two names across two producers would mean two lookups where one
    will do. The decoder identity is recorded beside it, because which decoder
    read a document is part of what makes the reading reproducible.
    """
    return {
        "assertion_id": signal.signal_id,
        "predicate": signal.predicate,
        "object": signal.object,
        "evidence_excerpt": signal.evidence_excerpt,
        "extractor_id": signal.extractor_id,
        "decoder_id": signal.decoder_id,
        "decoder_version": signal.decoder_version,
        "document_format": signal.document_format,
        "artifact_id": signal.artifact_id,
        "locator": signal.locator.model_dump(mode="json"),
        "declared_authority": signal.authority,
        "declared_confidence": signal.confidence,
    }


def signal_source_ref(
    signal: DocumentWorkSignal, *, packet: CorpusIntelligencePacket
) -> EvidenceSourceRef:
    """Return where this signal was read, in the document's own coordinates.

    ``line_number`` is populated only when the locator is a line span, and then
    only to its start line. For every other format it stays unset: the evidence
    ref refuses a line number beside a structured locator, so a caller cannot
    quietly reintroduce the flattening this module exists to avoid.
    """
    line_number = signal.locator.start_line if isinstance(signal.locator, LineLocator) else None
    return EvidenceSourceRef(
        source_path=signal.source_path,
        line_number=line_number,
        # The source document's digest, not the corpus snapshot's. A claim must
        # stay bound to the bytes that support it, so that an unrelated file
        # appearing elsewhere in the corpus does not move this claim's evidence.
        content_hash=signal.source_content_hash,
        packet_id=packet.packet_id,
        source_revision=None,
        locator=signal.locator,
    )


def signal_evidence_record(
    signal: DocumentWorkSignal, *, packet: CorpusIntelligencePacket
) -> EvidenceRecord:
    """Return the topology evidence record for one document work signal."""
    return make_evidence_record(
        subject_id=signal.subject_id,
        # The predicate is the field this evidence speaks to, which is what makes
        # a per-predicate conflict material to exactly the claims depending on
        # it, and to nothing else.
        field=signal.predicate,
        stage=DOCUMENT_SIGNAL_EVIDENCE_STAGE,
        evidence_class=signal.evidence_class,
        source_type="file",
        source_ref=signal_source_ref(signal, packet=packet),
        value=signal_evidence_value(signal),
        confidence=signal_confidence(signal),
        producer=packet.producer.name,
        producer_version=packet.producer.version,
        created_at=ASSERTION_EVIDENCE_CREATED_AT,
    )


def signal_evidence_records(
    packet: CorpusIntelligencePacket,
) -> tuple[EvidenceRecord, ...]:
    """Return evidence for every work signal the packet carries, in packet order."""
    if packet.payload is None or not packet.payload.document_work_signals:
        return ()
    return tuple(
        signal_evidence_record(signal, packet=packet)
        for signal in packet.payload.document_work_signals
    )


def signal_semantic_input(signal: DocumentWorkSignal) -> SemanticInput:
    """Reduce a work signal to the shape reconciliation reads.

    Identical in kind to what a repository-model assertion reduces to, which is
    the point: downstream cannot tell a Word document's status claim from a
    Markdown file's, and so cannot reconcile them under different rules.
    """
    return SemanticInput(
        input_id=signal.signal_id,
        subject_id=signal.subject_id,
        predicate=signal.predicate,
        object=signal.object,
        authority=signal.authority,
        confidence=signal.confidence,
        evidence_class=signal.evidence_class,
        origin="corpus-document-signal",
    )


def signal_semantic_inputs(
    packet: CorpusIntelligencePacket,
) -> tuple[SemanticInput, ...]:
    if packet.payload is None:
        return ()
    return tuple(signal_semantic_input(signal) for signal in packet.payload.document_work_signals)
