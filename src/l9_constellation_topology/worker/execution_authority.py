"""Authoritative execution lease and idempotency claim for protected stage work.

The stage worker performs a sequence of protected side effects (compile, commit, publish,
register, callback). HMAC signature verification proves *integrity and possession* of a
dispatch, not *current, unique, one-time authorization* to execute it. This module adds
the missing authority: a short-lived execution lease that must be acquired before the
first side effect and revalidated immediately before each subsequent one.

``ExecutionPermit`` is a capability, not a checkpoint. It carries an authority-generated
``lease_id`` and secret ``fence_token`` that only exist in the backing store, so a permit
cannot be forged from raw dispatch input: every use is re-checked against the store.

``SqliteExecutionAuthority`` is the authoritative implementation for single-host and test
execution. It enforces, in one atomic transaction, ``UNIQUE(idempotency_key)`` (single
winner across concurrent workers) and ``UNIQUE(dispatch_nonce)`` (one-time use, replay
rejection) plus the ``CLAIMED -> PUBLISHED -> ACKNOWLEDGED`` (or ``FAILED``) state machine.

Cross-run, cross-host suppression is the responsibility of the external Postgres control
plane, which is outside this repository. ``resolve_execution_authority`` is the fail-closed
seam: production modes that require the control plane refuse to run when it is unavailable
rather than silently falling back to the local backend.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path
from typing import Literal, Protocol, cast, runtime_checkable

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.packets import PacketRef
from l9_constellation_topology.run import canonical_json

from .errors import WorkerError

LeaseState = Literal["CLAIMED", "PUBLISHED", "ACKNOWLEDGED", "FAILED"]

_CONTROL_PLANE_MODES = {"control-plane", "control_plane", "postgres", "production"}
_LOCAL_MODES = {"", "local", "single-host", "single_host"}
_PROTOCOL_MESSAGE = "ExecutionAuthority is a structural protocol; use a concrete authority"

# Repeated SQL/SQLite literals extracted to constants (S1192)
_SQL_BEGIN_IMMEDIATE = "BEGIN IMMEDIATE"
_SQL_LEASE_BY_IKEY = "SELECT * FROM execution_lease WHERE idempotency_key = ?"


class ExecutionPermit(FrozenModel):
    """A non-forgeable capability to perform one stage's protected side effects."""

    idempotency_key: str
    dispatch_nonce: str
    stage_id: str
    packet_id: str
    lease_id: str
    fence_token: str


class AcquireOutcome(FrozenModel):
    """Result of an acquisition attempt: either a fresh permit or a reuse signal."""

    permit: ExecutionPermit | None = None
    reuse: bool = False


@runtime_checkable
class ExecutionAuthority(Protocol):
    """Authority that gates protected stage execution behind a live lease."""

    def acquire(
        self,
        *,
        idempotency_key: str,
        packet_id: str,
        dispatch_nonce: str,
        stage_id: str,
    ) -> AcquireOutcome:
        raise TypeError(_PROTOCOL_MESSAGE)

    def assert_active(self, permit: ExecutionPermit) -> None:
        raise TypeError(_PROTOCOL_MESSAGE)

    def finalize(self, permit: ExecutionPermit, result: PacketRef) -> None:
        raise TypeError(_PROTOCOL_MESSAGE)

    def release(self, permit: ExecutionPermit) -> None:
        raise TypeError(_PROTOCOL_MESSAGE)

    def fail(self, permit: ExecutionPermit, reason: str) -> None:
        raise TypeError(_PROTOCOL_MESSAGE)


class SqliteExecutionAuthority:
    """Transactional single-host execution authority.

    Production authority is the external Postgres control plane. This SQLite-backed
    implementation is authoritative for a single host and for tests: it enforces the
    whole-stage claim, unique nonce, fencing, and state machine that the audit found
    missing at the worker side-effect boundary.
    """

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize(self) -> None:
        try:
            with closing(self._connect()) as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS execution_lease (
                        idempotency_key TEXT PRIMARY KEY,
                        dispatch_nonce TEXT NOT NULL UNIQUE,
                        stage_id TEXT NOT NULL,
                        packet_id TEXT NOT NULL,
                        lease_id TEXT NOT NULL,
                        fence_token TEXT NOT NULL,
                        state TEXT NOT NULL
                            CHECK(state IN ('CLAIMED', 'PUBLISHED', 'ACKNOWLEDGED', 'FAILED')),
                        result_json TEXT
                    )
                    """
                )
        except sqlite3.Error as exc:
            raise WorkerError(
                "execution-authority-invalid",
                f"cannot initialize execution lease store: {exc}",
                blocked=True,
            ) from exc

    def acquire(
        self,
        *,
        idempotency_key: str,
        packet_id: str,
        dispatch_nonce: str,
        stage_id: str,
    ) -> AcquireOutcome:
        try:
            with closing(self._connect()) as connection:
                connection.execute(_SQL_BEGIN_IMMEDIATE)
                try:
                    existing = connection.execute(
                        _SQL_LEASE_BY_IKEY,
                        (idempotency_key,),
                    ).fetchone()
                    if existing is not None:
                        return self._resume_existing(
                            connection,
                            existing,
                            dispatch_nonce=dispatch_nonce,
                            packet_id=packet_id,
                            stage_id=stage_id,
                        )
                    nonce_holder = connection.execute(
                        "SELECT idempotency_key FROM execution_lease WHERE dispatch_nonce = ?",
                        (dispatch_nonce,),
                    ).fetchone()
                    if nonce_holder is not None:
                        connection.execute("ROLLBACK")
                        raise WorkerError(
                            "dispatch-nonce-replayed",
                            "dispatch nonce has already been used for a different stage claim",
                            blocked=True,
                        )
                    permit = ExecutionPermit(
                        idempotency_key=idempotency_key,
                        dispatch_nonce=dispatch_nonce,
                        stage_id=stage_id,
                        packet_id=packet_id,
                        lease_id=secrets.token_hex(16),
                        fence_token=secrets.token_hex(32),
                    )
                    connection.execute(
                        """
                        INSERT INTO execution_lease(
                            idempotency_key, dispatch_nonce, stage_id, packet_id,
                            lease_id, fence_token, state, result_json
                        ) VALUES (?, ?, ?, ?, ?, ?, 'CLAIMED', NULL)
                        """,
                        (
                            idempotency_key,
                            dispatch_nonce,
                            stage_id,
                            packet_id,
                            permit.lease_id,
                            permit.fence_token,
                        ),
                    )
                    connection.execute("COMMIT")
                    return AcquireOutcome(permit=permit)
                except WorkerError:
                    raise
                except sqlite3.Error:
                    connection.execute("ROLLBACK")
                    raise
        except WorkerError:
            raise
        except sqlite3.IntegrityError as exc:
            raise WorkerError(
                "execution-lease-contended",
                f"execution lease is already held for this claim: {exc}",
                retryable=True,
            ) from exc
        except sqlite3.Error as exc:
            raise WorkerError(
                "execution-authority-write-failed",
                str(exc),
                retryable=True,
            ) from exc

    def _resume_existing(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        *,
        dispatch_nonce: str,
        packet_id: str,
        stage_id: str,
    ) -> AcquireOutcome:
        state = str(row["state"])
        if state in {"PUBLISHED", "ACKNOWLEDGED"}:
            connection.execute("COMMIT")
            return AcquireOutcome(reuse=True)
        if state == "CLAIMED":
            connection.execute("ROLLBACK")
            raise WorkerError(
                "execution-lease-contended",
                "another worker holds an active lease for this idempotency key",
                retryable=True,
            )
        # state == FAILED: a previous attempt failed; re-claim with a fresh fence.
        if str(row["dispatch_nonce"]) != dispatch_nonce:
            nonce_holder = connection.execute(
                "SELECT idempotency_key FROM execution_lease WHERE dispatch_nonce = ?",
                (dispatch_nonce,),
            ).fetchone()
            if nonce_holder is not None and str(nonce_holder["idempotency_key"]) != str(
                row["idempotency_key"]
            ):
                connection.execute("ROLLBACK")
                raise WorkerError(
                    "dispatch-nonce-replayed",
                    "dispatch nonce has already been used for a different stage claim",
                    blocked=True,
                )
        permit = ExecutionPermit(
            idempotency_key=str(row["idempotency_key"]),
            dispatch_nonce=dispatch_nonce,
            stage_id=stage_id,
            packet_id=packet_id,
            lease_id=secrets.token_hex(16),
            fence_token=secrets.token_hex(32),
        )
        connection.execute(
            """
            UPDATE execution_lease
            SET dispatch_nonce = ?, stage_id = ?, packet_id = ?,
                lease_id = ?, fence_token = ?, state = 'CLAIMED', result_json = NULL
            WHERE idempotency_key = ?
            """,
            (
                dispatch_nonce,
                stage_id,
                packet_id,
                permit.lease_id,
                permit.fence_token,
                permit.idempotency_key,
            ),
        )
        connection.execute("COMMIT")
        return AcquireOutcome(permit=permit)

    def _load_active(self, connection: sqlite3.Connection, permit: ExecutionPermit) -> sqlite3.Row:
        row = connection.execute(
            _SQL_LEASE_BY_IKEY,
            (permit.idempotency_key,),
        ).fetchone()
        if (
            row is None
            or str(row["lease_id"]) != permit.lease_id
            or str(row["fence_token"]) != permit.fence_token
        ):
            raise WorkerError(
                "execution-lease-lost",
                "execution lease is no longer held by this worker",
                blocked=True,
            )
        return cast(sqlite3.Row, row)

    def assert_active(self, permit: ExecutionPermit) -> None:
        try:
            with closing(self._connect()) as connection:
                row = self._load_active(connection, permit)
        except sqlite3.Error as exc:
            raise WorkerError(
                "execution-authority-read-failed",
                str(exc),
                retryable=True,
            ) from exc
        if str(row["state"]) != "CLAIMED":
            raise WorkerError(
                "execution-lease-lost",
                f"execution lease is not active: state={row['state']}",
                blocked=True,
            )

    def finalize(self, permit: ExecutionPermit, result: PacketRef) -> None:
        self._transition(
            permit,
            expected="CLAIMED",
            target="PUBLISHED",
            result_json=canonical_json(result),
        )

    def release(self, permit: ExecutionPermit) -> None:
        self._transition(permit, expected="PUBLISHED", target="ACKNOWLEDGED")

    def fail(self, permit: ExecutionPermit, reason: str) -> None:
        # Best-effort release of a claimed lease. Never overwrite a lease whose protected
        # work already completed (PUBLISHED/ACKNOWLEDGED); failure cleanup must not undo it.
        try:
            with closing(self._connect()) as connection:
                connection.execute(_SQL_BEGIN_IMMEDIATE)
                try:
                    row = connection.execute(
                        _SQL_LEASE_BY_IKEY,
                        (permit.idempotency_key,),
                    ).fetchone()
                    if (
                        row is None
                        or str(row["lease_id"]) != permit.lease_id
                        or str(row["fence_token"]) != permit.fence_token
                        or str(row["state"]) != "CLAIMED"
                    ):
                        connection.execute("ROLLBACK")
                        return
                    connection.execute(
                        "UPDATE execution_lease SET state = 'FAILED' WHERE idempotency_key = ?",
                        (permit.idempotency_key,),
                    )
                    connection.execute("COMMIT")
                except sqlite3.Error:
                    connection.execute("ROLLBACK")
                    raise
        except sqlite3.Error as exc:
            raise WorkerError(
                "execution-authority-write-failed",
                f"{reason}: {exc}" if reason else str(exc),
                retryable=True,
            ) from exc

    def _transition(
        self,
        permit: ExecutionPermit,
        *,
        expected: LeaseState | None,
        target: LeaseState,
        result_json: str | None = None,
    ) -> None:
        try:
            with closing(self._connect()) as connection:
                connection.execute(_SQL_BEGIN_IMMEDIATE)
                try:
                    row = self._load_active(connection, permit)
                    if expected is not None and str(row["state"]) != expected:
                        connection.execute("ROLLBACK")
                        raise WorkerError(
                            "execution-lease-invalid-transition",
                            f"cannot move lease from {row['state']} to {target}",
                            blocked=True,
                        )
                    if result_json is None:
                        connection.execute(
                            "UPDATE execution_lease SET state = ? WHERE idempotency_key = ?",
                            (target, permit.idempotency_key),
                        )
                    else:
                        connection.execute(
                            "UPDATE execution_lease SET state = ?, result_json = ? "
                            "WHERE idempotency_key = ?",
                            (target, result_json, permit.idempotency_key),
                        )
                    connection.execute("COMMIT")
                except WorkerError:
                    raise
                except sqlite3.Error:
                    connection.execute("ROLLBACK")
                    raise
        except WorkerError:
            raise
        except sqlite3.Error as exc:
            raise WorkerError(
                "execution-authority-write-failed",
                str(exc),
                retryable=True,
            ) from exc


def _local_lease_path(
    environ: Mapping[str, str],
    registry_path: Path | None,
    workspace: Path,
) -> Path:
    configured = environ.get("L9_EXECUTION_LEASE_FILE")
    if configured:
        return Path(configured)
    if registry_path is not None:
        return registry_path.with_name(f"{registry_path.stem}-execution-lease.sqlite3")
    return workspace / "execution-lease.sqlite3"


def resolve_execution_authority(
    *,
    workspace: Path,
    registry_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> ExecutionAuthority:
    """Select the execution authority, failing closed when the control plane is required.

    Mode is chosen explicitly via ``L9_EXECUTION_AUTHORITY_MODE``. A control-plane mode
    requires the external Postgres-backed authority, which is not part of this repository;
    when it is unavailable this refuses to run rather than continuing on the local backend.
    """

    environ = os.environ if environ is None else environ
    mode = (environ.get("L9_EXECUTION_AUTHORITY_MODE") or "local").strip().lower()
    if mode in _CONTROL_PLANE_MODES:
        raise WorkerError(
            "execution-authority-unavailable",
            "control-plane execution authority is required but is not available in-process; "
            "refusing to perform protected side effects without an authoritative lease",
            blocked=True,
        )
    if mode in _LOCAL_MODES:
        return SqliteExecutionAuthority(_local_lease_path(environ, registry_path, workspace))
    raise WorkerError(
        "execution-authority-mode-invalid",
        f"unknown execution authority mode: {mode}",
        blocked=True,
    )
