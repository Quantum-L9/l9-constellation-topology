"""GitHub Actions worker and foundational transport adapters."""

from .errors import WorkerError
from .packet_store import PacketStoreClient
from .registry import LocalPacketRegistry, RegistryEntry
from .signature import (
    calculate_transport_packet_id,
    sign_transport_packet,
    transport_signing_view,
    verify_transport_packet,
)
from .stage_runner import StageExecutionOutcome, execute_stage, validate_stage_dispatch
from .transport_factory import build_callback_transport_packet, build_transport_packet

__all__ = [
    "LocalPacketRegistry",
    "PacketStoreClient",
    "RegistryEntry",
    "StageExecutionOutcome",
    "WorkerError",
    "build_callback_transport_packet",
    "build_transport_packet",
    "calculate_transport_packet_id",
    "execute_stage",
    "sign_transport_packet",
    "transport_signing_view",
    "validate_stage_dispatch",
    "verify_transport_packet",
]
