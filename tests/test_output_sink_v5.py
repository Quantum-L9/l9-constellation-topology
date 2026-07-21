from pathlib import Path

from l9_constellation_topology.io import (
    FileSystemOutputSink,
    MemoryOutputSink,
    RenderedArtifact,
    WriteIntent,
    WritePolicy,
)
from l9_constellation_topology.run import artifact_hash

KINDS = ("topology-packet", "validation-receipt", "commit-receipt")


def artifact(path: str, content: bytes = b"data") -> RenderedArtifact:
    return RenderedArtifact(
        logical_id=path,
        destination_path=path,
        artifact_kind="topology-packet",
        media_type="application/octet-stream",
        content=content,
        content_hash=artifact_hash(content),
    )


def test_memory_sink_dry_run_never_writes() -> None:
    sink = MemoryOutputSink(
        WritePolicy(
            mode="dry-run",
            allowed_output_roots=(".",),
            allowed_artifact_kinds=KINDS,
            allow_overwrite=True,
            require_expected_hash_for_replace=False,
        )
    )
    sink.enqueue(WriteIntent(artifact=artifact("packet.json")))
    receipt = sink.commit()
    assert receipt.status == "passed"
    assert receipt.results[0].status == "skipped"
    assert sink.storage == {}


def test_sink_skips_unchanged_content() -> None:
    sink = MemoryOutputSink(
        WritePolicy(
            allowed_output_roots=(".",),
            allowed_artifact_kinds=KINDS,
            allow_overwrite=True,
            require_expected_hash_for_replace=False,
        ),
        existing={"packet.json": b"same"},
    )
    sink.enqueue(WriteIntent(artifact=artifact("packet.json", b"same")))
    plan = sink.plan()
    assert plan.entries[0].action == "skip"
    assert sink.commit().results[0].status == "skipped"


def test_sink_blocks_collision() -> None:
    sink = MemoryOutputSink(
        WritePolicy(
            allowed_output_roots=(".",),
            allowed_artifact_kinds=KINDS,
            allow_overwrite=True,
            require_expected_hash_for_replace=False,
        )
    )
    sink.enqueue(WriteIntent(artifact=artifact("packet.json", b"first")))
    sink.enqueue(WriteIntent(artifact=artifact("packet.json", b"second")))
    assert sink.plan().status == "blocked"
    assert sink.commit().status == "blocked"
    assert sink.storage == {}


def test_filesystem_sink_enforces_expected_hash(tmp_path: Path) -> None:
    existing = tmp_path / "packet.json"
    existing.write_bytes(b"old")
    sink = FileSystemOutputSink(
        tmp_path,
        WritePolicy(
            allowed_output_roots=(".",),
            allowed_artifact_kinds=KINDS,
            allow_overwrite=True,
            require_expected_hash_for_replace=True,
        ),
    )
    sink.enqueue(
        WriteIntent(
            artifact=artifact("packet.json", b"new"),
            expected_existing_hash="sha256:not-the-current-hash",
        )
    )
    assert sink.plan().status == "blocked"
    assert sink.commit().status == "blocked"
    assert existing.read_bytes() == b"old"


def test_filesystem_sink_atomic_commit(tmp_path: Path) -> None:
    sink = FileSystemOutputSink(
        tmp_path,
        WritePolicy(
            allowed_output_roots=(".",),
            allowed_artifact_kinds=KINDS,
            allow_overwrite=True,
            require_expected_hash_for_replace=False,
            atomic_writes=True,
        ),
    )
    sink.enqueue(WriteIntent(artifact=artifact("payload/a.json", b"new")))
    receipt = sink.commit()
    assert receipt.status == "passed"
    assert (tmp_path / "payload/a.json").read_bytes() == b"new"
    assert not list(tmp_path.rglob("*.tmp"))
