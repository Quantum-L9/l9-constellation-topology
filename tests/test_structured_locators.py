"""Structured evidence locators, and the fake line numbers they exist to prevent.

A Word document has no lines. Neither does a slide deck, a workbook, or a PDF.
The whole point of the locator union is that evidence read out of one of those
cites the coordinate its format actually has, and the tests here are mostly
about the *refusals* — because a locator that is merely absent is recoverable,
and one that is confidently wrong is not.
"""

from __future__ import annotations

import pytest

from l9_constellation_topology.packets.corpus_intelligence import DocumentWorkSignal
from l9_constellation_topology.packets.corpus_validator import (
    CorpusIntelligenceValidationError,
    validate_corpus_intelligence_packet,
)
from l9_constellation_topology.packets.document_signal_evidence import (
    signal_evidence_record,
    signal_source_ref,
)
from l9_constellation_topology.run.evidence import EvidenceSourceRef, semantic_hash
from tests.corpus_fixtures import (
    REPOSITORY_PACKETS,
    corpus_packet,
    corpus_payload,
    signal,
)

#: One locator per coordinate system a real decoder produces.
LOCATORS: dict[str, dict[str, object]] = {
    "line": {"kind": "line", "start_line": 3, "end_line": 5},
    "pdf": {"kind": "pdf", "page_number": 2, "block_index": 7},
    "docx": {"kind": "docx", "block_index": 4, "block_kind": "heading"},
    "pptx": {"kind": "pptx", "slide_number": 3, "shape_index": 1},
    "spreadsheet": {"kind": "spreadsheet", "sheet": "Tasks", "cell_or_range": "B7"},
    "notebook": {"kind": "notebook", "cell_index": 3, "cell_type": "markdown"},
    "csv": {"kind": "csv", "row": 12},
    "html": {"kind": "html", "stable_node_index": 42},
}


@pytest.mark.parametrize("kind", sorted(LOCATORS))
def test_every_locator_kind_round_trips_through_an_evidence_ref(kind: str) -> None:
    reference = EvidenceSourceRef(source_path="doc.bin", locator=LOCATORS[kind])  # type: ignore[arg-type]
    assert reference.locator is not None
    assert reference.locator.kind == kind
    restored = EvidenceSourceRef.model_validate(reference.model_dump(mode="json"))
    assert restored == reference


@pytest.mark.parametrize("kind", sorted(set(LOCATORS) - {"line"}))
def test_a_structured_locator_may_not_carry_a_line_number(kind: str) -> None:
    """The union's central refusal.

    A consumer that reads only ``line_number`` must never be handed one for a
    format that has no lines: it cannot tell such a number from a real one, and
    would report a coordinate an operator cannot open the file and find.
    """
    with pytest.raises(ValueError, match="no lines to number"):
        EvidenceSourceRef(source_path="doc.bin", line_number=7, locator=LOCATORS[kind])  # type: ignore[arg-type]


def test_a_line_locator_may_also_project_to_a_line_number() -> None:
    reference = EvidenceSourceRef(
        source_path="plan.md",
        line_number=3,
        locator=LOCATORS["line"],  # type: ignore[arg-type]
    )
    assert reference.line_number == 3


def test_a_line_number_disagreeing_with_its_locator_is_refused() -> None:
    with pytest.raises(ValueError, match="must equal the line locator"):
        EvidenceSourceRef(
            source_path="plan.md",
            line_number=9,
            locator=LOCATORS["line"],  # type: ignore[arg-type]
        )


def test_an_existing_line_only_reference_is_unchanged() -> None:
    """Repository-model assertions predate locators and must stay byte-identical.

    ``locator`` is excluded from serialization when absent, so an assertion's
    evidence hashes exactly as it did before the field existed. That is what
    keeps every already-published effect key where it was.
    """
    reference = EvidenceSourceRef(source_path="pyproject.toml", line_number=4)
    assert reference.locator is None
    assert "locator" not in reference.model_dump(mode="json", exclude_none=True)


def test_the_locator_participates_in_semantic_identity() -> None:
    """Two signals differing only in where they were read are two facts."""
    first = EvidenceSourceRef(source_path="deck.pptx", locator=LOCATORS["pptx"])  # type: ignore[arg-type]
    second = EvidenceSourceRef(
        source_path="deck.pptx",
        locator={"kind": "pptx", "slide_number": 9, "shape_index": 1},  # type: ignore[arg-type]
    )
    assert semantic_hash(first) != semantic_hash(second)


@pytest.mark.parametrize(
    ("document_format", "kind"),
    [
        ("markdown", "line"),
        ("docx", "docx"),
        ("pptx", "pptx"),
        ("pdf", "pdf"),
        ("xlsx", "spreadsheet"),
        ("ipynb", "notebook"),
        ("csv", "csv"),
        ("html", "html"),
    ],
)
def test_a_work_signal_carries_its_format_s_own_coordinate(document_format: str, kind: str) -> None:
    record = signal(
        f"signal:{document_format}",
        "plan_md",
        "work.status",
        "WIP",
        LOCATORS[kind],
        document_format,
    )
    reference = signal_source_ref(record, packet=corpus_packet())
    assert reference.locator is not None
    assert reference.locator.kind == kind
    # A line number appears only where the format has lines.
    assert (reference.line_number is not None) == (kind == "line")


def test_a_binary_document_signal_claiming_a_line_locator_is_refused() -> None:
    """The packet boundary's own check, independent of the evidence ref's.

    A ``.docx`` signal citing ``line 7`` is syntactically valid — a line locator
    is a real locator — so the refusal has to come from the format, which is why
    the packet carries ``document_format`` at all.
    """
    fake = signal(
        "signal:fake-line",
        "wip_docx",
        "work.status",
        "WIP",
        LOCATORS["line"],
        "docx",
    )
    with pytest.raises(CorpusIntelligenceValidationError) as caught:
        validate_corpus_intelligence_packet(
            corpus_packet(corpus_payload(document_work_signals=(fake,))),
            REPOSITORY_PACKETS,
        )
    assert any("has no lines" in error for error in caught.value.errors)


def test_signal_evidence_carries_the_source_document_digest_not_the_snapshot() -> None:
    """A claim stays bound to the bytes behind it.

    Binding to the corpus snapshot instead would move this claim's evidence every
    time an unrelated file appeared anywhere in the corpus, which is exactly the
    coupling effect identity v3 exists to remove.
    """
    record = signal(
        "signal:docx",
        "wip_docx",
        "work.status",
        "WIP",
        LOCATORS["docx"],
        "docx",
    )
    packet = corpus_packet()
    evidence = signal_evidence_record(record, packet=packet)
    assert evidence.source_ref.content_hash == record.source_content_hash
    assert evidence.source_ref.content_hash != packet.corpus.corpus_source_snapshot_id


def test_a_work_signal_requires_a_locator() -> None:
    """A signal that cannot say where it came from is not evidence."""
    with pytest.raises(ValueError):
        DocumentWorkSignal(
            signal_id="signal:nowhere",
            artifact_id="artifact:plan-md",
            subject_id="repo:plans",
            predicate="work.status",
            object="WIP",
            source_path="plans/plan.md",
            source_content_hash="sha256:" + "1" * 64,
            document_format="markdown",
            evidence_excerpt="",
            extractor_id="x",
            decoder_id="markdown",
            decoder_version="1.0.0",
            evidence_class="declared",
            authority="source",
            confidence="high",
        )  # type: ignore[call-arg]
