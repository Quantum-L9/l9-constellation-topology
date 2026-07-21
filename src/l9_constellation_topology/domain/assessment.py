"""Impact, risk, maturity, unknown, and conflict records."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import FrozenModel


class RiskRecord(FrozenModel):
    risk_id: str
    subject_id: str
    severity: Literal["low", "medium", "high", "critical"]
    category: str
    description: str
    rule_id: str
    rule_version: str
    evidence_refs: tuple[str, ...] = ()
    remediation: str | None = None
    status: Literal["open", "accepted", "mitigated", "resolved"] = "open"


class MaturityAssessment(FrozenModel):
    subject_id: str
    profile_id: str
    profile_version: str
    score: int = Field(ge=0)
    maximum_score: int = Field(gt=0)
    band: str
    dimensions: dict[str, int] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()


class ImpactIndex(FrozenModel):
    subject_id: str
    direction: Literal["upstream", "downstream", "both"]
    maximum_depth: int = Field(ge=0)
    affected_entity_ids: tuple[str, ...] = ()
    paths: tuple[tuple[str, ...], ...] = ()
    unresolved_edge_ids: tuple[str, ...] = ()
    affected_repository_ids: tuple[str, ...] = ()
    affected_capability_ids: tuple[str, ...] = ()


class UnknownRecord(FrozenModel):
    unknown_id: str
    subject_id: str
    field: str | None = None
    reason: str
    evidence_refs: tuple[str, ...] = ()


class ConflictRecord(FrozenModel):
    conflict_id: str
    subject_id: str
    field: str
    values: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()
    blocking: bool = False
    resolution: str | None = None
