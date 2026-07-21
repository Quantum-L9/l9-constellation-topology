"""Topology Packet and materialized payload contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.run.evidence import semantic_hash, utc_now

from .common import PacketLineage, PacketValidationRef, Producer, ProfileRef
from .refs import PacketRef


class TopologyInputs(FrozenModel):
    repository_model_packets: tuple[PacketRef, ...]


class TopologyPacket(FrozenModel):
    packet_type: Literal["l9.topology"] = "l9.topology"
    packet_version: str = "1.0.0"
    packet_id: str
    producer: Producer
    profile: ProfileRef
    inputs: TopologyInputs
    schema_hash: str
    policy_hashes: dict[str, str] = Field(default_factory=dict)
    payload_refs: dict[str, str]
    payload_hashes: dict[str, str]
    validation: PacketValidationRef
    semantic_hash: str
    artifact_hash: str
    lineage: PacketLineage = Field(default_factory=PacketLineage)
    created_at: datetime = Field(default_factory=utc_now)


class MaterializedTopology(FrozenModel):
    packet: TopologyPacket
    state: TopologyState


def topology_packet_semantic_view(packet: TopologyPacket) -> dict[str, object]:
    """Return exactly the fields that define immutable topology meaning."""
    return {
        "packet_type": packet.packet_type,
        "packet_version": packet.packet_version,
        "producer": packet.producer,
        "profile": packet.profile,
        "inputs": packet.inputs,
        "schema_hash": packet.schema_hash,
        "policy_hashes": packet.policy_hashes,
        "payload_refs": packet.payload_refs,
        "payload_hashes": packet.payload_hashes,
        "lineage": packet.lineage,
    }


def calculate_topology_semantic_hash(packet: TopologyPacket) -> str:
    return semantic_hash(topology_packet_semantic_view(packet))
