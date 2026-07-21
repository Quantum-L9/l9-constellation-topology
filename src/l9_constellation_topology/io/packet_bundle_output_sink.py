"""Filesystem sink specialized for one immutable packet bundle directory."""

from __future__ import annotations

from pathlib import Path

from .filesystem_output_sink import FileSystemOutputSink
from .rendered_artifact import ArtifactKind
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
    def __init__(
        self,
        bundle_root: Path,
        *,
        mode: str = "write",
        allow_overwrite: bool = False,
    ) -> None:
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
