"""Explicit topology validation stage."""

from datetime import datetime
from pathlib import Path

from l9_constellation_topology.domain import TopologyState
from l9_constellation_topology.packets.loader import RepositoryModelBundle
from l9_constellation_topology.packets.topology_packet import TopologyPacket
from l9_constellation_topology.packets.validation_receipt import ValidationReceipt
from l9_constellation_topology.validation.topology_validator import validate_topology


def run(
    packet: TopologyPacket,
    state: TopologyState,
    input_bundles: tuple[RepositoryModelBundle, ...],
    *,
    schema_root: Path,
    created_at: datetime | None = None,
) -> ValidationReceipt:
    return validate_topology(
        packet,
        state,
        input_bundles,
        schema_root=schema_root,
        created_at=created_at,
    )
