"""Convert worker exceptions into canonical failure payloads."""

from __future__ import annotations

from l9_constellation_topology.packets import ExecutionFailure

from .errors import WorkerError


def execution_failure(
    *,
    run_id: str,
    stage_id: str,
    input_packet_ids: tuple[str, ...],
    error: Exception,
) -> ExecutionFailure:
    if isinstance(error, WorkerError):
        return ExecutionFailure(
            run_id=run_id,
            stage_id=stage_id,
            status="blocked" if error.blocked else "failed",
            error_class=error.code,
            message=error.message,
            retryable=error.retryable,
            input_packet_ids=input_packet_ids,
        )
    return ExecutionFailure(
        run_id=run_id,
        stage_id=stage_id,
        status="failed",
        error_class=type(error).__name__,
        message=str(error),
        retryable=False,
        input_packet_ids=input_packet_ids,
    )
