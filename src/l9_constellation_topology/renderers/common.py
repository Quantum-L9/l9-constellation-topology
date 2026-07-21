"""Renderer helpers that keep formatting pure and effects inside OutputSink."""

from __future__ import annotations

from pathlib import Path

from l9_constellation_topology.io import (
    FileSystemOutputSink,
    RenderedArtifact,
    WriteIntent,
    WritePolicy,
)
from l9_constellation_topology.run import artifact_hash


def make_rendered_artifact(
    *,
    logical_id: str,
    destination_path: str,
    artifact_kind: str,
    media_type: str,
    content: bytes,
    semantic_hash: str | None = None,
    source_refs: tuple[str, ...] = (),
) -> RenderedArtifact:
    return RenderedArtifact(
        logical_id=logical_id,
        destination_path=destination_path,
        artifact_kind=artifact_kind,  # type: ignore[arg-type]
        media_type=media_type,
        content=content,
        content_hash=artifact_hash(content),
        semantic_hash=semantic_hash,
        source_refs=source_refs,
    )


def write_compatibility_artifact(output_path: Path, artifact: RenderedArtifact) -> None:
    """Compatibility wrapper; all actual mutation remains inside io/."""
    target = output_path.resolve()
    relocated = artifact.model_copy(update={"destination_path": target.name})
    sink = FileSystemOutputSink(
        target.parent,
        WritePolicy(
            allowed_output_roots=(".",),
            allowed_artifact_kinds=(relocated.artifact_kind,),
            allow_overwrite=True,
            require_expected_hash_for_replace=False,
        ),
    )
    sink.enqueue(WriteIntent(artifact=relocated))
    receipt = sink.commit()
    if receipt.status != "passed":
        raise OSError(f"renderer output commit failed: {receipt.model_dump(mode='json')}")
