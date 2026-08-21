"""GitHub Actions worker and foundational transport adapters."""

from .errors import WorkerError
from .execution_authority import (
    AcquireOutcome,
    ExecutionAuthority,
    ExecutionPermit,
    SqliteExecutionAuthority,
    resolve_execution_authority,
)
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
    "AcquireOutcome",
    "ExecutionAuthority",
    "ExecutionPermit",
    "LocalPacketRegistry",
    "PacketStoreClient",
    "RegistryEntry",
    "SqliteExecutionAuthority",
    "StageExecutionOutcome",
    "WorkerError",
    "build_callback_transport_packet",
    "build_transport_packet",
    "calculate_transport_packet_id",
    "execute_stage",
    "resolve_execution_authority",
    "sign_transport_packet",
    "transport_signing_view",
    "validate_stage_dispatch",
    "verify_transport_packet",
]
