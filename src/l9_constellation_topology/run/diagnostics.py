"""Run-scoped diagnostics."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel


class Diagnostic(FrozenModel):
    diagnostic_id: str
    stage: str
    severity: Literal["info", "warning", "error"]
    code: str
    message: str
    subject_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
