"""Explicit topology validation stage."""

from l9_constellation_topology.domain import TopologyState
from l9_constellation_topology.packets.loader import RepositoryModelBundle
from l9_constellation_topology.packets.topology_packet import TopologyPacket
from l9_constellation_topology.packets.validation_receipt import ValidationReceipt
from l9_constellation_topology.validation.topology_validator import validate_topology


def run(
    packet: TopologyPacket,
    state: TopologyState,
    input_bundles: tuple[RepositoryModelBundle, ...],
) -> ValidationReceipt:
    return validate_topology(packet, state, input_bundles)
