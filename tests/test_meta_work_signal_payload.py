"""The complete work-signal payload, and every way it is refused.

The payload is the only document in a Meta generation that states the whole of
what the corpus read. Its manifest is what makes that statement checkable, so
this suite is mostly about the manifest: a payload whose count and hashes are
not verified is a payload whose losses are invisible, and invisible loss is the
one failure that cannot be audited afterwards.

Every refusal here is fail-closed on purpose. Compiling the readable subset of a
damaged payload would produce a topology that looks complete and silently omits
whatever the producer got wrong.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from l9_constellation_topology.packets.adapters.errors import MetaGenerationError
from l9_constellation_topology.packets.adapters.meta_work_signals import (
    DOCUMENT_WORK_SIGNALS_FILE,
    DOCUMENT_WORK_SIGNALS_MANIFEST_FILE,
    DOCUMENT_WORK_SIGNALS_SCHEMA,
    load_work_signal_payload,
    translate_locator,
)
from l9_constellation_topology.run.evidence import canonical_json, sha256_text


def _signal(**overrides: Any) -> dict[str, Any]:
    record = {
        "signal_id": "sig:1",
        "artifact_id": "vsrc:1",
        "rmp_artifact_id": "artifact:1",
        "source_path": "plan.md",
        "format": "markdown",
        "raw_content_hash": "sha256:" + "a" * 64,
        "normalized_document_id": "normdoc:1",
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
    record.update(overrides)
    return record


def _write(root: Path, records: list[dict[str, Any]], **manifest_overrides: Any) -> Path:
    """Write a payload and a manifest computed from it.

    The manifest is derived rather than written out by hand, so a test that
    wants to break one field breaks exactly that field and every other value
    stays true. A fixture with hand-copied hashes would keep passing if the
    reader stopped checking them.
    """
    payload = "".join(canonical_json(record) + "\n" for record in records)
    formats: dict[str, int] = {}
    predicates: dict[str, int] = {}
    for record in records:
        formats[record["format"]] = formats.get(record["format"], 0) + 1
        predicates[record["predicate"]] = predicates.get(record["predicate"], 0) + 1
    manifest = {
        "schema": "l9.document-work-signals-manifest/v1",
        "corpus_source_snapshot_id": "snap:1",
        "corpus_analysis_id": "analysis:1",
        "profile_id": "l9.interpretation",
        "profile_version": "1.0.0",
        "profile_hash": "sha256:" + "b" * 64,
        "payload_file": DOCUMENT_WORK_SIGNALS_FILE,
        "record_count": len(records),
        "document_count": len({record["artifact_id"] for record in records}),
        "by_format": [
            {"format": name, "document_count": 1, "signal_count": count}
            for name, count in sorted(formats.items())
        ],
        "by_predicate": [
            {"predicate": name, "signal_count": count} for name, count in sorted(predicates.items())
        ],
        "payload_byte_length": len(payload.encode("utf-8")),
        "payload_artifact_hash": sha256_text(payload),
        "payload_semantic_hash": sha256_text(
            canonical_json({"schema": DOCUMENT_WORK_SIGNALS_SCHEMA, "records": records})
        ),
    }
    manifest.update(manifest_overrides)
    (root / DOCUMENT_WORK_SIGNALS_FILE).write_text(payload, encoding="utf-8")
    (root / DOCUMENT_WORK_SIGNALS_MANIFEST_FILE).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return root


def _write_raw(root: Path, payload_text: str, *, record_count: int) -> Path:
    """Write payload text with a manifest whose integrity fields match it.

    Used for the parse failures. The reader checks byte length and the artifact
    hash before it parses anything — cheap checks first — so a test that edits
    the payload without updating those trips the integrity check instead of the
    one it meant to exercise, and would pass while proving nothing about
    parsing.
    """
    manifest = {
        "schema": "l9.document-work-signals-manifest/v1",
        "corpus_source_snapshot_id": "snap:1",
        "corpus_analysis_id": "analysis:1",
        "profile_id": "l9.interpretation",
        "profile_version": "1.0.0",
        "profile_hash": "sha256:" + "b" * 64,
        "payload_file": DOCUMENT_WORK_SIGNALS_FILE,
        "record_count": record_count,
        "payload_byte_length": len(payload_text.encode("utf-8")),
        "payload_artifact_hash": sha256_text(payload_text),
        "payload_semantic_hash": "sha256:" + "c" * 64,
    }
    (root / DOCUMENT_WORK_SIGNALS_FILE).write_text(payload_text, encoding="utf-8")
    (root / DOCUMENT_WORK_SIGNALS_MANIFEST_FILE).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return root


@pytest.fixture
def generation(tmp_path: Path) -> Path:
    return _write(tmp_path, [_signal(), _signal(signal_id="sig:2", predicate="work.kind")])


def test_a_sound_payload_loads(generation: Path) -> None:
    payload = load_work_signal_payload(generation)
    assert payload.record_count == 2
    assert payload.manifest["record_count"] == 2


def test_the_manifest_hashes_are_recomputed_not_trusted(generation: Path) -> None:
    """The difference between checking and reading a claim back.

    Both hashes are recalculated here from the bytes and the records. A manifest
    that merely *contains* a hash proves nothing about the payload beside it.
    """
    manifest = json.loads(
        (generation / DOCUMENT_WORK_SIGNALS_MANIFEST_FILE).read_text(encoding="utf-8")
    )
    payload_text = (generation / DOCUMENT_WORK_SIGNALS_FILE).read_text(encoding="utf-8")
    assert manifest["payload_artifact_hash"] == sha256_text(payload_text)
    assert load_work_signal_payload(generation).record_count == 2


# --- the payload and its manifest are one document in two files -------------


def test_a_payload_without_a_manifest_is_refused(generation: Path) -> None:
    (generation / DOCUMENT_WORK_SIGNALS_MANIFEST_FILE).unlink()
    with pytest.raises(
        MetaGenerationError, match=re.escape("missing document-work-signals.manifest.json")
    ):
        load_work_signal_payload(generation)


def test_a_manifest_without_a_payload_is_refused(generation: Path) -> None:
    (generation / DOCUMENT_WORK_SIGNALS_FILE).unlink()
    with pytest.raises(MetaGenerationError, match="describes a payload that is not there"):
        load_work_signal_payload(generation)


def test_a_manifest_of_an_unsupported_schema_is_refused(tmp_path: Path) -> None:
    _write(tmp_path, [_signal()], schema="l9.document-work-signals-manifest/v2")
    with pytest.raises(MetaGenerationError, match="this reader supports exactly"):
        load_work_signal_payload(tmp_path)


def test_a_manifest_describing_another_file_is_refused(tmp_path: Path) -> None:
    _write(tmp_path, [_signal()], payload_file="something-else.jsonl")
    with pytest.raises(MetaGenerationError, match="describes payload_file"):
        load_work_signal_payload(tmp_path)


# --- integrity ---------------------------------------------------------------


def test_a_wrong_byte_length_is_refused(tmp_path: Path) -> None:
    _write(tmp_path, [_signal()], payload_byte_length=999)
    with pytest.raises(MetaGenerationError, match="byte"):
        load_work_signal_payload(tmp_path)


def test_a_wrong_artifact_hash_is_refused(tmp_path: Path) -> None:
    _write(tmp_path, [_signal()], payload_artifact_hash="sha256:" + "0" * 64)
    with pytest.raises(MetaGenerationError, match="artifact hash"):
        load_work_signal_payload(tmp_path)


def test_a_wrong_semantic_hash_is_refused(tmp_path: Path) -> None:
    _write(tmp_path, [_signal()], payload_semantic_hash="sha256:" + "0" * 64)
    with pytest.raises(MetaGenerationError, match="semantic hash"):
        load_work_signal_payload(tmp_path)


def test_a_record_count_above_the_payload_is_refused(tmp_path: Path) -> None:
    _write(tmp_path, [_signal()], record_count=5)
    with pytest.raises(MetaGenerationError, match="declares 5 record"):
        load_work_signal_payload(tmp_path)


def test_a_record_count_below_the_payload_is_refused(tmp_path: Path) -> None:
    _write(tmp_path, [_signal(), _signal(signal_id="sig:2")], record_count=1)
    with pytest.raises(MetaGenerationError, match="declares 1 record"):
        load_work_signal_payload(tmp_path)


def test_a_wrong_document_count_is_refused(tmp_path: Path) -> None:
    _write(tmp_path, [_signal()], document_count=7)
    with pytest.raises(MetaGenerationError, match="declares 7 document"):
        load_work_signal_payload(tmp_path)


def test_a_wrong_per_format_count_is_refused(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [_signal()],
        by_format=[{"format": "markdown", "document_count": 1, "signal_count": 4}],
    )
    with pytest.raises(MetaGenerationError, match="by_format declares 4 signal"):
        load_work_signal_payload(tmp_path)


def test_a_format_the_manifest_does_not_declare_is_refused(tmp_path: Path) -> None:
    """Silence about a format is not the same as declaring zero of it."""
    _write(
        tmp_path,
        [_signal(), _signal(signal_id="sig:2", format="docx")],
        by_format=[{"format": "markdown", "document_count": 1, "signal_count": 1}],
    )
    with pytest.raises(MetaGenerationError, match="does not declare: docx"):
        load_work_signal_payload(tmp_path)


def test_a_wrong_per_predicate_count_is_refused(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [_signal()],
        by_predicate=[{"predicate": "work.status", "signal_count": 9}],
    )
    with pytest.raises(MetaGenerationError, match="by_predicate declares 9 signal"):
        load_work_signal_payload(tmp_path)


# --- the payload itself ------------------------------------------------------


def test_a_duplicate_signal_id_is_refused_rather_than_collapsed(tmp_path: Path) -> None:
    """Two records under one identity cannot both be kept, and neither can be
    chosen: the payload gives no way to tell a double write from two claims."""
    _write(tmp_path, [_signal(), _signal(predicate="work.kind")])
    with pytest.raises(MetaGenerationError, match="repeats signal_id"):
        load_work_signal_payload(tmp_path)


def test_a_malformed_line_names_the_line(tmp_path: Path) -> None:
    """A payload that fails to parse at line 4,000 is a different report from
    one that simply did not parse."""
    good = canonical_json(_signal())
    _write_raw(tmp_path, f"{good}\n{{not json\n", record_count=2)
    with pytest.raises(MetaGenerationError, match="line 2 did not parse"):
        load_work_signal_payload(tmp_path)


def test_a_record_without_a_signal_id_is_refused(tmp_path: Path) -> None:
    record = _signal()
    del record["signal_id"]
    _write_raw(tmp_path, canonical_json(record) + "\n", record_count=1)
    with pytest.raises(MetaGenerationError, match="carries no signal_id"):
        load_work_signal_payload(tmp_path)


def test_a_blank_line_is_refused(tmp_path: Path) -> None:
    """The payload is one record per line; a blank line is not a record."""
    good = canonical_json(_signal())
    _write_raw(tmp_path, f"{good}\n\n", record_count=1)
    with pytest.raises(MetaGenerationError, match="is blank"):
        load_work_signal_payload(tmp_path)


# --- locators ----------------------------------------------------------------


def _locate(raw: Any, *, document_format: str = "docx", block_kind: str = "heading") -> Any:
    return translate_locator(
        raw, document_format=document_format, block_kind=block_kind, context="signal"
    )


@pytest.mark.parametrize(
    ("producer", "document_format", "expected"),
    [
        (
            {"kind": "line_span", "line_start": 3, "line_end": 4},
            "markdown",
            {"kind": "line", "start_line": 3, "end_line": 4},
        ),
        (
            {"kind": "pdf_page_block", "page_number": 2, "block_index": 5},
            "pdf",
            {"kind": "pdf", "page_number": 2, "block_index": 5},
        ),
        (
            {"kind": "docx_block", "block_index": 7, "part": "word/document.xml"},
            "docx",
            {
                "kind": "docx",
                "block_index": 7,
                "block_kind": "heading",
                "part": "word/document.xml",
            },
        ),
        (
            {"kind": "pptx_shape", "slide_number": 1, "shape_index": 2, "part": "ppt/slide1.xml"},
            "pptx",
            {"kind": "pptx", "slide_number": 1, "shape_index": 2, "part": "ppt/slide1.xml"},
        ),
        (
            {"kind": "spreadsheet_cell", "sheet": "Tracker", "cell_or_range": "B4"},
            "xlsx",
            {"kind": "spreadsheet", "sheet": "Tracker", "cell_or_range": "B4"},
        ),
        (
            {"kind": "notebook_cell", "cell_index": 3, "cell_type": "markdown"},
            "ipynb",
            {"kind": "notebook", "cell_index": 3, "cell_type": "markdown"},
        ),
        (
            {"kind": "csv_row", "row_number": 9, "column": "status"},
            "csv",
            {"kind": "csv", "row": 9, "column": "status"},
        ),
        (
            {"kind": "html_node", "node_index": 12, "node_path": "html/body/p"},
            "html",
            {"kind": "html", "stable_node_index": 12, "node_path": "html/body/p"},
        ),
    ],
)
def test_every_producer_locator_kind_translates(
    producer: dict[str, Any], document_format: str, expected: dict[str, Any]
) -> None:
    """A rename, and nothing more. No coordinate becomes another coordinate."""
    assert _locate(producer, document_format=document_format) == expected


def test_an_unknown_locator_kind_is_refused() -> None:
    with pytest.raises(MetaGenerationError, match="unknown locator kind"):
        _locate({"kind": "quantum_position", "index": 1})


def test_a_binary_format_carrying_a_line_locator_is_refused() -> None:
    """`line 7` of a .docx names nothing an operator can open."""
    with pytest.raises(MetaGenerationError, match="has no lines"):
        _locate({"kind": "line_span", "line_start": 1, "line_end": 2}, document_format="docx")


@pytest.mark.parametrize(
    ("producer", "document_format"),
    [
        ({"kind": "docx_block", "part": "word/document.xml"}, "docx"),
        ({"kind": "docx_block", "block_index": 1}, "docx"),
        ({"kind": "pptx_shape", "shape_index": 1, "part": "ppt/slide1.xml"}, "pptx"),
        ({"kind": "pdf_page_block", "block_index": 1}, "pdf"),
        ({"kind": "notebook_cell", "cell_type": "code"}, "ipynb"),
        ({"kind": "spreadsheet_cell", "cell_or_range": "A1"}, "xlsx"),
        ({"kind": "html_node", "node_index": 1}, "html"),
        ({"kind": "csv_row"}, "csv"),
    ],
)
def test_a_locator_missing_a_required_field_is_refused(
    producer: dict[str, Any], document_format: str
) -> None:
    """A coordinate that was never taken, not a coordinate with a gap in it."""
    with pytest.raises(MetaGenerationError):
        _locate(producer, document_format=document_format)


@pytest.mark.parametrize(
    ("producer", "document_format"),
    [
        ({"kind": "pdf_page_block", "page_number": 0, "block_index": 1}, "pdf"),
        ({"kind": "pdf_page_block", "page_number": -1, "block_index": 1}, "pdf"),
        ({"kind": "pptx_shape", "slide_number": 0, "shape_index": 1, "part": "p"}, "pptx"),
        ({"kind": "csv_row", "row_number": 0}, "csv"),
        ({"kind": "spreadsheet_cell", "sheet": "", "cell_or_range": "A1"}, "xlsx"),
        ({"kind": "spreadsheet_cell", "sheet": "S", "cell_or_range": ""}, "xlsx"),
        ({"kind": "docx_block", "block_index": 1, "part": ""}, "docx"),
    ],
)
def test_an_out_of_range_or_empty_coordinate_is_refused(
    producer: dict[str, Any], document_format: str
) -> None:
    with pytest.raises(MetaGenerationError):
        _locate(producer, document_format=document_format)


def test_a_locator_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(MetaGenerationError, match="not an object"):
        _locate("line 7")


def test_a_notebook_cell_span_is_kept_when_the_producer_states_one() -> None:
    """A cell does have lines, so a span within one is a real coordinate."""
    located = _locate(
        {
            "kind": "notebook_cell",
            "cell_index": 2,
            "cell_type": "code",
            "line_start": 4,
            "line_end": 6,
        },
        document_format="ipynb",
    )
    assert located == {
        "kind": "notebook",
        "cell_index": 2,
        "cell_type": "code",
        "start_line": 4,
        "end_line": 6,
    }
