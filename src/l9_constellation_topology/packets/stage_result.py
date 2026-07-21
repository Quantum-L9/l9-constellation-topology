"""Worker result, failure, and reuse payload contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.run.evidence import utc_now

from .refs import PacketRef


class StageResult(FrozenModel):
    payload_schema: Literal["l9.stage-result/1.0.0"] = "l9.stage-result/1.0.0"
    run_id: str
    stage_id: str
    status: Literal["succeeded"] = "succeeded"
    output_packet: PacketRef
    validation_receipt_uri: str
    commit_receipt_uri: str
    idempotency_key: str
    completed_at: datetime = Field(default_factory=utc_now)


class ExecutionFailure(FrozenModel):
    payload_schema: Literal["l9.execution-failure/1.0.0"] = "l9.execution-failure/1.0.0"
    run_id: str
    stage_id: str
    status: Literal["failed", "blocked"]
    error_class: str
    message: str
    retryable: bool
    input_packet_ids: tuple[str, ...] = ()
    failed_at: datetime = Field(default_factory=utc_now)


class ReuseReceipt(FrozenModel):
    payload_schema: Literal["l9.reuse-receipt/1.0.0"] = "l9.reuse-receipt/1.0.0"
    idempotency_key: str
    reused_packet: PacketRef
    reason: str = "validated packet already registered for identical semantic inputs"
    created_at: datetime = Field(default_factory=utc_now)
