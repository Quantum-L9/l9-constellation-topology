"""Canonical serialization, semantic hashing, and evidence value objects."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.domain.confidence import ConfidenceAssessment

_SHA_PREFIX = "sha256:"
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonical_data(value: Any) -> Any:
    """Convert supported objects into deterministic JSON-compatible data."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {str(key): canonical_data(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [canonical_data(item) for item in value]
    if isinstance(value, set | frozenset):
        return sorted(
            (canonical_data(item) for item in value), key=lambda item: canonical_json(item)
        )
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        canonical_data(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return _SHA_PREFIX + hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def semantic_hash(value: Any, *, excluded_fields: set[str] | None = None) -> str:
    """Hash semantic data after recursively removing volatile fields."""
    excluded = excluded_fields or {
        "created_at",
        "checked_at",
        "generated_at",
        "committed_at",
        "frozen_at",
        "run_id",
        "stage_id",
        "trace_id",
        "workflow_id",
        "artifact_hash",
        "semantic_hash",
        "packet_id",
        "receipt_id",
    }

    def strip(item: Any) -> Any:
        item = canonical_data(item)
        if isinstance(item, dict):
            return {key: strip(value) for key, value in item.items() if key not in excluded}
        if isinstance(item, list):
            return [strip(value) for value in item]
        return item

    return sha256_bytes(canonical_bytes(strip(value)))


def artifact_hash(content: bytes) -> str:
    return sha256_bytes(content)


def normalize_source_path(path: str, *, repository_root: Path | None = None) -> str:
    """Return a portable relative POSIX path and reject path escape."""
    raw = path.replace("\\", "/")
    if repository_root is not None:
        candidate = Path(path)
        if candidate.is_absolute():
            try:
                raw = candidate.resolve().relative_to(repository_root.resolve()).as_posix()
            except ValueError as exc:
                raise ValueError(f"source path escapes repository root: {path}") from exc
    if raw.startswith("/") or _WINDOWS_ABSOLUTE.match(raw):
        raise ValueError(f"absolute source path is not canonical: {path}")
    normalized = PurePosixPath(raw).as_posix()
    if normalized in {"", "."}:
        return "."
    if normalized == ".." or normalized.startswith("../"):
        raise ValueError(f"source path escapes repository root: {path}")
    return normalized


def stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}:{semantic_hash(value).removeprefix(_SHA_PREFIX)}"


class LineLocator(FrozenModel):
    """A 1-based inclusive line span, for a format that has lines."""

    kind: Literal["line"] = "line"
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class PdfLocator(FrozenModel):
    """A block on a page. A PDF page is not a line and has no line numbers."""

    kind: Literal["pdf"] = "pdf"
    page_number: int = Field(ge=1)
    block_index: int = Field(ge=0)


class DocxLocator(FrozenModel):
    """A block within a Word document body, by ordinal and block kind."""

    kind: Literal["docx"] = "docx"
    block_index: int = Field(ge=0)
    block_kind: str
    #: The OPC part the block was read from, e.g. ``word/document.xml``. A Word
    #: file is several XML parts and block 3 of the body is not block 3 of a
    #: footnote, so the ordinal alone does not identify the block.
    part: str = ""


class PptxLocator(FrozenModel):
    """A shape on a slide."""

    kind: Literal["pptx"] = "pptx"
    slide_number: int = Field(ge=1)
    shape_index: int = Field(ge=0)
    #: The OPC part the shape was read from. Same reason as ``DocxLocator``:
    #: a notes slide and its slide carry independent shape ordinals.
    part: str = ""


class SpreadsheetLocator(FrozenModel):
    """A cell or range on a named sheet, in the workbook's own A1 vocabulary."""

    kind: Literal["spreadsheet"] = "spreadsheet"
    sheet: str
    cell_or_range: str


class NotebookLocator(FrozenModel):
    """A notebook cell by ordinal and declared cell type."""

    kind: Literal["notebook"] = "notebook"
    cell_index: int = Field(ge=0)
    cell_type: str
    #: A cell does have lines, so a span *within* the cell is a real coordinate
    #: rather than an invented one. Absent when the producer cited the cell
    #: whole.
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)


class CsvLocator(FrozenModel):
    """A row of a delimited file."""

    kind: Literal["csv"] = "csv"
    row: int = Field(ge=1)
    #: The named column, when the claim was read from one cell rather than the
    #: whole row.
    column: str | None = None


class HtmlLocator(FrozenModel):
    """A node, by an index stable under the producer's own traversal order."""

    kind: Literal["html"] = "html"
    stable_node_index: int = Field(ge=0)
    #: The element path the index was counted along. The index is stable only
    #: relative to a traversal; the path is what a reader can actually follow.
    node_path: str = ""


#: Where a piece of evidence sits, in the coordinate system its format has.
#:
#: A Markdown file has lines. A slide deck has slides and shapes; a workbook has
#: sheets and cells; a PDF has pages and blocks within them. None of those is a
#: line number, and flattening one into a line number does not lose precision so
#: much as invent it: ``line 7`` of a ``.docx`` names nothing an operator can
#: open. The union keeps each format's true coordinates, so evidence that cannot
#: honestly cite a line simply does not.
SourceLocator = Annotated[
    LineLocator
    | PdfLocator
    | DocxLocator
    | PptxLocator
    | SpreadsheetLocator
    | NotebookLocator
    | CsvLocator
    | HtmlLocator,
    Field(discriminator="kind"),
]

#: Locator kinds that name a line span. Everything else is a structured
#: coordinate, and a signal decoded from such a format may never carry a line.
LINE_LOCATOR_KINDS: frozenset[str] = frozenset({"line"})


class EvidenceSourceRef(FrozenModel):
    uri: str | None = None
    source_path: str | None = None
    line_number: int | None = Field(default=None, ge=1)
    content_hash: str | None = None
    packet_id: str | None = None
    source_revision: str | None = None
    #: The structured coordinate this evidence was read at, when the producer
    #: reported one. ``None`` for evidence that carries only ``line_number``,
    #: which is every repository-model assertion emitted before locators existed.
    locator: SourceLocator | None = None

    @field_validator("source_path")
    @classmethod
    def source_path_is_portable(cls, value: str | None) -> str | None:
        return normalize_source_path(value) if value is not None else None

    @model_validator(mode="after")
    def line_number_agrees_with_locator(self) -> EvidenceSourceRef:
        """Refuse a line number that contradicts the structured coordinate.

        A line locator may also project to ``line_number`` — that is how a 1.1.0
        repository-model assertion keeps working unchanged. What is refused is a
        line number beside a *structured* locator: it would let a consumer that
        reads only ``line_number`` believe a Word document has lines, which is
        the exact confusion the locator union exists to prevent.
        """
        if self.locator is None:
            return self
        if not isinstance(self.locator, LineLocator):
            if self.line_number is not None:
                raise ValueError(
                    "evidence located by a structured "
                    f"{self.locator.kind!r} coordinate cannot also carry a line number; "
                    "the format has no lines to number"
                )
            return self
        if self.line_number is not None and self.line_number != self.locator.start_line:
            raise ValueError(
                "line_number must equal the line locator's start_line: "
                f"{self.line_number} != {self.locator.start_line}"
            )
        return self


EvidenceClass = Literal[
    "observed",
    "declared",
    "derived",
    "assisted",
    "projected",
    "validated",
    "committed",
]
EvidenceSourceType = Literal["file", "packet", "inference", "validation", "unknown"]


class EvidenceRecord(FrozenModel):
    evidence_id: str
    subject_id: str
    field: str | None = None
    stage: str
    evidence_class: EvidenceClass
    source_type: EvidenceSourceType
    source_ref: EvidenceSourceRef
    value: Any
    confidence: ConfidenceAssessment
    producer: str
    producer_version: str
    created_at: datetime = Field(default_factory=utc_now)


def make_evidence_record(
    *,
    subject_id: str,
    field: str | None,
    stage: str,
    evidence_class: EvidenceClass,
    source_type: EvidenceSourceType,
    source_ref: EvidenceSourceRef,
    value: Any,
    confidence: ConfidenceAssessment,
    producer: str,
    producer_version: str,
    created_at: datetime | None = None,
) -> EvidenceRecord:
    identity = {
        "subject_id": subject_id,
        "field": field,
        "stage": stage,
        "evidence_class": evidence_class,
        "source_type": source_type,
        "source_ref": source_ref,
        "value": value,
        "producer": producer,
        "producer_version": producer_version,
    }
    return EvidenceRecord(
        evidence_id=stable_id("evidence", identity),
        subject_id=subject_id,
        field=field,
        stage=stage,
        evidence_class=evidence_class,
        source_type=source_type,
        source_ref=source_ref,
        value=value,
        confidence=confidence,
        producer=producer,
        producer_version=producer_version,
        created_at=created_at or utc_now(),
    )
