"""Policy-governed filesystem sink with atomic per-file commits."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from l9_constellation_topology.run.evidence import artifact_hash

from .write_intent import WriteIntent
from .write_plan import (
    CommitArtifactResult,
    CommitReceipt,
    WriteAction,
    WritePlan,
    WritePlanEntry,
    make_commit_receipt,
    make_write_plan,
)
from .write_policy import WritePolicy


class FileSystemOutputSink:
    def __init__(self, output_root: Path, policy: WritePolicy) -> None:
        self.output_root = output_root.resolve()
        self.policy = policy
        self._intents: list[WriteIntent] = []
        self._planned: WritePlan | None = None

    def enqueue(self, intent: WriteIntent) -> None:
        self._intents.append(intent)
        self._planned = None

    def _resolve_destination(self, destination: str) -> Path:
        target = (self.output_root / destination).resolve()
        if self.policy.enforce_path_containment:
            try:
                target.relative_to(self.output_root)
            except ValueError as exc:
                raise ValueError(f"destination escapes output root: {destination}") from exc
        return target

    def _allowed_root(self, destination: str) -> bool:
        return any(
            root == "." or destination == root or destination.startswith(f"{root}/")
            for root in self.policy.allowed_output_roots
        )

    def plan(self) -> WritePlan:
        if self._planned is not None:
            return self._planned
        issues: list[str] = []
        if len(self._intents) > self.policy.maximum_output_count:
            issues.append("maximum_output_count exceeded")
        total_bytes = sum(len(intent.artifact.content) for intent in self._intents)
        if total_bytes > self.policy.maximum_output_bytes:
            issues.append("maximum_output_bytes exceeded")

        seen: set[Path] = set()
        entries: list[WritePlanEntry] = []
        for intent in self._intents:
            artifact = intent.artifact
            destination = artifact.destination_path
            if artifact.artifact_kind not in self.policy.allowed_artifact_kinds:
                issues.append(f"artifact kind is not allowed: {artifact.artifact_kind}")
            if not self._allowed_root(destination):
                issues.append(f"destination is outside allowed output roots: {destination}")
            try:
                target = self._resolve_destination(destination)
            except ValueError as exc:
                issues.append(str(exc))
                target = self.output_root / "__blocked__"
            if target in seen and self.policy.reject_collisions:
                issues.append(f"output collision: {destination}")
            seen.add(target)

            action: WriteAction
            existing_hash: str | None = None
            if target.is_file():
                existing_hash = artifact_hash(target.read_bytes())
            if existing_hash == artifact.content_hash:
                action = "skip"
                reason = "content unchanged"
            elif not target.exists():
                action = "create"
                reason = "destination does not exist"
            elif not target.is_file():
                action = "skip"
                reason = "destination is not a regular file"
                if intent.required:
                    issues.append(f"destination is not a regular file: {destination}")
            elif not self.policy.allow_overwrite:
                action = "skip"
                reason = "overwrite prohibited"
                if intent.required:
                    issues.append(
                        f"required output exists and overwrite is prohibited: {destination}"
                    )
            elif (
                self.policy.require_expected_hash_for_replace
                and intent.expected_existing_hash is None
            ):
                action = "skip"
                reason = "expected existing hash required"
                if intent.required:
                    issues.append(f"expected existing hash is required: {destination}")
            elif (
                intent.expected_existing_hash is not None
                and intent.expected_existing_hash != existing_hash
            ):
                action = "skip"
                reason = "existing hash does not match expected hash"
                if intent.required:
                    issues.append(f"existing hash mismatch: {destination}")
            else:
                action = "replace"
                reason = "replacement authorized"
            entries.append(
                WritePlanEntry(
                    intent=intent,
                    action=action,
                    existing_hash=existing_hash,
                    reason=reason,
                )
            )
        self._planned = make_write_plan(tuple(entries), issues=tuple(sorted(set(issues))))
        return self._planned

    def _atomic_write(self, target: Path, content: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not self.policy.atomic_writes:
            target.write_bytes(content)
            return
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()

    def commit(self) -> CommitReceipt:
        plan = self.plan()
        if plan.status == "blocked":
            return make_commit_receipt(plan, (), blocked=True)
        results: list[CommitArtifactResult] = []
        for entry in plan.entries:
            artifact = entry.intent.artifact
            if self.policy.mode == "dry-run":
                results.append(
                    CommitArtifactResult(
                        logical_id=artifact.logical_id,
                        destination_path=artifact.destination_path,
                        status="skipped",
                        content_hash=artifact.content_hash,
                        message=f"dry-run: {entry.action}",
                    )
                )
                continue
            if entry.action == "skip":
                results.append(
                    CommitArtifactResult(
                        logical_id=artifact.logical_id,
                        destination_path=artifact.destination_path,
                        status="skipped",
                        content_hash=artifact.content_hash,
                        message=entry.reason,
                    )
                )
                continue
            target = self._resolve_destination(artifact.destination_path)
            try:
                self._atomic_write(target, artifact.content)
            except OSError as exc:
                results.append(
                    CommitArtifactResult(
                        logical_id=artifact.logical_id,
                        destination_path=artifact.destination_path,
                        status="failed",
                        content_hash=artifact.content_hash,
                        message=str(exc),
                    )
                )
            else:
                results.append(
                    CommitArtifactResult(
                        logical_id=artifact.logical_id,
                        destination_path=artifact.destination_path,
                        status="written",
                        content_hash=artifact.content_hash,
                        message=entry.action,
                    )
                )
        return make_commit_receipt(plan, tuple(results))

    def clear(self) -> None:
        self._intents.clear()
        self._planned = None
