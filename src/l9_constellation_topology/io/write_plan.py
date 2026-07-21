"""Deterministic write planning and immutable commit receipts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.run.evidence import semantic_hash, utc_now

from .write_intent import WriteIntent

WriteAction = Literal["create", "replace", "skip"]


class WritePlanEntry(FrozenModel):
    intent: WriteIntent
    action: WriteAction
    existing_hash: str | None = None
    reason: str


class WritePlan(FrozenModel):
    plan_id: str
    entries: tuple[WritePlanEntry, ...]
    total_bytes: int = Field(ge=0)
    status: Literal["ready", "blocked"]
    issues: tuple[str, ...] = ()


class CommitArtifactResult(FrozenModel):
    logical_id: str
    destination_path: str
    status: Literal["written", "skipped", "failed"]
    content_hash: str
    message: str


class CommitReceipt(FrozenModel):
    packet_type: Literal["l9.commit-receipt"] = "l9.commit-receipt"
    packet_version: str = "1.0.0"
    receipt_id: str
    plan_id: str
    status: Literal["passed", "failed", "blocked"]
    results: tuple[CommitArtifactResult, ...]
    created_at: datetime = Field(default_factory=utc_now)
    semantic_hash: str


def make_write_plan(
    entries: tuple[WritePlanEntry, ...],
    *,
    issues: tuple[str, ...] = (),
) -> WritePlan:
    identity = {
        "entries": entries,
        "issues": issues,
    }
    digest = semantic_hash(identity)
    return WritePlan(
        plan_id=f"write-plan:{digest.removeprefix('sha256:')}",
        entries=entries,
        total_bytes=sum(len(entry.intent.artifact.content) for entry in entries),
        status="blocked" if issues else "ready",
        issues=issues,
    )


def make_commit_receipt(
    plan: WritePlan,
    results: tuple[CommitArtifactResult, ...],
    *,
    blocked: bool = False,
) -> CommitReceipt:
    status: Literal["passed", "failed", "blocked"]
    if blocked or plan.status == "blocked":
        status = "blocked"
    elif any(result.status == "failed" for result in results):
        status = "failed"
    else:
        status = "passed"
    candidate = CommitReceipt(
        receipt_id="receipt:pending",
        plan_id=plan.plan_id,
        status=status,
        results=results,
        semantic_hash="sha256:pending",
    )
    digest = semantic_hash(candidate)
    return candidate.model_copy(
        update={
            "receipt_id": f"receipt:{digest.removeprefix('sha256:')}",
            "semantic_hash": digest,
        }
    )
