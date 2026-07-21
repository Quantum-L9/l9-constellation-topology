"""Build signed TransportPacket messages without introducing a second wire shape."""

from __future__ import annotations

from typing import Any, Literal

from l9_constellation_topology.packets.transport import (
    TransportAttachment,
    TransportHeader,
    TransportPacket,
)
from l9_constellation_topology.run import semantic_hash

from .signature import sign_transport_packet


def build_transport_packet(
    *,
    payload: object,
    packet_type: Literal["command", "event", "result", "failure"],
    action: str,
    idempotency_key: str,
    trace_id: str,
    correlation_id: str,
    workflow_id: str | None,
    key: bytes,
    key_id: str,
    provenance: dict[str, Any] | None = None,
    governance: dict[str, Any] | None = None,
    attachments: tuple[TransportAttachment, ...] = (),
) -> TransportPacket:
    payload_data = (
        payload.model_dump(mode="json", exclude_none=True)
        if hasattr(payload, "model_dump")
        else payload
    )
    if not isinstance(payload_data, dict):
        raise TypeError("TransportPacket payload must serialize to a mapping")
    draft = TransportPacket(
        header=TransportHeader(
            packet_id="packet:pending",
            packet_type=packet_type,
            action=action,
            schema_version="transport-packet/1.0.0",
            idempotency_key=idempotency_key,
            trace_id=trace_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
        ),
        provenance=provenance or {},
        governance=governance or {},
        attachments=attachments,
        payload=payload_data,
    )
    return sign_transport_packet(draft, key=key, key_id=key_id)


def build_callback_transport_packet(
    request: TransportPacket,
    payload: object,
    *,
    key: bytes,
    key_id: str,
) -> TransportPacket:
    payload_schema = str(getattr(payload, "payload_schema", "unknown"))
    if payload_schema == "l9.execution-failure/1.0.0":
        packet_type: Literal["result", "failure"] = "failure"
        action = "topology-stage-failed"
    elif payload_schema == "l9.reuse-receipt/1.0.0":
        packet_type = "result"
        action = "topology-stage-reused"
    else:
        packet_type = "result"
        action = "topology-stage-succeeded"
    callback_idempotency = semantic_hash(
        {
            "request_packet_id": request.header.packet_id,
            "payload": payload,
            "action": action,
        }
    )
    return build_transport_packet(
        payload=payload,
        packet_type=packet_type,
        action=action,
        idempotency_key=callback_idempotency,
        trace_id=request.header.trace_id,
        correlation_id=request.header.correlation_id,
        workflow_id=request.header.workflow_id,
        key=key,
        key_id=key_id,
        provenance={
            "resolved_by_gate": False,
            "resolver": "l9-constellation-topology",
            "parent_packet_id": request.header.packet_id,
        },
        governance=request.governance,
    )
