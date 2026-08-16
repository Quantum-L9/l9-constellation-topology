"""Load, validate, and adapt Repository Model Packet inputs."""

from __future__ import annotations

from pathlib import Path

from l9_constellation_topology.packets.adapters import (
    NormalizedRepositoryModel,
    RepositoryModelV1Adapter,
)
from l9_constellation_topology.packets.loader import load_repository_model_packet
from l9_constellation_topology.packets.repository_model import RepositoryModelPacket


def ingest_paths(paths: tuple[Path, ...]) -> tuple[RepositoryModelPacket, ...]:
    if not paths:
        raise ValueError("at least one Repository Model Packet is required")
    return tuple(load_repository_model_packet(path) for path in paths)


def adapt_packets(
    packets: tuple[RepositoryModelPacket, ...],
) -> tuple[NormalizedRepositoryModel, ...]:
    # Dispatch on what the adapter declares it supports. Hardcoding a single version here
    # duplicated the contract and drifted from it: the adapter accepted 1.1.0 and the
    # validator permitted it, while this table still admitted only 1.0.0, so every
    # assertion-bearing packet was rejected as unsupported before reaching it.
    repository_model_v1 = RepositoryModelV1Adapter()
    adapters = {version: repository_model_v1 for version in repository_model_v1.supported_versions}
    normalized: list[NormalizedRepositoryModel] = []
    for packet in packets:
        adapter = adapters.get(packet.packet_version)
        if adapter is None:
            raise ValueError(
                f"unsupported Repository Model Packet version: {packet.packet_version}"
            )
        normalized.append(adapter.adapt(packet))
    return tuple(normalized)
