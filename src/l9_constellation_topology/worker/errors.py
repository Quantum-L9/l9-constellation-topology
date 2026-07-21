"""Typed worker failures with retry semantics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerError(RuntimeError):
    code: str
    message: str
    retryable: bool = False
    blocked: bool = False

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
