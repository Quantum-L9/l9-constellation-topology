"""Atomic filesystem sink specialized for one immutable packet bundle directory."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from .filesystem_output_sink import FileSystemOutputSink
from .rendered_artifact import ArtifactKind
from .write_plan import CommitArtifactResult, CommitReceipt, make_commit_receipt
from .write_policy import WritePolicy

_ALL_KINDS: tuple[ArtifactKind, ...] = (
    "topology-packet",
    "validation-receipt",
    "report-manifest",
    "human-report",
    "graph-export",
    "risk-report",
    "maturity-report",
    "diagram",
    "debug-artifact",
    "commit-receipt",
)


class PacketBundleOutputSink(FileSystemOutputSink):
    """Commit a complete packet bundle by one atomic directory rename.

    Canonical packet bundles are immutable. An existing bundle may only be reused when every
    planned artifact is byte-identical; partial replacement is rejected.
    """

    def __init__(
        self,
        bundle_root: Path,
        *,
        mode: str = "write",
        allow_overwrite: bool = False,
        bundle_verifier: Callable[[Path], object] | None = None,
    ) -> None:
        # Post-write verifier that re-reads and validates the staged bundle before the
        # atomic rename. Defaults to Topology Packet verification; callers writing a
        # different canonical bundle kind (e.g. a Repository Model Packet in the scan
        # compatibility path) must pass the matching loader so a valid bundle of that
        # kind is not rejected as a non-Topology Packet.
        self._bundle_verifier = bundle_verifier
        policy = WritePolicy(
            mode="dry-run" if mode == "dry-run" else "write",
            allowed_output_roots=(".",),
            allowed_artifact_kinds=_ALL_KINDS,
            allow_overwrite=allow_overwrite,
            require_expected_hash_for_replace=False,
            enforce_path_containment=True,
            reject_collisions=True,
            atomic_writes=True,
        )
        super().__init__(bundle_root, policy)

    @staticmethod
    def _fsync_tree(root: Path) -> None:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                descriptor = os.open(path, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        directories = [path for path in root.rglob("*") if path.is_dir()]
        for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
            descriptor = os.open(path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        descriptor = os.open(root, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def commit(self) -> CommitReceipt:
        plan = self.plan()
        if plan.status == "blocked":
            return make_commit_receipt(plan, (), blocked=True)
        if self.policy.mode == "dry-run":
            return super().commit()

        mutating = tuple(entry for entry in plan.entries if entry.action != "skip")
        if not mutating:
            results = tuple(
                CommitArtifactResult(
                    logical_id=entry.intent.artifact.logical_id,
                    destination_path=entry.intent.artifact.destination_path,
                    status="skipped",
                    content_hash=entry.intent.artifact.content_hash,
                    message=entry.reason,
                )
                for entry in plan.entries
            )
            return make_commit_receipt(plan, results)
        if self.output_root.exists():
            results = tuple(
                CommitArtifactResult(
                    logical_id=entry.intent.artifact.logical_id,
                    destination_path=entry.intent.artifact.destination_path,
                    status="failed",
                    content_hash=entry.intent.artifact.content_hash,
                    message="immutable packet bundle already exists",
                )
                for entry in plan.entries
            )
            return make_commit_receipt(plan, results)

        self.output_root.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{self.output_root.name}.staging-",
                dir=self.output_root.parent,
            )
        )
        try:
            staging_sink = FileSystemOutputSink(
                staging,
                WritePolicy(
                    allowed_output_roots=(".",),
                    allowed_artifact_kinds=_ALL_KINDS,
                    allow_overwrite=False,
                    require_expected_hash_for_replace=False,
                    enforce_path_containment=True,
                    reject_collisions=True,
                    atomic_writes=True,
                    maximum_output_count=self.policy.maximum_output_count,
                    maximum_output_bytes=self.policy.maximum_output_bytes,
                ),
            )
            for intent in self._intents:
                staging_sink.enqueue(intent)
            staging_receipt = staging_sink.commit()
            if staging_receipt.status != "passed":
                return make_commit_receipt(plan, staging_receipt.results)

            verifier = self._bundle_verifier
            if verifier is None:
                from l9_constellation_topology.packets.loader import load_topology_bundle

                verifier = load_topology_bundle
            verifier(staging)
            self._fsync_tree(staging)
            os.replace(staging, self.output_root)
            parent_descriptor = os.open(self.output_root.parent, os.O_RDONLY)
            try:
                os.fsync(parent_descriptor)
            finally:
                os.close(parent_descriptor)
            results = tuple(
                CommitArtifactResult(
                    logical_id=entry.intent.artifact.logical_id,
                    destination_path=entry.intent.artifact.destination_path,
                    status="written" if entry.action != "skip" else "skipped",
                    content_hash=entry.intent.artifact.content_hash,
                    message=("atomic bundle commit" if entry.action != "skip" else entry.reason),
                )
                for entry in plan.entries
            )
            return make_commit_receipt(plan, results)
        except (OSError, ValueError) as exc:
            results = tuple(
                CommitArtifactResult(
                    logical_id=entry.intent.artifact.logical_id,
                    destination_path=entry.intent.artifact.destination_path,
                    status="failed",
                    content_hash=entry.intent.artifact.content_hash,
                    message=str(exc),
                )
                for entry in plan.entries
            )
            return make_commit_receipt(plan, results)
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
