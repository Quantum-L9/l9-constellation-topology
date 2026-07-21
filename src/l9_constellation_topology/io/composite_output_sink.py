"""Fan-out sink for local bundle plus additional approved destinations."""

from __future__ import annotations

from .output_sink import OutputSink
from .write_intent import WriteIntent
from .write_plan import (
    CommitArtifactResult,
    CommitReceipt,
    WritePlan,
    make_commit_receipt,
    make_write_plan,
)


class CompositeOutputSink:
    def __init__(self, sinks: tuple[OutputSink, ...]) -> None:
        if not sinks:
            raise ValueError("CompositeOutputSink requires at least one sink")
        self.sinks = sinks
        self._plan: WritePlan | None = None

    def enqueue(self, intent: WriteIntent) -> None:
        for sink in self.sinks:
            sink.enqueue(intent)
        self._plan = None

    def plan(self) -> WritePlan:
        plans = tuple(sink.plan() for sink in self.sinks)
        issues = tuple(
            f"sink[{index}]: {issue}" for index, plan in enumerate(plans) for issue in plan.issues
        )
        entries = tuple(entry for plan in plans for entry in plan.entries)
        self._plan = make_write_plan(entries, issues=issues)
        return self._plan

    def commit(self) -> CommitReceipt:
        plan = self.plan()
        if plan.status == "blocked":
            return make_commit_receipt(plan, (), blocked=True)
        child_receipts = tuple(sink.commit() for sink in self.sinks)
        results: list[CommitArtifactResult] = []
        for index, receipt in enumerate(child_receipts):
            for result in receipt.results:
                results.append(
                    result.model_copy(
                        update={
                            "logical_id": f"sink[{index}]/{result.logical_id}",
                        }
                    )
                )
        return make_commit_receipt(plan, tuple(results))

    def clear(self) -> None:
        for sink in self.sinks:
            sink.clear()
        self._plan = None
