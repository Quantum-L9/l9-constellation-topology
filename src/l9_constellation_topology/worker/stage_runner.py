"""Exact-revision GitHub Actions stage worker for Topology Packet compilation."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from l9_constellation_topology.compiler import (
    COMPILER_VERSION,
    TopologyCompilationError,
    calculate_idempotency_key,
    commit_compilation,
    compile_topology,
)
from l9_constellation_topology.config import ResolvedConfiguration, resolve_configuration
from l9_constellation_topology.io import (
    FileSystemOutputSink,
    PacketBundleOutputSink,
    RenderedArtifact,
    WriteIntent,
    WritePolicy,
)
from l9_constellation_topology.packets import (
    CallbackRef,
    PacketRef,
    ReuseReceipt,
    StageDispatchPayload,
    StageResult,
    TransportPacket,
)
from l9_constellation_topology.run import (
    artifact_hash,
    canonical_bytes,
    canonical_json,
    semantic_hash,
)

from .callback import send_callback
from .errors import WorkerError
from .failure import execution_failure
from .packet_store import PacketStoreClient, file_uri_to_path, path_to_file_uri
from .registry import LocalPacketRegistry, RegistryEntry
from .signature import verify_transport_packet
from .transport_factory import build_callback_transport_packet

TARGET_REPOSITORY = "Quantum-L9/l9-constellation-topology"


@dataclass(frozen=True)
class StageExecutionOutcome:
    payload: StageResult | ReuseReceipt
    reused: bool
    output_bundle: Path | None


def _current_git_revision(repository_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise WorkerError(
            "source-revision-unavailable",
            completed.stderr.strip() or "git revision cannot be resolved",
            blocked=True,
        )
    return completed.stdout.strip()


def _normalize_revision(value: str) -> str:
    return value.removeprefix("git:")


def _response_key_id(packet: TransportPacket) -> str:
    configured = os.environ.get("L9_RESULT_HMAC_KEY_ID")
    if configured:
        return configured
    if packet.security.signatures:
        return packet.security.signatures[0].key_id
    return "foundational-hmac-v1"


def validate_stage_dispatch(
    packet: TransportPacket,
    *,
    configuration: ResolvedConfiguration,
    repository_root: Path,
    hmac_key: bytes,
    enforce_source_revision: bool = True,
) -> StageDispatchPayload:
    packet_profile = configuration.packet_profile
    allowed_algorithms = tuple(
        str(value) for value in packet_profile.get("allowed_signature_algorithms", ())
    )
    allowed_key_ids = tuple(str(value) for value in packet_profile.get("allowed_key_ids", ()))
    if packet_profile.get("require_signature", True):
        verify_transport_packet(
            packet,
            key=hmac_key,
            allowed_algorithms=allowed_algorithms,
            allowed_key_ids=allowed_key_ids,
        )
    if packet.header.packet_type != "command":
        raise WorkerError(
            "dispatch-packet-type-invalid",
            "topology stage dispatch requires header.packet_type=command",
            blocked=True,
        )
    if packet.header.schema_version != "transport-packet/1.0.0":
        raise WorkerError(
            "transport-version-unsupported",
            f"unsupported transport schema: {packet.header.schema_version}",
            blocked=True,
        )
    dispatch = StageDispatchPayload.model_validate(packet.payload)
    data = dispatch.data
    allowed_payloads = {str(value) for value in packet_profile.get("allowed_payload_schemas", ())}
    if dispatch.payload_schema not in allowed_payloads:
        raise WorkerError(
            "dispatch-payload-schema-forbidden",
            f"payload schema is not allowlisted: {dispatch.payload_schema}",
            blocked=True,
        )
    if packet.header.action != data.action:
        raise WorkerError(
            "dispatch-action-mismatch",
            "TransportPacket header action does not match stage payload action",
            blocked=True,
        )
    if packet.header.workflow_id not in {None, data.workflow_id}:
        raise WorkerError(
            "dispatch-workflow-mismatch",
            "TransportPacket workflow_id does not match stage payload workflow_id",
            blocked=True,
        )
    allowed_actions = {str(value) for value in packet_profile.get("allowed_actions", ())}
    if data.action not in allowed_actions:
        raise WorkerError(
            "dispatch-action-forbidden",
            f"action is not allowlisted: {data.action}",
            blocked=True,
        )
    allowed_repositories = {
        str(value) for value in packet_profile.get("allowed_target_repositories", ())
    }
    if (
        data.target_repository not in allowed_repositories
        or data.target_repository != TARGET_REPOSITORY
    ):
        raise WorkerError(
            "dispatch-target-forbidden",
            f"target repository is not allowlisted: {data.target_repository}",
            blocked=True,
        )
    target_revision = _normalize_revision(data.target_revision)
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", target_revision) is None:
        raise WorkerError(
            "target-revision-invalid",
            "target revision must be an exact lowercase Git object ID",
            blocked=True,
        )
    if enforce_source_revision:
        current_revision = _current_git_revision(repository_root)
        if target_revision != current_revision:
            raise WorkerError(
                "target-revision-mismatch",
                f"worker checkout is {current_revision}, dispatch requires {data.target_revision}",
                blocked=True,
            )
    expected_profile_hash = semantic_hash(configuration.topology_profile)
    if (
        data.profile.id != configuration.profile_id
        or data.profile.version != configuration.profile_version
        or data.profile.hash != expected_profile_hash
    ):
        raise WorkerError(
            "topology-profile-mismatch",
            "dispatch profile does not match the checked-out compiler profile",
            blocked=True,
        )
    if packet_profile.get("require_callback", False) and data.callback is None:
        raise WorkerError(
            "dispatch-callback-missing",
            "the foundational worker profile requires a stage callback",
            blocked=True,
        )
    if packet_profile.get("require_output_uri", False) and data.output_uri is None:
        raise WorkerError(
            "dispatch-output-uri-missing",
            "the foundational worker profile requires an immutable output URI",
            blocked=True,
        )
    required_versions = {
        str(value)
        for value in configuration.topology_profile.get("required_repository_packet_versions", ())
    }
    if not data.input_packets:
        raise WorkerError(
            "input-packets-missing",
            "compile-topology requires at least one Repository Model Packet",
            blocked=True,
        )
    for reference in data.input_packets:
        if reference.packet_type != "l9.repository-model":
            raise WorkerError(
                "input-packet-type-invalid",
                f"expected l9.repository-model, got {reference.packet_type}",
                blocked=True,
            )
        if reference.packet_version not in required_versions:
            raise WorkerError(
                "unsupported-contract-version",
                f"Repository Model Packet version is not supported: {reference.packet_version}",
                blocked=True,
            )
        if reference.validation_status != "passed":
            raise WorkerError(
                "input-validation-failed",
                f"input packet is not validated: {reference.packet_id}",
                blocked=True,
            )
        if reference.source_revision is None:
            raise WorkerError(
                "input-source-revision-missing",
                f"input packet lacks source revision: {reference.packet_id}",
                blocked=True,
            )
    expected_idempotency = calculate_idempotency_key(
        data.input_packets,
        configuration,
        compiler_build_identity=target_revision,
    )
    if packet.header.idempotency_key != expected_idempotency:
        raise WorkerError(
            "idempotency-key-mismatch",
            f"expected {expected_idempotency}, got {packet.header.idempotency_key}",
            blocked=True,
        )
    if packet.provenance.get("resolved_by_gate") is not False:
        raise WorkerError(
            "dispatch-resolution-invalid",
            "foundational profile requires provenance.resolved_by_gate=false",
            blocked=True,
        )
    if packet.provenance.get("resolver") != packet_profile.get("resolver"):
        raise WorkerError(
            "dispatch-resolver-invalid",
            "dispatch resolver does not match the foundational packet profile",
            blocked=True,
        )
    return dispatch


def _bundle_output_location(
    *,
    configured_uri: str | None,
    workspace: Path,
    packet_id: str,
) -> tuple[Path, str]:
    if configured_uri is None:
        path = workspace / "published" / packet_id.replace(":", "_")
        return path, path_to_file_uri(path)
    parsed = urlparse(configured_uri)
    if parsed.scheme in {"", "file"}:
        destination = file_uri_to_path(configured_uri)
        return destination, path_to_file_uri(destination)
    if parsed.scheme == "oci":
        path = workspace / "outgoing" / packet_id.replace(":", "_")
        return path, configured_uri
    raise WorkerError(
        "packet-uri-unsupported",
        f"unsupported output packet URI scheme: {parsed.scheme}",
        blocked=True,
    )


def _persist_commit_receipt(
    workspace: Path,
    packet_id: str,
    receipt: object,
) -> str:
    content = canonical_bytes(receipt) + b"\n"
    directory = workspace / "execution-receipts"
    destination = f"{packet_id.replace(':', '_')}-commit-receipt.json"
    artifact = RenderedArtifact(
        logical_id="stage-commit-receipt",
        destination_path=destination,
        artifact_kind="commit-receipt",
        media_type="application/json",
        content=content,
        content_hash=artifact_hash(content),
    )
    sink = FileSystemOutputSink(
        directory,
        WritePolicy(
            allowed_output_roots=(".",),
            allowed_artifact_kinds=("commit-receipt",),
            allow_overwrite=False,
            require_expected_hash_for_replace=False,
            atomic_writes=True,
        ),
    )
    sink.enqueue(WriteIntent(artifact=artifact))
    write_receipt = sink.commit()
    if write_receipt.status != "passed":
        raise WorkerError(
            "commit-receipt-persistence-failed",
            write_receipt.model_dump_json(),
            retryable=True,
        )
    return path_to_file_uri(directory / destination)


def _send_signed_callback(
    request_packet: TransportPacket,
    callback: CallbackRef,
    payload: object,
    *,
    hmac_key: bytes,
    callback_policy: dict[str, object],
) -> None:
    signed = build_callback_transport_packet(
        request_packet,
        payload,
        key=hmac_key,
        key_id=_response_key_id(request_packet),
    )
    send_callback(callback, signed, callback_policy=callback_policy)


def _execute_validated_stage(
    packet: TransportPacket,
    dispatch: StageDispatchPayload,
    *,
    repository_root: Path,
    workspace: Path,
    hmac_key: bytes,
    registry: LocalPacketRegistry,
    packet_store: PacketStoreClient,
    configuration: ResolvedConfiguration,
) -> StageExecutionOutcome:
    data = dispatch.data
    idempotency_key = packet.header.idempotency_key
    existing = registry.get(idempotency_key)
    if existing is not None:
        bundle_manifest_digest = existing.metadata.get("bundle_manifest_digest")
        if not bundle_manifest_digest:
            raise WorkerError(
                "registry-publication-evidence-missing",
                "registry entry lacks bundle manifest digest",
                blocked=True,
            )
        packet_store.verify_published(
            existing.packet_ref.uri,
            expected=existing.packet_ref,
            expected_bundle_manifest_digest=bundle_manifest_digest,
            expected_registry_manifest_digest=existing.metadata.get("registry_manifest_digest"),
            workspace=workspace / "reuse-verify",
        )
        reuse = ReuseReceipt(
            idempotency_key=idempotency_key,
            reused_packet=existing.packet_ref,
        )
        if data.callback is not None:
            _send_signed_callback(
                packet,
                data.callback,
                reuse,
                hmac_key=hmac_key,
                callback_policy=configuration.callback_policy,
            )
            registry.acknowledge(idempotency_key)
        return StageExecutionOutcome(payload=reuse, reused=True, output_bundle=None)

    input_paths = tuple(
        packet_store.resolve_input(reference, workspace=workspace)
        for reference in data.input_packets
    )
    try:
        compilation = compile_topology(repository_root, input_paths)
    except TopologyCompilationError as exc:
        raise WorkerError(
            "topology-invariant-failed",
            exc.receipt.model_dump_json(),
            blocked=True,
        ) from exc
    packet_id = compilation.materialized.packet.packet_id
    bundle_path, publish_uri = _bundle_output_location(
        configured_uri=data.output_uri,
        workspace=workspace,
        packet_id=packet_id,
    )
    commit_receipt = commit_compilation(
        compilation,
        PacketBundleOutputSink(bundle_path, allow_overwrite=False),
    )
    if commit_receipt.status != "passed":
        raise WorkerError(
            "packet-bundle-commit-failed",
            commit_receipt.model_dump_json(),
            blocked=True,
        )
    commit_uri = _persist_commit_receipt(workspace, packet_id, commit_receipt)
    published = packet_store.publish(bundle_path, publish_uri)
    output_packet = PacketRef(
        packet_id=packet_id,
        packet_type=compilation.materialized.packet.packet_type,
        packet_version=compilation.materialized.packet.packet_version,
        uri=published.uri,
        semantic_hash=compilation.materialized.packet.semantic_hash,
        artifact_hash=compilation.materialized.packet.artifact_hash,
        validation_status="passed",
        subject_id="constellation:foundational-repository-intelligence",
        source_revision=data.target_revision,
    )
    packet_store.verify_published(
        published.uri,
        expected=output_packet,
        expected_bundle_manifest_digest=published.bundle_manifest_digest,
        expected_registry_manifest_digest=published.registry_manifest_digest,
        workspace=workspace / "publish-verify",
    )

    validation_uri = f"{published.uri}#receipts/validation-receipt.json"
    registry.register(
        RegistryEntry(
            idempotency_key=idempotency_key,
            packet_ref=output_packet,
            validation_receipt_uri=validation_uri,
            commit_receipt_uri=commit_uri,
            metadata={
                "run_id": data.run_id,
                "stage_id": data.stage_id,
                "compiler_version": COMPILER_VERSION,
                "bundle_manifest_digest": published.bundle_manifest_digest,
                **(
                    {"registry_manifest_digest": published.registry_manifest_digest}
                    if published.registry_manifest_digest
                    else {}
                ),
            },
        )
    )
    result = StageResult(
        run_id=data.run_id,
        stage_id=data.stage_id,
        output_packet=output_packet,
        validation_receipt_uri=validation_uri,
        commit_receipt_uri=commit_uri,
        idempotency_key=idempotency_key,
    )
    if data.callback is not None:
        _send_signed_callback(
            packet,
            data.callback,
            result,
            hmac_key=hmac_key,
            callback_policy=configuration.callback_policy,
        )
        registry.acknowledge(idempotency_key)
    return StageExecutionOutcome(payload=result, reused=False, output_bundle=bundle_path)


def execute_stage(
    packet: TransportPacket,
    *,
    repository_root: Path,
    workspace: Path,
    hmac_key: bytes,
    registry: LocalPacketRegistry,
    packet_store: PacketStoreClient | None = None,
) -> StageExecutionOutcome:
    repository_root = repository_root.resolve()
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    configuration = resolve_configuration(repository_root)
    dispatch = validate_stage_dispatch(
        packet,
        configuration=configuration,
        repository_root=repository_root,
        hmac_key=hmac_key,
    )
    return _execute_validated_stage(
        packet,
        dispatch,
        repository_root=repository_root,
        workspace=workspace,
        hmac_key=hmac_key,
        registry=registry,
        packet_store=packet_store or PacketStoreClient(),
        configuration=configuration,
    )


def _load_transport_packet(path: Path) -> TransportPacket:
    try:
        return TransportPacket.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkerError(
            "dispatch-packet-invalid",
            f"cannot load dispatch packet: {exc}",
            blocked=True,
        ) from exc


def run_worker(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="l9-topology-worker")
    parser.add_argument("--dispatch-file", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workspace", default=".l9-worker")
    parser.add_argument("--registry-file")
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Validate the signed dispatch before using its target revision.",
    )
    args = parser.parse_args(argv)

    packet: TransportPacket | None = None
    dispatch: StageDispatchPayload | None = None
    dispatch_validated = False
    key_value = os.environ.get("L9_DISPATCH_HMAC_KEY")
    try:
        if not key_value:
            raise WorkerError(
                "dispatch-key-missing",
                "L9_DISPATCH_HMAC_KEY is required",
                blocked=True,
            )
        packet = _load_transport_packet(Path(args.dispatch_file))
        repository_root = Path(args.repo_root).resolve()
        workspace = Path(args.workspace).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        configuration = resolve_configuration(repository_root)
        dispatch = validate_stage_dispatch(
            packet,
            configuration=configuration,
            repository_root=repository_root,
            hmac_key=key_value.encode("utf-8"),
            enforce_source_revision=not args.preflight,
        )
        dispatch_validated = True
        if args.preflight:
            target_revision = _normalize_revision(dispatch.data.target_revision)
            print(
                canonical_json(
                    {
                        "status": "passed",
                        "target_repository": dispatch.data.target_repository,
                        "target_revision": target_revision,
                        "uses_ghcr": bool(
                            dispatch.data.output_uri
                            and dispatch.data.output_uri.startswith("oci://ghcr.io/")
                        ),
                    }
                )
            )
            return 0
        registry_path = Path(
            args.registry_file
            or os.environ.get("L9_PACKET_REGISTRY_FILE", str(workspace / "packet-registry.sqlite3"))
        )
        outcome = _execute_validated_stage(
            packet,
            dispatch,
            repository_root=repository_root,
            workspace=workspace,
            hmac_key=key_value.encode("utf-8"),
            registry=LocalPacketRegistry(registry_path),
            packet_store=PacketStoreClient(),
            configuration=configuration,
        )
        print(canonical_json(outcome.payload))
        return 0
    except Exception as exc:
        if dispatch_validated and dispatch is not None and packet is not None and key_value:
            failure = execution_failure(
                run_id=dispatch.data.run_id,
                stage_id=dispatch.data.stage_id,
                input_packet_ids=tuple(ref.packet_id for ref in dispatch.data.input_packets),
                error=exc,
            )
            print(canonical_json(failure), file=sys.stderr)
            if dispatch.data.callback is not None and not (
                isinstance(exc, WorkerError) and exc.code == "callback-failed"
            ):
                try:
                    _send_signed_callback(
                        packet,
                        dispatch.data.callback,
                        failure,
                        hmac_key=key_value.encode("utf-8"),
                        callback_policy=configuration.callback_policy,
                    )
                except WorkerError as callback_error:
                    print(str(callback_error), file=sys.stderr)
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def main() -> None:
    raise SystemExit(run_worker())


if __name__ == "__main__":
    main()
