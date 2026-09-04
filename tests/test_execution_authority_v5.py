"""Adversarial coverage for the execution-lease trust boundary (audit F-02..F-06).

These tests exercise the defects the audit could not test dynamically: stale/replayed
dispatch authority, non-atomic idempotency claims, forgeable execution permits, fail-open
authority selection, and the OutputSink plan/commit race.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest

from l9_constellation_topology.compiler import calculate_idempotency_key
from l9_constellation_topology.config import resolve_configuration
from l9_constellation_topology.io import (
    FileSystemOutputSink,
    RenderedArtifact,
    WriteIntent,
    WritePolicy,
)
from l9_constellation_topology.packets import (
    CallbackRef,
    PacketRef,
    StageDispatchData,
    StageDispatchPayload,
    StageProfileRef,
    TransportPacket,
    load_repository_model_bundle,
)
from l9_constellation_topology.run import artifact_hash, semantic_hash
from l9_constellation_topology.worker import (
    ExecutionPermit,
    LocalPacketRegistry,
    SqliteExecutionAuthority,
    WorkerError,
    build_transport_packet,
    execute_stage,
    resolve_execution_authority,
    validate_stage_dispatch,
)
from l9_constellation_topology.worker.packet_store import PacketStoreClient
from l9_constellation_topology.worker.stage_runner import _execute_stage

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)
KEY = b"test-foundational-key"
KEY_ID = "foundational-hmac-v1"


class _CallbackHandler(BaseHTTPRequestHandler):
    received: ClassVar[list[dict[str, object]]] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.received.append(json.loads(body))
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def _callback_server() -> Iterator[tuple[str, list[dict[str, object]]]]:
    _CallbackHandler.received = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/callback", _CallbackHandler.received
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _git_revision() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _input_refs() -> tuple[PacketRef, ...]:
    refs = []
    for path in INPUTS:
        packet = load_repository_model_bundle(path).packet
        refs.append(
            PacketRef(
                packet_id=packet.packet_id,
                packet_type=packet.packet_type,
                packet_version=packet.packet_version,
                uri=path.resolve().as_uri(),
                semantic_hash=packet.semantic_hash,
                artifact_hash=packet.artifact_hash,
                validation_status=packet.validation.status,
                subject_id=packet.subject.repository_id,
                source_revision=packet.source_snapshot.revision,
            )
        )
    return tuple(refs)


def _dispatch(
    output: Path,
    *,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    dispatch_nonce: str | None = None,
) -> TransportPacket:
    configuration = resolve_configuration(ROOT)
    refs = _input_refs()
    target_revision = _git_revision()
    now = datetime.now(UTC)
    payload = StageDispatchPayload(
        data=StageDispatchData(
            run_id="run:test",
            stage_id="stage:compile-topology",
            workflow_id="foundational-repository-intelligence",
            action="compile-topology",
            target_repository="Quantum-L9/l9-constellation-topology",
            target_revision=target_revision,
            input_packets=refs,
            profile=StageProfileRef(
                id=configuration.profile_id,
                version=configuration.profile_version,
                hash=semantic_hash(configuration.topology_profile),
            ),
            issued_at=issued_at or now,
            expires_at=expires_at or (now + timedelta(minutes=10)),
            dispatch_nonce=dispatch_nonce or f"nonce:{uuid.uuid4().hex}",
            callback=CallbackRef(callback_id="local-integration-test"),
            output_uri=output.resolve().as_uri(),
        )
    )
    return build_transport_packet(
        payload=payload,
        packet_type="command",
        action="compile-topology",
        idempotency_key=calculate_idempotency_key(
            refs, configuration, compiler_build_identity=target_revision.removeprefix("git:")
        ),
        trace_id="trace:test",
        correlation_id="correlation:test",
        workflow_id="foundational-repository-intelligence",
        key=KEY,
        key_id=KEY_ID,
        provenance={"resolved_by_gate": False, "resolver": "l9-ci-core"},
    )


def _validate(packet: TransportPacket) -> None:
    validate_stage_dispatch(
        packet,
        configuration=resolve_configuration(ROOT),
        repository_root=ROOT,
        hmac_key=KEY,
        enforce_source_revision=False,
    )


# ---- F-02: signed freshness / replay window ---------------------------------------------


def test_expired_dispatch_is_rejected(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    packet = _dispatch(
        tmp_path / "out",
        issued_at=now - timedelta(minutes=30),
        expires_at=now - timedelta(minutes=15),
    )
    with pytest.raises(WorkerError, match="dispatch-expired"):
        _validate(packet)


def test_future_dispatch_is_rejected(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    packet = _dispatch(
        tmp_path / "out",
        issued_at=now + timedelta(hours=1),
        expires_at=now + timedelta(hours=2),
    )
    with pytest.raises(WorkerError, match="dispatch-issued-in-future"):
        _validate(packet)


def test_overlong_ttl_is_rejected(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    packet = _dispatch(
        tmp_path / "out",
        issued_at=now,
        expires_at=now + timedelta(hours=6),
    )
    with pytest.raises(WorkerError, match="dispatch-ttl-too-long"):
        _validate(packet)


# ---- F-03: atomic idempotency claim, concurrency, replay --------------------------------


def _authority(tmp_path: Path) -> SqliteExecutionAuthority:
    return SqliteExecutionAuthority(tmp_path / "lease.sqlite3")


def test_reused_dispatch_nonce_is_rejected(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    first = authority.acquire(
        idempotency_key="sha256:" + "a" * 64,
        packet_id="packet:one",
        dispatch_nonce="nonce:shared",
        stage_id="stage:one",
    )
    assert first.permit is not None
    with pytest.raises(WorkerError, match="dispatch-nonce-replayed"):
        authority.acquire(
            idempotency_key="sha256:" + "b" * 64,
            packet_id="packet:two",
            dispatch_nonce="nonce:shared",
            stage_id="stage:two",
        )


def test_concurrent_workers_yield_one_winner(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    idempotency_key = "sha256:" + "c" * 64

    def claim(index: int) -> bool:
        try:
            outcome = authority.acquire(
                idempotency_key=idempotency_key,
                packet_id=f"packet:{index}",
                dispatch_nonce=f"nonce:{index}",
                stage_id=f"stage:{index}",
            )
            return outcome.permit is not None
        except WorkerError:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(claim, range(8)))
    assert sum(1 for won in results if won) == 1


def test_finalized_claim_serves_reuse_signal(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    idempotency_key = "sha256:" + "d" * 64
    outcome = authority.acquire(
        idempotency_key=idempotency_key,
        packet_id="packet:final",
        dispatch_nonce="nonce:final",
        stage_id="stage:final",
    )
    permit = outcome.permit
    assert permit is not None
    result = PacketRef(
        packet_id="packet:final",
        packet_type="l9.topology",
        packet_version="1.0.0",
        uri="file:///tmp/final",
        semantic_hash="sha256:" + "e" * 64,
        validation_status="passed",
    )
    authority.finalize(permit, result)
    resumed = authority.acquire(
        idempotency_key=idempotency_key,
        packet_id="packet:final",
        dispatch_nonce="nonce:final-2",
        stage_id="stage:final",
    )
    assert resumed.reuse is True
    assert resumed.permit is None


# ---- F-04: permit is a capability, not a naming convention ------------------------------


def test_forged_permit_fails_assert_active(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    forged = ExecutionPermit(
        idempotency_key="sha256:" + "f" * 64,
        dispatch_nonce="nonce:forged",
        stage_id="stage:forged",
        packet_id="packet:forged",
        lease_id="deadbeef",
        fence_token="deadbeef",
    )
    with pytest.raises(WorkerError, match="execution-lease-lost"):
        authority.assert_active(forged)


def test_direct_helper_invocation_cannot_reach_side_effects(tmp_path: Path) -> None:
    packet = _dispatch(tmp_path / "out")
    dispatch = StageDispatchPayload.model_validate(packet.payload)
    forged = ExecutionPermit(
        idempotency_key=packet.header.idempotency_key,
        dispatch_nonce=dispatch.data.dispatch_nonce,
        stage_id=dispatch.data.stage_id,
        packet_id=packet.header.packet_id,
        lease_id="forged",
        fence_token="forged",
    )
    # The helper's first action is a lease revalidation, so compile/publish/callback are
    # unreachable with a permit that was never issued by the authority.
    # Construct args outside the raises block (S5778: single raising invocation)
    _registry = LocalPacketRegistry(tmp_path / "registry.sqlite3")
    _store = PacketStoreClient()
    _config = resolve_configuration(ROOT)
    _auth = _authority(tmp_path)
    with pytest.raises(WorkerError, match="execution-lease-lost"):
        _execute_stage(
            packet,
            dispatch,
            forged,
            repository_root=ROOT,
            workspace=tmp_path / "workspace",
            hmac_key=KEY,
            registry=_registry,
            packet_store=_store,
            configuration=_config,
            authority=_auth,
        )


def test_superseded_lease_fails_closed_mid_execution(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    outcome = authority.acquire(
        idempotency_key="sha256:" + "1" * 64,
        packet_id="packet:live",
        dispatch_nonce="nonce:live",
        stage_id="stage:live",
    )
    permit = outcome.permit
    assert permit is not None
    authority.assert_active(permit)
    # Another worker supersedes the lease (new fence token) between two side effects.
    with sqlite3.connect(authority.path) as connection:
        connection.execute(
            "UPDATE execution_lease SET fence_token = ? WHERE idempotency_key = ?",
            ("superseded", permit.idempotency_key),
        )
        connection.commit()
    with pytest.raises(WorkerError, match="execution-lease-lost"):
        authority.assert_active(permit)


# ---- F-03: fail-closed authority selection ---------------------------------------------


def test_control_plane_mode_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WorkerError, match="execution-authority-unavailable"):
        resolve_execution_authority(
            workspace=tmp_path,
            environ={"L9_EXECUTION_AUTHORITY_MODE": "control-plane"},
        )


def test_local_mode_resolves_sqlite_authority(tmp_path: Path) -> None:
    authority = resolve_execution_authority(workspace=tmp_path, environ={})
    assert isinstance(authority, SqliteExecutionAuthority)


# ---- F-03 end-to-end: a completed stage acknowledges its lease -------------------------


def test_execute_stage_acknowledges_lease(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = LocalPacketRegistry(tmp_path / "registry.sqlite3")
    authority = SqliteExecutionAuthority(tmp_path / "lease.sqlite3")
    packet = _dispatch(tmp_path / "published-packet")
    with _callback_server() as (callback_url, _received):
        monkeypatch.setenv("L9_TEST_CALLBACK_URL", callback_url)
        outcome = execute_stage(
            packet,
            repository_root=ROOT,
            workspace=tmp_path / "workspace",
            hmac_key=KEY,
            registry=registry,
            authority=authority,
        )
    assert outcome.reused is False
    with sqlite3.connect(authority.path) as connection:
        row = connection.execute(
            "SELECT state FROM execution_lease WHERE idempotency_key = ?",
            (packet.header.idempotency_key,),
        ).fetchone()
    assert row is not None
    assert row[0] == "ACKNOWLEDGED"


# ---- F-05: OutputSink revalidates target state at commit --------------------------------


def _sink(tmp_path: Path) -> FileSystemOutputSink:
    return FileSystemOutputSink(
        tmp_path,
        WritePolicy(
            allowed_output_roots=(".",),
            allowed_artifact_kinds=("topology-packet",),
            allow_overwrite=True,
            require_expected_hash_for_replace=False,
        ),
    )


def _artifact(content: bytes) -> RenderedArtifact:
    return RenderedArtifact(
        logical_id="packet.json",
        destination_path="packet.json",
        artifact_kind="topology-packet",
        media_type="application/json",
        content=content,
        content_hash=artifact_hash(content),
    )


def test_create_race_fails_closed(tmp_path: Path) -> None:
    sink = _sink(tmp_path)
    sink.enqueue(WriteIntent(artifact=_artifact(b"planned")))
    plan = sink.plan()
    assert plan.entries[0].action == "create"
    # A file races into existence after planning but before commit.
    (tmp_path / "packet.json").write_bytes(b"raced-in")
    receipt = sink.commit()
    assert receipt.status == "failed"
    assert receipt.results[0].status == "failed"
    assert "stale plan" in receipt.results[0].message
    assert (tmp_path / "packet.json").read_bytes() == b"raced-in"


def test_replace_race_fails_closed(tmp_path: Path) -> None:
    target = tmp_path / "packet.json"
    target.write_bytes(b"original")
    sink = _sink(tmp_path)
    sink.enqueue(WriteIntent(artifact=_artifact(b"replacement")))
    plan = sink.plan()
    assert plan.entries[0].action == "replace"
    # The target changes after planning; the cached plan's assumptions are now stale.
    target.write_bytes(b"changed-underneath")
    receipt = sink.commit()
    assert receipt.status == "failed"
    assert "stale plan" in receipt.results[0].message
    assert target.read_bytes() == b"changed-underneath"


# ---- F-06: workflow trigger/profile contract check -------------------------------------


def test_workflow_profile_event_contract_flags_mismatch() -> None:
    spec = importlib.util.spec_from_file_location(
        "validate_workflows", ROOT / "scripts" / "validate_workflows.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    errors = module._check_analysis_profile_events(
        {"on": {"push": None}},
        "push) profile=pr_fast ;;",
    )
    assert any("does not permit event push" in error for error in errors)
    ok = module._check_analysis_profile_events(
        {"on": {"push": None}},
        "push) profile=merge ;;",
    )
    assert ok == []
