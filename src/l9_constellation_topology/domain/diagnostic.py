"""Canonical diagnostic records preserved across compiler stages."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .base import FrozenModel


class DiagnosticRecord(FrozenModel):
    diagnostic_id: str
    source_packet_id: str
    stage: str
    severity: Literal["info", "warning", "error"]
    code: str
    message: str
    category: str = "upstream"
    subject_id: str | None = None
    evidence_refs: tuple[str, ...] = ()
    disposition: Literal["preserved", "translated", "suppressed", "rejected"] = "preserved"
    details: dict[str, Any] = Field(default_factory=dict)
