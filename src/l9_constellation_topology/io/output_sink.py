"""Single effect boundary used by the topology compiler."""

from __future__ import annotations

from typing import Protocol

from .write_intent import WriteIntent
from .write_plan import CommitReceipt, WritePlan


class OutputSink(Protocol):
    """Structural contract for controlled topology artifact effects."""

    def enqueue(self, intent: WriteIntent) -> None:
        raise TypeError("OutputSink is a structural protocol; use a concrete sink")

    def plan(self) -> WritePlan:
        raise TypeError("OutputSink is a structural protocol; use a concrete sink")

    def commit(self) -> CommitReceipt:
        raise TypeError("OutputSink is a structural protocol; use a concrete sink")

    def clear(self) -> None:
        raise TypeError("OutputSink is a structural protocol; use a concrete sink")
