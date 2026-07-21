"""Explicit run-scoped signal plane."""

from __future__ import annotations

from pydantic import Field

from l9_constellation_topology.domain.assessment import ConflictRecord, UnknownRecord
from l9_constellation_topology.domain.base import StrictModel
from l9_constellation_topology.run.diagnostics import Diagnostic
from l9_constellation_topology.run.evidence import EvidenceRecord
from l9_constellation_topology.run.receipts import StageReceipt


class ArtifactState(StrictModel):
    logical_id: str
    status: str
    content_hash: str | None = None
    semantic_hash: str | None = None
    destination: str | None = None


class RunContext(StrictModel):
    run_id: str
    stage_id: str
    workflow_id: str
    trace_id: str
    compiler_version: str
    profile_id: str
    profile_hash: str
    source_snapshot_hash: str
    input_packet_refs: list[dict[str, str]] = Field(default_factory=list)
    artifacts: dict[str, ArtifactState] = Field(default_factory=dict)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    unknowns: list[UnknownRecord] = Field(default_factory=list)
    stage_receipts: list[StageReceipt] = Field(default_factory=list)
