"""Deterministic, operator-actionable rendering of write and commit failures.

A commit receipt already carries why each artifact failed. Collapsing that into
the receipt status alone produces messages like ``commit failed: failed``, which
name neither the stage, the packet type, the failing member, nor the underlying
validation code. This module renders the receipt instead of discarding it.

Rendering is pure: it reads a receipt, emits ordered lines, and performs no I/O.
Only fields the caller already holds are rendered, so no credential or payload
value can reach an operator log through this path.
"""

from __future__ import annotations

from .write_plan import CommitReceipt

#: Emitted when a receipt records a failure that carries no message at all.
UNSPECIFIED_REASON = "no reason was recorded by the sink"

_FAILED_FIRST = {"failed": 0, "blocked": 1, "skipped": 2, "written": 3}


def format_commit_failure(
    receipt: CommitReceipt,
    *,
    stage: str,
    packet_type: str | None = None,
) -> tuple[str, ...]:
    """Return ordered, human-readable lines explaining a failed commit.

    Lines are ordered failures first and then by destination path so repeated
    runs of the same defect produce identical operator output.
    """
    header = f"{stage}: commit status {receipt.status}"
    if packet_type:
        header = f"{header} for packet type {packet_type}"
    lines = [header, f"{stage}: write plan {receipt.plan_id}"]

    if receipt.status == "blocked":
        lines.append(f"{stage}: the write plan was blocked before any artifact was written")

    ordered = sorted(
        receipt.results,
        key=lambda item: (_FAILED_FIRST.get(item.status, 9), item.destination_path),
    )
    reported = 0
    seen_messages: set[str] = set()
    for result in ordered:
        if result.status != "failed":
            continue
        reported += 1
        message = result.message.strip() or UNSPECIFIED_REASON
        # The same underlying verification error is recorded against every member
        # of an atomic bundle. Name each affected member, but print the shared
        # cause once so the real reason is not buried by repetition.
        if message in seen_messages:
            lines.append(f"{stage}: {result.destination_path}: same cause as above")
            continue
        seen_messages.add(message)
        lines.append(f"{stage}: {result.destination_path}: {message}")

    if not reported and receipt.status != "passed":
        lines.append(f"{stage}: {UNSPECIFIED_REASON}")
    return tuple(lines)


def commit_failure_message(
    receipt: CommitReceipt,
    *,
    stage: str,
    packet_type: str | None = None,
) -> str:
    """Return the rendered failure as a single multi-line message."""
    return "\n".join(format_commit_failure(receipt, stage=stage, packet_type=packet_type))
