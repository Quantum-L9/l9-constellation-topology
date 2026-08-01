from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import ValidationError

from l9_constellation_topology.compiler import calculate_idempotency_key
from l9_constellation_topology.config import resolve_configuration
from l9_constellation_topology.packets import (
    CallbackRef,
    PacketRef,
    StageDispatchData,
    StageDispatchPayload,
    StageProfileRef,
    TransportPacket,
    load_repository_model_bundle,
    load_topology_bundle,
)
from l9_constellation_topology.run import semantic_hash
from l9_constellation_topology.worker import (
    LocalPacketRegistry,
    WorkerError,
    build_transport_packet,
    execute_stage,
    validate_stage_dispatch,
    verify_transport_packet,
)
from l9_constellation_topology.worker.callback import (
    ResolvedCallback,
    _validate_endpoint,
    path_is_allowed,
    send_callback,
)

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
def callback_server() -> Iterator[tuple[str, list[dict[str, object]]]]:
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


def _dispatch(output: Path, *, revision: str | None = None) -> TransportPacket:
    configuration = resolve_configuration(ROOT)
    refs = _input_refs()
    target_revision = revision or _git_revision()
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
            callback=CallbackRef(callback_id="local-integration-test"),
            output_uri=output.resolve().as_uri(),
        )
    )
    return build_transport_packet(
        payload=payload,
        packet_type="command",
        action="compile-topology",
        idempotency_key=calculate_idempotency_key(
            refs,
            configuration,
            compiler_build_identity=target_revision.removeprefix("git:"),
        ),
        trace_id="trace:test",
        correlation_id="correlation:test",
        workflow_id="foundational-repository-intelligence",
        key=KEY,
        key_id=KEY_ID,
        provenance={"resolved_by_gate": False, "resolver": "l9-ci-core"},
    )


def test_worker_compiles_callbacks_and_reuses_registered_packet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = LocalPacketRegistry(tmp_path / "registry.sqlite3")
    output = tmp_path / "published-packet"
    with callback_server() as (callback_url, received):
        monkeypatch.setenv("L9_TEST_CALLBACK_URL", callback_url)
        dispatch = _dispatch(output)
        first = execute_stage(
            dispatch,
            repository_root=ROOT,
            workspace=tmp_path / "workspace",
            hmac_key=KEY,
            registry=registry,
        )
        assert first.reused is False
        assert first.output_bundle == output
        materialized, validation = load_topology_bundle(output)
        assert validation.status == "passed"
        assert materialized.packet.packet_id == first.payload.output_packet.packet_id
        entry = registry.get(dispatch.header.idempotency_key)
        assert entry is not None
        assert entry.status == "acknowledged"
        assert entry.metadata["bundle_manifest_digest"].startswith("sha256:")

        assert len(received) == 1
        callback_packet = TransportPacket.model_validate(received[0])
        verify_transport_packet(
            callback_packet,
            key=KEY,
            allowed_algorithms=("hmac-sha256",),
            allowed_key_ids=(KEY_ID,),
        )
        assert callback_packet.payload["payload_schema"] == "l9.stage-result/1.0.0"

        second = execute_stage(
            dispatch,
            repository_root=ROOT,
            workspace=tmp_path / "workspace-second",
            hmac_key=KEY,
            registry=registry,
        )
        assert second.reused is True
        assert second.output_bundle is None
        assert len(received) == 2
        reuse_packet = TransportPacket.model_validate(received[1])
        assert reuse_packet.payload["payload_schema"] == "l9.reuse-receipt/1.0.0"


def test_preflight_validates_signature_before_checkout_revision(tmp_path: Path) -> None:
    configuration = resolve_configuration(ROOT)
    dispatch = _dispatch(tmp_path / "out", revision="git:" + "a" * 40)
    validated = validate_stage_dispatch(
        dispatch,
        configuration=configuration,
        repository_root=ROOT,
        hmac_key=KEY,
        enforce_source_revision=False,
    )
    assert validated.data.target_revision == "git:" + "a" * 40


def test_preflight_rejects_non_object_revision(tmp_path: Path) -> None:
    configuration = resolve_configuration(ROOT)
    dispatch = _dispatch(tmp_path / "out")
    payload = StageDispatchPayload.model_validate(dispatch.payload).model_copy(
        update={
            "data": StageDispatchPayload.model_validate(dispatch.payload).data.model_copy(
                update={"target_revision": "main\nmalicious"}
            )
        }
    )
    tampered = build_transport_packet(
        payload=payload,
        packet_type="command",
        action="compile-topology",
        idempotency_key=dispatch.header.idempotency_key,
        trace_id="trace:test",
        correlation_id="correlation:test",
        workflow_id="foundational-repository-intelligence",
        key=KEY,
        key_id=KEY_ID,
        provenance={"resolved_by_gate": False, "resolver": "l9-ci-core"},
    )
    with pytest.raises(WorkerError, match="target-revision-invalid"):
        validate_stage_dispatch(
            tampered,
            configuration=configuration,
            repository_root=ROOT,
            hmac_key=KEY,
            enforce_source_revision=False,
        )


def test_worker_blocks_wrong_checkout_revision(tmp_path: Path) -> None:
    dispatch = _dispatch(tmp_path / "out", revision="git:" + "d" * 40)
    with pytest.raises(WorkerError, match="target-revision-mismatch"):
        execute_stage(
            dispatch,
            repository_root=ROOT,
            workspace=tmp_path / "workspace",
            hmac_key=KEY,
            registry=LocalPacketRegistry(tmp_path / "registry.sqlite3"),
        )


def test_worker_blocks_tampered_dispatch_before_callback(tmp_path: Path) -> None:
    dispatch = _dispatch(tmp_path / "out")
    tampered = dispatch.model_copy(
        update={
            "payload": {
                **dispatch.payload,
                "data": {**dispatch.payload["data"], "run_id": "run:tampered"},
            }
        }
    )
    with pytest.raises(WorkerError, match="transport-signature-invalid"):
        execute_stage(
            tampered,
            repository_root=ROOT,
            workspace=tmp_path / "workspace",
            hmac_key=KEY,
            registry=LocalPacketRegistry(tmp_path / "registry.sqlite3"),
        )


def test_callback_contract_rejects_packet_selected_url_and_secret() -> None:
    with pytest.raises(ValidationError):
        CallbackRef.model_validate(
            {
                "callback_id": "topology-control-plane",
                "url": "https://attacker.invalid/callback",
                "token_ref": "env:SECRET",
            }
        )


def test_callback_id_must_exist_in_local_policy() -> None:
    with pytest.raises(WorkerError, match="callback-id-forbidden"):
        send_callback(
            CallbackRef(callback_id="not-allowlisted"),
            {"status": "test"},
            callback_policy=resolve_configuration(ROOT).callback_policy,
            attempts=1,
        )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/api/results", True),
        ("/api/results/run-123", True),
        ("/api/results/", True),
        ("/api/results-evil", False),
        ("/api/result", False),
        ("/api/results%2fevil", False),
        ("/api/results%2Fevil", False),
        ("/api/results%5cevil", False),
        ("/api/results%5Cevil", False),
    ],
)
def test_callback_path_policy_uses_segment_boundaries(path: str, expected: bool) -> None:
    assert path_is_allowed(path, "/api/results") is expected


def test_callback_endpoint_rejects_encoded_separator_before_request() -> None:
    endpoint = ResolvedCallback(
        callback_id="test",
        url="https://control.example/api/results%2fevil",
        token=None,
        allow_loopback=False,
        allowed_path_prefix="/api/results",
        expected_hosts=("control.example",),
        expected_port=443,
    )
    with pytest.raises(WorkerError, match="callback-path-forbidden"):
        _validate_endpoint(endpoint)


def test_callback_endpoint_enforces_expected_host_and_port() -> None:
    wrong_host = ResolvedCallback(
        callback_id="test",
        url="https://other.example/api/results",
        token=None,
        allow_loopback=False,
        allowed_path_prefix="/api/results",
        expected_hosts=("control.example",),
        expected_port=443,
    )
    with pytest.raises(WorkerError, match="callback-host-forbidden"):
        _validate_endpoint(wrong_host)

    wrong_port = ResolvedCallback(
        callback_id="test",
        url="https://control.example:8443/api/results",
        token=None,
        allow_loopback=False,
        allowed_path_prefix="/api/results",
        expected_hosts=("control.example",),
        expected_port=443,
    )
    with pytest.raises(WorkerError, match="callback-port-forbidden"):
        _validate_endpoint(wrong_port)


def test_disabled_production_callback_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("L9_CONTROL_API_URL", "https://control.example/api/results")
    monkeypatch.setenv("L9_CALLBACK_TOKEN", "test-token")
    with pytest.raises(WorkerError, match="callback-id-disabled"):
        send_callback(
            CallbackRef(callback_id="topology-control-plane"),
            {"status": "test"},
            callback_policy=resolve_configuration(ROOT).callback_policy,
            attempts=1,
        )
