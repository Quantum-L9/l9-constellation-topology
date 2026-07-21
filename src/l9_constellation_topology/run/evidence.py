"""Canonical serialization, semantic hashing, and evidence value objects."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import Field, field_validator

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


class EvidenceSourceRef(FrozenModel):
    uri: str | None = None
    source_path: str | None = None
    line_number: int | None = Field(default=None, ge=1)
    content_hash: str | None = None
    packet_id: str | None = None
    source_revision: str | None = None

    @field_validator("source_path")
    @classmethod
    def source_path_is_portable(cls, value: str | None) -> str | None:
        return normalize_source_path(value) if value is not None else None


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
