"""Reading Meta's complete document-work-signal payload.

The producer emits two documents about the same claims, and only one of them is
a machine contract.

``document-signals.json`` is a **report**. Its per-format ``records`` array is
capped, and it says so: ``signal_count`` is what the corpus found,
``listed_signal_count`` is what the array holds, and ``omitted_signal_count`` is
the difference. Adapting it would produce a topology that conserved its signal
count perfectly against a number that was never the total.

``document-work-signals.jsonl`` is the **payload**: one line per signal, never
sampled, never truncated, with ``document-work-signals.manifest.json`` beside it
carrying the count and the hashes. This module reads the payload and refuses it
unless the manifest's own arithmetic checks out, because a payload that arrives
without a verified count is a payload whose losses are invisible.

Nothing here guesses. Every locator is the coordinate the producer stated,
translated in field naming only; a record the producer did not locate is a
record this module refuses rather than places.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from l9_constellation_topology.run.evidence import canonical_json, sha256_bytes, sha256_text

from .errors import MetaGenerationError

__all__ = [
    "DOCUMENT_WORK_SIGNALS_FILE",
    "DOCUMENT_WORK_SIGNALS_MANIFEST_FILE",
    "DOCUMENT_WORK_SIGNALS_MANIFEST_SCHEMA",
    "DOCUMENT_WORK_SIGNALS_SCHEMA",
    "LOCATOR_KIND_BY_PRODUCER_KIND",
    "WorkSignalPayload",
    "load_work_signal_payload",
    "translate_locator",
]

#: Generation-relative name of the complete payload.
DOCUMENT_WORK_SIGNALS_FILE = "document-work-signals.jsonl"

#: Generation-relative name of the manifest describing that payload.
DOCUMENT_WORK_SIGNALS_MANIFEST_FILE = "document-work-signals.manifest.json"

#: The exact payload schema this reader supports.
DOCUMENT_WORK_SIGNALS_SCHEMA = "l9.document-work-signals/v1"

#: The exact manifest schema this reader supports.
DOCUMENT_WORK_SIGNALS_MANIFEST_SCHEMA = "l9.document-work-signals-manifest/v1"

#: The producer's locator vocabulary, mapped to this compiler's.
#:
#: A rename and nothing more. Both sides name the same coordinate systems, and
#: neither entry here converts one coordinate into another: the whole point of
#: the structured locator is that a page is not a line and cannot be turned into
#: one.
LOCATOR_KIND_BY_PRODUCER_KIND: dict[str, str] = {
    "line_span": "line",
    "notebook_cell": "notebook",
    "pdf_page_block": "pdf",
    "docx_block": "docx",
    "pptx_shape": "pptx",
    "spreadsheet_cell": "spreadsheet",
    "csv_row": "csv",
    "html_node": "html",
}

#: Formats whose decoded text has lines an operator can open the file and find.
LINE_BEARING_FORMATS: frozenset[str] = frozenset({"text", "markdown", "csv", "html", "ipynb"})


@dataclass(frozen=True)
class WorkSignalPayload:
    """A verified payload: the records, and the manifest that vouched for them."""

    records: tuple[dict[str, Any], ...]
    manifest: dict[str, Any]

    @property
    def record_count(self) -> int:
        return len(self.records)


def _require_int(container: dict[str, Any], key: str, *, minimum: int, context: str) -> int:
    value = container.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise MetaGenerationError(f"{context}: {key} is not an integer")
    if value < minimum:
        raise MetaGenerationError(f"{context}: {key} is {value}, below the minimum of {minimum}")
    return value


def _require_text(container: dict[str, Any], key: str, *, context: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        raise MetaGenerationError(f"{context}: {key} is missing or empty")
    return value


def translate_locator(
    raw: Any, *, document_format: str, block_kind: str, context: str
) -> dict[str, Any]:
    """Return the producer's coordinate in this compiler's field naming.

    Refuses rather than repairs. A locator missing a field its own kind requires
    is not a locator with a gap in it — it is a coordinate that was never taken,
    and a consumer cannot tell a defaulted ordinal from a real one afterwards.
    """
    if not isinstance(raw, dict):
        raise MetaGenerationError(f"{context}: structured_locator is not an object")
    producer_kind = raw.get("kind")
    if not isinstance(producer_kind, str) or producer_kind not in LOCATOR_KIND_BY_PRODUCER_KIND:
        raise MetaGenerationError(f"{context}: unknown locator kind {producer_kind!r}")
    kind = LOCATOR_KIND_BY_PRODUCER_KIND[producer_kind]

    if kind == "line" and document_format not in LINE_BEARING_FORMATS:
        raise MetaGenerationError(
            f"{context}: a {document_format} document carries a line locator; "
            "that format has no lines, so the coordinate names nothing openable"
        )

    if kind == "line":
        return {
            "kind": "line",
            "start_line": _require_int(raw, "line_start", minimum=1, context=context),
            "end_line": _require_int(raw, "line_end", minimum=1, context=context),
        }
    if kind == "notebook":
        located: dict[str, Any] = {
            "kind": "notebook",
            "cell_index": _require_int(raw, "cell_index", minimum=0, context=context),
            "cell_type": _require_text(raw, "cell_type", context=context),
        }
        # A cell does have lines, so a span within one is a real coordinate. It
        # is optional because the producer cites some cells whole.
        if raw.get("line_start") is not None:
            located["start_line"] = _require_int(raw, "line_start", minimum=1, context=context)
        if raw.get("line_end") is not None:
            located["end_line"] = _require_int(raw, "line_end", minimum=1, context=context)
        return located
    if kind == "pdf":
        return {
            "kind": "pdf",
            "page_number": _require_int(raw, "page_number", minimum=1, context=context),
            "block_index": _require_int(raw, "block_index", minimum=0, context=context),
        }
    if kind == "docx":
        return {
            "kind": "docx",
            "block_index": _require_int(raw, "block_index", minimum=0, context=context),
            # The producer carries the block's kind on the record rather than in
            # the locator; both describe the same block.
            "block_kind": block_kind,
            "part": _require_text(raw, "part", context=context),
        }
    if kind == "pptx":
        return {
            "kind": "pptx",
            "slide_number": _require_int(raw, "slide_number", minimum=1, context=context),
            "shape_index": _require_int(raw, "shape_index", minimum=0, context=context),
            "part": _require_text(raw, "part", context=context),
        }
    if kind == "spreadsheet":
        return {
            "kind": "spreadsheet",
            "sheet": _require_text(raw, "sheet", context=context),
            "cell_or_range": _require_text(raw, "cell_or_range", context=context),
        }
    if kind == "csv":
        row: dict[str, Any] = {
            "kind": "csv",
            "row": _require_int(raw, "row_number", minimum=1, context=context),
        }
        column = raw.get("column")
        if isinstance(column, str) and column:
            row["column"] = column
        return row
    return {
        "kind": "html",
        "stable_node_index": _require_int(raw, "node_index", minimum=0, context=context),
        "node_path": _require_text(raw, "node_path", context=context),
    }


def _read_manifest(root: Path) -> dict[str, Any]:
    path = root / DOCUMENT_WORK_SIGNALS_MANIFEST_FILE
    if not path.is_file():
        raise MetaGenerationError(
            f"the generation at {root} declares a complete work-signal payload but is "
            f"missing {DOCUMENT_WORK_SIGNALS_MANIFEST_FILE}; an unmanifested payload "
            "cannot be checked for completeness"
        )
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MetaGenerationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise MetaGenerationError(f"{path} is not an object")
    schema = manifest.get("schema")
    if schema != DOCUMENT_WORK_SIGNALS_MANIFEST_SCHEMA:
        raise MetaGenerationError(
            f"{DOCUMENT_WORK_SIGNALS_MANIFEST_FILE} declares schema {schema!r}; "
            f"this reader supports exactly {DOCUMENT_WORK_SIGNALS_MANIFEST_SCHEMA!r}"
        )
    declared_file = manifest.get("payload_file")
    if declared_file != DOCUMENT_WORK_SIGNALS_FILE:
        raise MetaGenerationError(
            f"the manifest describes payload_file {declared_file!r}, not "
            f"{DOCUMENT_WORK_SIGNALS_FILE!r}"
        )
    return manifest


def _parse_payload(path: Path, payload_text: str) -> tuple[dict[str, Any], ...]:
    """Parse every line, naming the exact line that failed.

    A duplicate ``signal_id`` is refused rather than collapsed: two records
    under one id are either one record written twice or two claims sharing an
    identity, and the payload gives no way to tell which.
    """
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for number, line in enumerate(payload_text.splitlines(), start=1):
        if not line.strip():
            raise MetaGenerationError(
                f"{path} line {number} is blank; the payload is one record per line"
            )
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MetaGenerationError(f"{path} line {number} did not parse: {exc}") from exc
        if not isinstance(record, dict):
            raise MetaGenerationError(f"{path} line {number} is not an object")
        signal_id = record.get("signal_id")
        if not isinstance(signal_id, str) or not signal_id:
            raise MetaGenerationError(f"{path} line {number} carries no signal_id")
        if signal_id in seen:
            raise MetaGenerationError(
                f"{path} line {number} repeats signal_id {signal_id!r}; "
                "two records under one identity cannot both be kept"
            )
        seen.add(signal_id)
        records.append(record)
    return tuple(records)


def _tally(records: tuple[dict[str, Any], ...], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = record.get(key)
        if isinstance(value, str):
            counts[value] = counts.get(value, 0) + 1
    return counts


def _check_declared_counts(manifest: dict[str, Any], records: tuple[dict[str, Any], ...]) -> None:
    """Check every count the manifest chose to declare.

    Declared counts are checked because they are checkable. A manifest that
    states a per-format breakdown and disagrees with its own payload is not a
    manifest with a cosmetic error: whichever of the two is wrong, the payload's
    completeness is no longer something the manifest can vouch for.
    """
    declared_documents = manifest.get("document_count")
    if isinstance(declared_documents, int) and not isinstance(declared_documents, bool):
        observed = len({record.get("artifact_id") for record in records})
        if observed != declared_documents:
            raise MetaGenerationError(
                f"manifest declares {declared_documents} document(s) and the payload "
                f"carries signals from {observed}"
            )

    for field_name, record_key, count_key in (
        ("by_format", "format", "signal_count"),
        ("by_predicate", "predicate", "signal_count"),
    ):
        declared = manifest.get(field_name)
        if not isinstance(declared, list):
            continue
        observed_counts = _tally(records, record_key)
        for entry in declared:
            if not isinstance(entry, dict):
                raise MetaGenerationError(f"manifest {field_name} carries a non-object entry")
            name = entry.get(record_key)
            expected = entry.get(count_key)
            if not isinstance(name, str) or not isinstance(expected, int):
                raise MetaGenerationError(f"manifest {field_name} entry is not well formed")
            actual = observed_counts.pop(name, 0)
            if actual != expected:
                raise MetaGenerationError(
                    f"manifest {field_name} declares {expected} signal(s) for {name!r} "
                    f"and the payload carries {actual}"
                )
        if observed_counts:
            extra = ", ".join(sorted(observed_counts))
            raise MetaGenerationError(
                f"the payload carries {record_key}(s) the manifest {field_name} does not "
                f"declare: {extra}"
            )


def load_work_signal_payload(root: Path) -> WorkSignalPayload:
    """Read and verify the complete payload, or refuse the generation.

    Verification is done by recomputation rather than by reading the manifest's
    own claims back to it: the byte length, the artifact hash over the exact
    bytes, and the semantic hash over the records are each recalculated here
    under the producer's own definitions. A manifest that merely *contains* a
    hash proves nothing; one whose hash this reader can reproduce proves the
    payload arrived as it left.
    """
    manifest = _read_manifest(root)
    path = root / DOCUMENT_WORK_SIGNALS_FILE
    if not path.is_file():
        raise MetaGenerationError(
            f"the generation at {root} carries {DOCUMENT_WORK_SIGNALS_MANIFEST_FILE} but "
            f"no {DOCUMENT_WORK_SIGNALS_FILE}; the manifest describes a payload that is "
            "not there"
        )
    try:
        payload_bytes = path.read_bytes()
    except OSError as exc:
        raise MetaGenerationError(f"cannot read {path}: {exc}") from exc

    byte_length = _require_int(manifest, "payload_byte_length", minimum=0, context="manifest")
    if len(payload_bytes) != byte_length:
        raise MetaGenerationError(
            f"manifest says the payload is {byte_length} byte(s) and it is {len(payload_bytes)}"
        )

    artifact_hash = sha256_bytes(payload_bytes)
    declared_artifact_hash = _require_text(manifest, "payload_artifact_hash", context="manifest")
    if artifact_hash != declared_artifact_hash:
        raise MetaGenerationError(
            f"payload artifact hash is {artifact_hash} and the manifest declares "
            f"{declared_artifact_hash}"
        )

    try:
        payload_text = payload_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MetaGenerationError(f"{path} is not UTF-8: {exc}") from exc

    records = _parse_payload(path, payload_text)

    declared_count = _require_int(manifest, "record_count", minimum=0, context="manifest")
    if len(records) != declared_count:
        raise MetaGenerationError(
            f"manifest declares {declared_count} record(s) and the payload parsed to {len(records)}"
        )

    # Over the records rather than the bytes, so a generation copied to another
    # directory still verifies.
    semantic_hash = sha256_text(
        canonical_json({"schema": DOCUMENT_WORK_SIGNALS_SCHEMA, "records": list(records)})
    )
    declared_semantic_hash = _require_text(manifest, "payload_semantic_hash", context="manifest")
    if semantic_hash != declared_semantic_hash:
        raise MetaGenerationError(
            f"payload semantic hash is {semantic_hash} and the manifest declares "
            f"{declared_semantic_hash}"
        )

    _check_declared_counts(manifest, records)
    return WorkSignalPayload(records=records, manifest=manifest)
