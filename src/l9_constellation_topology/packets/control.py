"""Typed control-plane payloads carried inside canonical TransportPacket messages."""

from __future__ import annotations

from typing import Literal

from l9_constellation_topology.domain.base import FrozenModel

from .refs import PacketRef
from .transport import CallbackRef, StageProfileRef


class GitHubIngressData(FrozenModel):
    event_name: str
    target_repository: str
    target_revision: str
    action: Literal["compile-topology"] = "compile-topology"
    profile: StageProfileRef
    callback: CallbackRef | None = None


class GitHubIngressPayload(FrozenModel):
    payload_schema: Literal["l9.github-ingress/1.0.0"] = "l9.github-ingress/1.0.0"
    data: GitHubIngressData


class ReplayRequestData(FrozenModel):
    run_id: str
    stage_id: str
    packet_id: str
    reason: str
    dry_run: bool = False


class ReplayRequestPayload(FrozenModel):
    payload_schema: Literal["l9.replay-request/1.0.0"] = "l9.replay-request/1.0.0"
    data: ReplayRequestData


class RenderRequestData(FrozenModel):
    run_id: str
    stage_id: str
    source_packet: PacketRef
    report_profile_id: str
    report_profile_version: str
    output_uri: str
    callback: CallbackRef | None = None


class RenderRequestPayload(FrozenModel):
    payload_schema: Literal["l9.render-request/1.0.0"] = "l9.render-request/1.0.0"
    data: RenderRequestData


class ValidationRequestData(FrozenModel):
    run_id: str
    stage_id: str
    subject_packet: PacketRef
    callback: CallbackRef | None = None


class ValidationRequestPayload(FrozenModel):
    payload_schema: Literal["l9.validation-request/1.0.0"] = "l9.validation-request/1.0.0"
    data: ValidationRequestData


class RenderResult(FrozenModel):
    payload_schema: Literal["l9.render-result/1.0.0"] = "l9.render-result/1.0.0"
    run_id: str
    stage_id: str
    status: Literal["succeeded"] = "succeeded"
    source_packet_id: str
    report_manifest_uri: str
    commit_receipt_uri: str
