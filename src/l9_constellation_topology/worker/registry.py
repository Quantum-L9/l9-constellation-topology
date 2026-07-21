"""Local idempotency registry for tests, replay recovery, and single-host operation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.io import (
    FileSystemOutputSink,
    RenderedArtifact,
    WriteIntent,
    WritePolicy,
)
from l9_constellation_topology.packets import PacketRef
from l9_constellation_topology.run import artifact_hash, canonical_bytes

from .errors import WorkerError


class RegistryEntry(FrozenModel):
    idempotency_key: str
    packet_ref: PacketRef
    validation_receipt_uri: str
    commit_receipt_uri: str
    status: Literal["published", "acknowledged"] = "published"
    metadata: dict[str, str] = Field(default_factory=dict)


class LocalPacketRegistry:
    """Durable local recovery index; the production registry remains control-plane owned."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()

    def _read(self) -> dict[str, RegistryEntry]:
        if not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return {key: RegistryEntry.model_validate(value) for key, value in raw.items()}
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise WorkerError(
                "packet-registry-invalid",
                f"cannot read local packet registry: {exc}",
                blocked=True,
            ) from exc

    def get(self, idempotency_key: str) -> RegistryEntry | None:
        return self._read().get(idempotency_key)

    def _write(self, entries: dict[str, RegistryEntry]) -> None:
        content = (
            canonical_bytes(
                {key: value.model_dump(mode="json") for key, value in sorted(entries.items())}
            )
            + b"\n"
        )
        artifact = RenderedArtifact(
            logical_id="local-packet-registry",
            destination_path=self.path.name,
            artifact_kind="debug-artifact",
            media_type="application/json",
            content=content,
            content_hash=artifact_hash(content),
            source_refs=tuple(value.packet_ref.packet_id for value in entries.values()),
        )
        expected_hash = artifact_hash(self.path.read_bytes()) if self.path.is_file() else None
        sink = FileSystemOutputSink(
            self.path.parent,
            WritePolicy(
                allowed_output_roots=(".",),
                allowed_artifact_kinds=("debug-artifact",),
                allow_overwrite=True,
                require_expected_hash_for_replace=True,
                atomic_writes=True,
            ),
        )
        sink.enqueue(WriteIntent(artifact=artifact, expected_existing_hash=expected_hash))
        receipt = sink.commit()
        if receipt.status != "passed":
            raise WorkerError(
                "packet-registry-write-failed",
                receipt.model_dump_json(),
                retryable=True,
            )

    def register(self, entry: RegistryEntry) -> None:
        entries = self._read()
        existing = entries.get(entry.idempotency_key)
        if existing is not None and existing.packet_ref.packet_id != entry.packet_ref.packet_id:
            raise WorkerError(
                "idempotency-collision",
                "idempotency key already maps to a different packet",
                blocked=True,
            )
        entries[entry.idempotency_key] = entry
        self._write(entries)

    def acknowledge(self, idempotency_key: str) -> RegistryEntry:
        entries = self._read()
        existing = entries.get(idempotency_key)
        if existing is None:
            raise WorkerError(
                "packet-registry-entry-missing",
                f"cannot acknowledge unknown idempotency key: {idempotency_key}",
                blocked=True,
            )
        acknowledged = existing.model_copy(update={"status": "acknowledged"})
        entries[idempotency_key] = acknowledged
        self._write(entries)
        return acknowledged
