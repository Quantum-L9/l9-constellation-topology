"""Read-only source access protocol."""

from __future__ import annotations

from typing import Protocol


class SourceReader(Protocol):
    """Structural contract for deterministic read-only repository access."""

    repository_id: str
    source_revision: str

    def exists(self, path: str) -> bool:
        raise TypeError("SourceReader is a structural protocol; use a concrete reader")

    def read_bytes(self, path: str) -> bytes:
        raise TypeError("SourceReader is a structural protocol; use a concrete reader")

    def read_text(self, path: str) -> str:
        raise TypeError("SourceReader is a structural protocol; use a concrete reader")

    def iter_files(self) -> tuple[str, ...]:
        raise TypeError("SourceReader is a structural protocol; use a concrete reader")
