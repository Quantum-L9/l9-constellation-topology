"""Packet-store adapters for local files and GHCR-compatible OCI artifacts."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

from l9_constellation_topology.packets import (
    PacketRef,
    load_repository_model_bundle,
    load_topology_bundle,
)

from .errors import WorkerError


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

    def publish(self, bundle_path: Path, output_uri: str) -> str:
        parsed = urlparse(output_uri)
        if parsed.scheme in {"", "file"}:
            expected = file_uri_to_path(output_uri)
            if bundle_path.resolve() != expected:
                raise WorkerError(
                    "file-store-path-mismatch",
                    f"bundle was committed at {bundle_path}, not configured output {expected}",
                    blocked=True,
                )
            load_topology_bundle(expected)
            return path_to_file_uri(expected)
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
        command = [
            self._oras(),
            "push",
            output_uri,
            "--artifact-type",
            "application/vnd.quantum-l9.packet.bundle.v1+json",
            *[f"{path}:application/octet-stream" for path in files],
        ]
        command[2] = output_uri.removeprefix("oci://")
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
        return output_uri

    def verify_published(self, output_uri: str, *, workspace: Path) -> None:
        parsed = urlparse(output_uri)
        if parsed.scheme in {"", "file"}:
            load_topology_bundle(file_uri_to_path(output_uri))
            return
        if parsed.scheme != "oci":
            raise WorkerError(
                "packet-uri-unsupported",
                f"unsupported output packet URI scheme: {parsed.scheme}",
                blocked=True,
            )
        verification_path = workspace / "verify-published"
        verification_path.mkdir(parents=True, exist_ok=True)
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
        load_topology_bundle(verification_path)
