"""Diagnostic normalization for the run-scoped signal plane."""

from __future__ import annotations

from typing import Literal

from l9_constellation_topology.domain.diagnostic import DiagnosticRecord

from .evidence import canonical_data, stable_id

Diagnostic = DiagnosticRecord


def normalize_diagnostic(
    raw: dict[str, object],
    *,
    source_packet_id: str,
    index: int,
) -> DiagnosticRecord:
    """Convert a version-tolerant upstream diagnostic into the canonical record."""

    severity_value = str(raw.get("severity", "warning")).lower()
    severity: Literal["info", "warning", "error"] = (
        severity_value  # type: ignore[assignment]
        if severity_value in {"info", "warning", "error"}
        else "warning"
    )

    code = str(raw.get("code", "upstream-diagnostic"))
    message = str(raw.get("message", "Upstream repository analysis emitted a diagnostic."))
    stage = str(raw.get("stage", "repository-model"))
    subject_value = raw.get("subject_id")
    subject_id = str(subject_value) if subject_value is not None else None
    evidence_value = raw.get("evidence_refs", ())
    evidence_refs = (
        tuple(sorted(str(value) for value in evidence_value))
        if isinstance(evidence_value, (list, tuple, set))
        else ()
    )
    identity = {
        "source_packet_id": source_packet_id,
        "index": index,
        "stage": stage,
        "severity": severity,
        "code": code,
        "message": message,
        "subject_id": subject_id,
        "raw": canonical_data(raw),
    }
    diagnostic_id = str(raw.get("diagnostic_id") or stable_id("diagnostic", identity))
    return DiagnosticRecord(
        diagnostic_id=diagnostic_id,
        source_packet_id=source_packet_id,
        stage=stage,
        severity=severity,
        code=code,
        message=message,
        category=str(raw.get("category", "upstream")),
        subject_id=subject_id,
        evidence_refs=evidence_refs,
        disposition="preserved",
        details={"raw": canonical_data(raw)},
    )
