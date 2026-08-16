"""The bounded read-only scan must work, stay read-only, and fail out loud.

``scan`` is the documented compatibility ingress: a source repository is observed
read-only, turned into a synthetic ``l9.repository-model`` bundle, committed
through ``OutputSink``, verified back under Repository Model semantics, and then
compiled by the same canonical compiler the production ingress uses.

These tests cover the two defects that path carried — a bundle verified under the
wrong packet type, and a failure reported as ``commit failed: failed`` — and pin
the read-only and fail-closed properties that must survive the repair.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from l9_constellation_topology.cli import run
from l9_constellation_topology.compatibility.v4_models import RepoSource
from l9_constellation_topology.io import (
    PacketBundleOutputSink,
    WriteIntent,
    format_commit_failure,
    make_commit_receipt,
    make_write_plan,
)
from l9_constellation_topology.packets.bundle_verification import (
    BUNDLE_VERIFIERS,
    BundleVerificationError,
    verify_packet_bundle,
)
from l9_constellation_topology.packets.loader import load_topology_bundle
from l9_constellation_topology.packets.repository_bundle import (
    build_repository_model_bundle_artifacts,
)
from l9_constellation_topology.scanners.repository_model_scanner import scan_repository_model

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "fixtures" / "sample_constellation"


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def trivial_repository(tmp_path: Path) -> Path:
    """A one-file git repository: the smallest thing scan must handle."""
    source = tmp_path / "trivial"
    source.mkdir()
    (source / "README.md").write_text("# Trivial\n", encoding="utf-8")
    _git("init", "--quiet", ".", cwd=source)
    _git("config", "user.email", "scan@example.invalid", cwd=source)
    _git("config", "user.name", "scan probe", cwd=source)
    _git("add", "README.md", cwd=source)
    _git("commit", "--quiet", "-m", "initial", cwd=source)
    return source


def _tree_state(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def test_scan_of_a_trivial_repository_succeeds_and_validates(
    trivial_repository: Path, tmp_path: Path
) -> None:
    out = tmp_path / "topology-bundle"
    before = _tree_state(trivial_repository)

    exit_code = run(
        [
            "scan",
            "--repo-root",
            str(ROOT),
            "--source-repo",
            str(trivial_repository),
            "--out",
            str(out),
        ]
    )

    assert exit_code == 0
    materialized, receipt = load_topology_bundle(out)
    assert receipt.status == "passed"
    assert materialized.packet.validation.status == "passed"
    assert [record.repository_id for record in materialized.state.repository_records] == [
        "repo:trivial"
    ]
    assert _tree_state(trivial_repository) == before, "scan must not mutate its source"


def test_scan_verifies_the_intermediate_bundle_as_a_repository_model(
    trivial_repository: Path, tmp_path: Path
) -> None:
    """The synthetic bundle is verified under its own contract, not topology's.

    Verifying a Repository Model bundle with the Topology Packet loader was the
    original defect: it reported six contract violations that did not exist.
    """
    bundle = scan_repository_model(
        RepoSource(
            repo_id="trivial",
            name="trivial",
            local_path=str(trivial_repository),
        )
    )
    destination = tmp_path / "repository-model-bundle"
    sink = PacketBundleOutputSink(destination)
    for artifact in build_repository_model_bundle_artifacts(bundle):
        sink.enqueue(WriteIntent(artifact=artifact))

    receipt = sink.commit()

    assert receipt.status == "passed"
    assert verify_packet_bundle(destination) == "l9.repository-model"


def test_both_canonical_packet_types_have_a_bound_verifier() -> None:
    assert set(BUNDLE_VERIFIERS) == {"l9.topology", "l9.repository-model"}


def test_unknown_packet_type_fails_closed(trivial_repository: Path, tmp_path: Path) -> None:
    """An unrecognized packet type must not fall back to a default loader."""
    bundle = scan_repository_model(
        RepoSource(repo_id="trivial", name="trivial", local_path=str(trivial_repository))
    )
    destination = tmp_path / "repository-model-bundle"
    sink = PacketBundleOutputSink(destination)
    for artifact in build_repository_model_bundle_artifacts(bundle):
        sink.enqueue(WriteIntent(artifact=artifact))
    assert sink.commit().status == "passed"

    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["packet_type"] = "l9.not-a-packet-type"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(BundleVerificationError) as caught:
        verify_packet_bundle(destination)

    assert caught.value.code == "unsupported-bundle-packet-type"
    assert caught.value.packet_type == "l9.not-a-packet-type"
    # The refusal names the types that do have a verifier, so an operator can see
    # whether the bundle is wrong or the dispatch table is incomplete.
    assert "l9.repository-model" in str(caught.value)


def test_tampered_repository_model_member_is_rejected_actionably(
    trivial_repository: Path, tmp_path: Path
) -> None:
    """A modified intermediate bundle member must be refused, and say so."""
    bundle = scan_repository_model(
        RepoSource(repo_id="trivial", name="trivial", local_path=str(trivial_repository))
    )
    source_bundle = tmp_path / "repository-model-bundle"
    sink = PacketBundleOutputSink(source_bundle)
    for artifact in build_repository_model_bundle_artifacts(bundle):
        sink.enqueue(WriteIntent(artifact=artifact))
    assert sink.commit().status == "passed"

    tampered = tmp_path / "tampered"
    shutil.copytree(source_bundle, tampered)
    packet_path = tampered / "packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet["producer"]["version"] = "9.9.9"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    with pytest.raises(BundleVerificationError) as caught:
        verify_packet_bundle(tampered)

    message = str(caught.value)
    assert "packet.json" in message
    assert caught.value.stage
    assert caught.value.code


def test_scan_of_a_real_repository_compiles_and_leaves_it_untouched(tmp_path: Path) -> None:
    """A repository with real structure, not a synthetic single file."""
    source = tmp_path / "sample"
    shutil.copytree(SAMPLE / "l9-mcp-server", source)
    before = _tree_state(source)

    exit_code = run(
        [
            "scan",
            "--repo-root",
            str(ROOT),
            "--source-repo",
            str(source),
            "--repository-id",
            "l9-mcp-server",
            "--name",
            "l9-mcp-server",
            "--out",
            str(tmp_path / "out"),
        ]
    )

    assert exit_code == 0
    materialized, receipt = load_topology_bundle(tmp_path / "out")
    assert receipt.status == "passed"
    assert materialized.state.repository_records
    assert _tree_state(source) == before


def test_commit_failure_reporting_names_stage_member_and_cause(
    trivial_repository: Path, tmp_path: Path
) -> None:
    """A failed commit must never be reported only as its status."""
    bundle = scan_repository_model(
        RepoSource(repo_id="trivial", name="trivial", local_path=str(trivial_repository))
    )
    artifacts = build_repository_model_bundle_artifacts(bundle)
    sink = PacketBundleOutputSink(tmp_path / "bundle")
    intents = tuple(WriteIntent(artifact=artifact) for artifact in artifacts)
    for intent in intents:
        sink.enqueue(intent)
    plan = sink.plan()
    failed = make_commit_receipt(
        make_write_plan(plan.entries),
        tuple(
            result.model_copy(
                update={"status": "failed", "message": "repository model payload is unresolved"}
            )
            for result in sink.commit().results
        ),
    )

    lines = format_commit_failure(
        failed, stage="scan/trivial/repository-model-bundle-commit", packet_type="l9.repository-model"
    )

    rendered = "\n".join(lines)
    assert "scan/trivial/repository-model-bundle-commit" in rendered
    assert "l9.repository-model" in rendered
    assert "repository model payload is unresolved" in rendered
    assert "packet.json" in rendered
    assert rendered != "commit failed: failed"
    # Deterministic across repeated renderings of the same receipt.
    assert lines == format_commit_failure(
        failed,
        stage="scan/trivial/repository-model-bundle-commit",
        packet_type="l9.repository-model",
    )


def test_commit_failure_reporting_repeats_a_shared_cause_only_once(
    trivial_repository: Path, tmp_path: Path
) -> None:
    """An atomic bundle records one cause per member; print it once, name each."""
    bundle = scan_repository_model(
        RepoSource(repo_id="trivial", name="trivial", local_path=str(trivial_repository))
    )
    sink = PacketBundleOutputSink(tmp_path / "bundle")
    for artifact in build_repository_model_bundle_artifacts(bundle):
        sink.enqueue(WriteIntent(artifact=artifact))
    passed = sink.commit()
    shared = "bundle member hash mismatch: packet.json"
    failed = make_commit_receipt(
        make_write_plan(sink.plan().entries),
        tuple(
            result.model_copy(update={"status": "failed", "message": shared})
            for result in passed.results
        ),
    )

    rendered = "\n".join(format_commit_failure(failed, stage="scan"))

    assert rendered.count(shared) == 1
    assert rendered.count("same cause as above") == len(passed.results) - 1
