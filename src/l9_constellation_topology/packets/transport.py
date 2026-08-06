"""TransportPacket worker view and stage payload contracts.

This module validates the canonical TransportPacket shape required by this repository. It does
not introduce an alternative envelope or replace the platform transport implementation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel

from .refs import PacketRef


class TransportHeader(FrozenModel):
    packet_id: str
    packet_type: Literal["command", "event", "result", "failure"]
    action: str
    schema_version: str
    idempotency_key: str
    trace_id: str
    correlation_id: str
    workflow_id: str | None = None
    created_at: datetime | None = None


class TransportAttachment(FrozenModel):
    attachment_id: str
    uri: str
    media_type: str
    content_hash: str
    size_bytes: int
    encrypted: bool = False


class TransportSignature(FrozenModel):
    algorithm: str
    key_id: str
    value: str


class TransportSecurity(FrozenModel):
    signatures: tuple[TransportSignature, ...] = ()


class TransportPacket(FrozenModel):
    header: TransportHeader
    provenance: dict[str, Any] = Field(default_factory=dict)
    governance: dict[str, Any] = Field(default_factory=dict)
    security: TransportSecurity = Field(default_factory=TransportSecurity)
    attachments: tuple[TransportAttachment, ...] = ()
    payload: dict[str, Any]


class CallbackRef(FrozenModel):
    callback_id: str


class StageProfileRef(FrozenModel):
    id: str
    version: str
    hash: str


class StageDispatchData(FrozenModel):
    run_id: str
    stage_id: str
    workflow_id: str
    action: Literal["compile-topology"]
    target_repository: str
    target_revision: str
    input_packets: tuple[PacketRef, ...]
    profile: StageProfileRef
    callback: CallbackRef | None = None
    output_uri: str | None = None


class StageDispatchPayload(FrozenModel):
    payload_schema: Literal["l9.stage-dispatch/1.0.0"] = "l9.stage-dispatch/1.0.0"
    data: StageDispatchData
