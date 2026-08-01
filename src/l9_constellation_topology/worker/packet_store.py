"""Packet-store adapters with identity-bound local and OCI verification."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from l9_constellation_topology.packets import (
    PacketRef,
    load_repository_model_bundle,
    load_topology_bundle,
)
from l9_constellation_topology.run import artifact_hash

from .errors import WorkerError


@dataclass(frozen=True)
class PublishedPacket:
    uri: str
    bundle_manifest_digest: str
    registry_manifest_digest: str | None = None
    staging_uri: str | None = None


def file_uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme not in {"", "file"}:
        raise ValueError(f"not a file URI: {uri}")
    raw = unquote(parsed.path) if parsed.scheme == "file" else uri
    if parsed.netloc and parsed.netloc not in {"", "localhost"}:
        raw = f"//{parsed.netloc}{raw}"
    return Path(raw).resolve()


def path_to_file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _bundle_manifest_digest(bundle_path: Path) -> str:
    manifest = bundle_path / "manifest.json"
    if not manifest.is_file():
        raise WorkerError(
            "packet-bundle-manifest-missing",
            f"published bundle lacks manifest.json: {bundle_path}",
            blocked=True,
        )
    return artifact_hash(manifest.read_bytes())


def _oci_repository(reference: str) -> str:
    value = reference.removeprefix("oci://").split("@", 1)[0]
    slash = value.rfind("/")
    colon = value.rfind(":")
    if colon > slash:
        value = value[:colon]
    return value



def _publication_staging_target(output_uri: str, bundle_path: Path) -> str:
    materialized, _ = load_topology_bundle(bundle_path)
    semantic_digest = materialized.packet.semantic_hash.removeprefix("sha256:")
    if len(semantic_digest) != 64 or any(
        character not in "0123456789abcdef" for character in semantic_digest
    ):
        raise WorkerError(
            "packet-semantic-hash-invalid",
            "Topology Packet semantic hash cannot form an OCI staging tag",
            blocked=True,
        )
    return f"{_oci_repository(output_uri)}:packet-{semantic_digest}"


def _extract_digest(value: object) -> str | None:
    if isinstance(value, dict):
        for key in ("digest", "manifestDigest", "manifest_digest"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.startswith("sha256:"):
                return candidate
        for child in value.values():
            candidate = _extract_digest(child)
            if candidate:
                return candidate
    if isinstance(value, list):
        for child in value:
            candidate = _extract_digest(child)
            if candidate:
                return candidate
    return None


def _assert_expected_topology(
    bundle_path: Path,
    *,
    expected: PacketRef,
    expected_bundle_manifest_digest: str,
) -> None:
    materialized, receipt = load_topology_bundle(bundle_path)
    packet = materialized.packet
    actual_manifest_digest = _bundle_manifest_digest(bundle_path)
    mismatches: list[str] = []
    if packet.packet_id != expected.packet_id:
        mismatches.append("packet_id")
    if packet.packet_type != expected.packet_type:
        mismatches.append("packet_type")
    if packet.packet_version != expected.packet_version:
        mismatches.append("packet_version")
    if packet.semantic_hash != expected.semantic_hash:
        mismatches.append("semantic_hash")
    if expected.artifact_hash is not None and packet.artifact_hash != expected.artifact_hash:
        mismatches.append("artifact_hash")
    if expected.validation_status != "passed" or receipt.status != "passed":
        mismatches.append("validation_status")
    if receipt.subject_packet_id != expected.packet_id:
        mismatches.append("validation_receipt_packet")
    if receipt.subject_semantic_hash != expected.semantic_hash:
        mismatches.append("validation_receipt_semantic_hash")
    if actual_manifest_digest != expected_bundle_manifest_digest:
        mismatches.append("bundle_manifest_digest")
    if mismatches:
        raise WorkerError(
            "published-packet-reference-mismatch",
            f"{expected.packet_id}: {', '.join(mismatches)}",
            blocked=True,
        )


class PacketStoreClient:
    def __init__(self, *, oras_executable: str = "oras", timeout_seconds: int = 300) -> None:
        self.oras_executable = oras_executable
        self.timeout_seconds = timeout_seconds

    def _oras(self) -> str:
        executable = shutil.which(self.oras_executable)
        if executable is None:
            raise WorkerError(
                "packet-store-client-unavailable",
                "the oras executable is required for OCI packet URIs",
                retryable=False,
                blocked=True,
            )
        return executable

    def resolve_input(
        self,
        reference: PacketRef,
        *,
        workspace: Path,
    ) -> Path:
        parsed = urlparse(reference.uri)
        if parsed.scheme in {"", "file"}:
            path = file_uri_to_path(reference.uri)
        elif parsed.scheme == "oci":
            if "@sha256:" not in reference.uri:
                raise WorkerError(
                    "packet-uri-not-immutable",
                    f"production OCI input must be digest-qualified: {reference.uri}",
                    blocked=True,
                )
            path = workspace / "inputs" / reference.packet_id.replace(":", "_")
            path.mkdir(parents=True, exist_ok=True)
            command = [
                self._oras(),
                "pull",
                reference.uri.removeprefix("oci://"),
                "--output",
                str(path),
            ]
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            if completed.returncode != 0:
                raise WorkerError(
                    "packet-download-failed",
                    completed.stderr.strip() or completed.stdout.strip(),
                    retryable=True,
                )
        else:
            raise WorkerError(
                "packet-uri-unsupported",
                f"unsupported packet URI scheme: {parsed.scheme or '<none>'}",
                blocked=True,
            )
        bundle = load_repository_model_bundle(path)
        packet = bundle.packet
        mismatches = []
        if packet.packet_id != reference.packet_id:
            mismatches.append("packet_id")
        if packet.semantic_hash != reference.semantic_hash:
            mismatches.append("semantic_hash")
        if packet.packet_version != reference.packet_version:
            mismatches.append("packet_version")
        if reference.artifact_hash is not None and packet.artifact_hash != reference.artifact_hash:
            mismatches.append("artifact_hash")
        if (
            reference.subject_id is not None
            and packet.subject.repository_id != reference.subject_id
        ):
            mismatches.append("subject_id")
        if packet.source_snapshot.revision != reference.source_revision:
            mismatches.append("source_revision")
        if reference.validation_status != "passed":
            mismatches.append("validation_status")
        if mismatches:
            raise WorkerError(
                "input-packet-reference-mismatch",
                f"{reference.packet_id}: {', '.join(mismatches)}",
                blocked=True,
            )
        return path

    def publish(self, bundle_path: Path, output_uri: str) -> PublishedPacket:
        parsed = urlparse(output_uri)
        bundle_manifest_digest = _bundle_manifest_digest(bundle_path)
        if parsed.scheme in {"", "file"}:
            expected = file_uri_to_path(output_uri)
            if bundle_path.resolve() != expected:
                raise WorkerError(
                    "file-store-path-mismatch",
                    f"bundle was committed at {bundle_path}, not configured output {expected}",
                    blocked=True,
                )
            load_topology_bundle(expected)
            return PublishedPacket(
                uri=path_to_file_uri(expected),
                bundle_manifest_digest=bundle_manifest_digest,
            )
        if parsed.scheme != "oci":
            raise WorkerError(
                "packet-uri-unsupported",
                f"unsupported output packet URI scheme: {parsed.scheme}",
                blocked=True,
            )
        files = tuple(
            path.relative_to(bundle_path).as_posix()
            for path in sorted(bundle_path.rglob("*"))
            if path.is_file()
        )
        target = _publication_staging_target(output_uri, bundle_path)
        command = [
            self._oras(),
            "push",
            target,
            "--format",
            "json",
            "--artifact-type",
            "application/vnd.quantum-l9.packet.bundle.v1+json",
            *[f"{path}:application/octet-stream" for path in files],
        ]
        completed = subprocess.run(
            command,
            cwd=bundle_path,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            raise WorkerError(
                "packet-publication-failed",
                completed.stderr.strip() or completed.stdout.strip(),
                retryable=True,
            )
        try:
            output = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise WorkerError(
                "packet-publication-digest-missing",
                "ORAS publication did not return machine-readable digest evidence",
                blocked=True,
            ) from exc
        registry_digest = _extract_digest(output)
        if registry_digest is None:
            raise WorkerError(
                "packet-publication-digest-missing",
                "ORAS publication result did not contain a sha256 manifest digest",
                blocked=True,
            )
        immutable_uri = f"oci://{_oci_repository(output_uri)}@{registry_digest}"
        return PublishedPacket(
            uri=immutable_uri,
            bundle_manifest_digest=bundle_manifest_digest,
            registry_manifest_digest=registry_digest,
            staging_uri=f"oci://{target}",
        )

    def _fetch_registry_descriptor_digest(self, output_uri: str) -> str:
        completed = subprocess.run(
            [
                self._oras(),
                "manifest",
                "fetch",
                "--descriptor",
                "--format",
                "json",
                output_uri.removeprefix("oci://"),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            raise WorkerError(
                "packet-verification-descriptor-failed",
                completed.stderr.strip() or completed.stdout.strip(),
                retryable=True,
            )
        try:
            descriptor = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise WorkerError(
                "packet-verification-descriptor-invalid",
                "registry descriptor response is not valid JSON",
                blocked=True,
            ) from exc
        digest = _extract_digest(descriptor)
        if digest is None:
            raise WorkerError(
                "packet-verification-descriptor-invalid",
                "registry descriptor response lacks a sha256 digest",
                blocked=True,
            )
        return digest

    def verify_published(
        self,
        output_uri: str,
        *,
        expected: PacketRef,
        expected_bundle_manifest_digest: str,
        expected_registry_manifest_digest: str | None,
        workspace: Path,
    ) -> str | None:
        parsed = urlparse(output_uri)
        if parsed.scheme in {"", "file"}:
            _assert_expected_topology(
                file_uri_to_path(output_uri),
                expected=expected,
                expected_bundle_manifest_digest=expected_bundle_manifest_digest,
            )
            return None
        if parsed.scheme != "oci":
            raise WorkerError(
                "packet-uri-unsupported",
                f"unsupported output packet URI scheme: {parsed.scheme}",
                blocked=True,
            )
        if "@sha256:" not in output_uri:
            raise WorkerError(
                "packet-uri-not-immutable",
                f"published OCI packet must be digest-qualified: {output_uri}",
                blocked=True,
            )
        uri_digest = output_uri.rsplit("@", 1)[1]
        if (
            expected_registry_manifest_digest is None
            or uri_digest != expected_registry_manifest_digest
        ):
            raise WorkerError(
                "registry-manifest-digest-mismatch",
                "published OCI URI digest does not match registry evidence",
                blocked=True,
            )
        descriptor_digest = self._fetch_registry_descriptor_digest(output_uri)
        if descriptor_digest != uri_digest:
            raise WorkerError(
                "registry-descriptor-digest-mismatch",
                "independently resolved registry descriptor does not match the immutable URI",
                blocked=True,
            )
        workspace.mkdir(parents=True, exist_ok=True)
        verification_path = Path(
            tempfile.mkdtemp(prefix="verify-published-", dir=workspace)
        )
        completed = subprocess.run(
            [
                self._oras(),
                "pull",
                output_uri.removeprefix("oci://"),
                "--output",
                str(verification_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            raise WorkerError(
                "packet-verification-download-failed",
                completed.stderr.strip() or completed.stdout.strip(),
                retryable=True,
            )
        _assert_expected_topology(
            verification_path,
            expected=expected,
            expected_bundle_manifest_digest=expected_bundle_manifest_digest,
        )
        return descriptor_digest
