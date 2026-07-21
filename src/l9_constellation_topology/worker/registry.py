"""Transactional local packet registry for tests and single-host recovery."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.packets import PacketRef
from l9_constellation_topology.run import canonical_json

from .errors import WorkerError


class RegistryEntry(FrozenModel):
    idempotency_key: str
    packet_ref: PacketRef
    validation_receipt_uri: str
    commit_receipt_uri: str
    status: Literal["published", "acknowledged"] = "published"
    metadata: dict[str, str] = Field(default_factory=dict)


class LocalPacketRegistry:
    """SQLite WAL registry for local execution.

    Production authority remains the external Postgres control plane. SQLite is used here to
    make local and test execution transaction-safe under concurrent worker processes.
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
                    CREATE TABLE IF NOT EXISTS packet_registry (
                        idempotency_key TEXT PRIMARY KEY,
                        packet_id TEXT NOT NULL,
                        entry_json TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('published', 'acknowledged'))
                    )
                    """
                )
        except sqlite3.Error as exc:
            raise WorkerError(
                "packet-registry-invalid",
                f"cannot initialize local packet registry: {exc}",
                blocked=True,
            ) from exc

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> RegistryEntry | None:
        if row is None:
            return None
        try:
            return RegistryEntry.model_validate(json.loads(str(row["entry_json"])))
        except (json.JSONDecodeError, ValueError) as exc:
            raise WorkerError(
                "packet-registry-invalid",
                f"cannot decode local packet registry entry: {exc}",
                blocked=True,
            ) from exc

    def get(self, idempotency_key: str) -> RegistryEntry | None:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT entry_json FROM packet_registry WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
            return self._decode(row)
        except sqlite3.Error as exc:
            raise WorkerError(
                "packet-registry-read-failed",
                str(exc),
                retryable=True,
            ) from exc

    def register(self, entry: RegistryEntry) -> None:
        encoded = canonical_json(entry)
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT packet_id FROM packet_registry WHERE idempotency_key = ?",
                    (entry.idempotency_key,),
                ).fetchone()
                if row is not None and str(row["packet_id"]) != entry.packet_ref.packet_id:
                    connection.execute("ROLLBACK")
                    raise WorkerError(
                        "idempotency-collision",
                        "idempotency key already maps to a different packet",
                        blocked=True,
                    )
                connection.execute(
                    """
                    INSERT INTO packet_registry(idempotency_key, packet_id, entry_json, status)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(idempotency_key) DO UPDATE SET
                        packet_id = excluded.packet_id,
                        entry_json = excluded.entry_json,
                        status = excluded.status
                    """,
                    (
                        entry.idempotency_key,
                        entry.packet_ref.packet_id,
                        encoded,
                        entry.status,
                    ),
                )
                connection.execute("COMMIT")
        except WorkerError:
            raise
        except sqlite3.Error as exc:
            raise WorkerError(
                "packet-registry-write-failed",
                str(exc),
                retryable=True,
            ) from exc

    def acknowledge(self, idempotency_key: str) -> RegistryEntry:
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT entry_json FROM packet_registry WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                existing = self._decode(row)
                if existing is None:
                    connection.execute("ROLLBACK")
                    raise WorkerError(
                        "packet-registry-entry-missing",
                        f"cannot acknowledge unknown idempotency key: {idempotency_key}",
                        blocked=True,
                    )
                acknowledged = existing.model_copy(update={"status": "acknowledged"})
                connection.execute(
                    "UPDATE packet_registry SET entry_json = ?, status = ? WHERE idempotency_key = ?",
                    (canonical_json(acknowledged), "acknowledged", idempotency_key),
                )
                connection.execute("COMMIT")
                return acknowledged
        except WorkerError:
            raise
        except sqlite3.Error as exc:
            raise WorkerError(
                "packet-registry-write-failed",
                str(exc),
                retryable=True,
            ) from exc
