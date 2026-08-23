"""Packet-type-aware post-write verification for staged packet bundles.

A packet bundle is verified by loading it back with the loader that owns its
declared ``packet_type``. Verifying a Repository Model bundle with Topology
Packet semantics is a category error: it reports a contract violation that does
not exist and hides the one that might.

This module is the single dispatch point. It never relaxes verification, and an
unrecognized packet type fails closed rather than defaulting to a loader.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .corpus_bundle import load_corpus_intelligence_bundle
from .loader import (
    PacketLoadError,
    load_repository_model_bundle,
    load_topology_bundle,
    verify_bundle_manifest,
)

#: Declared bundle packet type to the loader that owns its verification.
BUNDLE_VERIFIERS: dict[str, Any] = {
    "l9.topology": load_topology_bundle,
    "l9.repository-model": load_repository_model_bundle,
    "l9.corpus-intelligence": load_corpus_intelligence_bundle,
}


class BundleVerificationError(PacketLoadError):
    """Raised when a staged bundle fails verification under its own contract.

    The error carries the operator-actionable coordinates of the failure so a
    caller can report which stage rejected which packet type without re-deriving
    them from prose.
    """

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        packet_type: str | None = None,
        code: str = "bundle-verification-failed",
        member: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.packet_type = packet_type
        self.code = code
        self.member = member


def bundle_packet_type(bundle_root: Path) -> str:
    """Return the declared packet type of a staged bundle."""
    try:
        return verify_bundle_manifest(bundle_root).packet_type
    except PacketLoadError as exc:
        raise BundleVerificationError(
            str(exc),
            stage="bundle-manifest-verification",
            code="bundle-manifest-invalid",
            member="manifest.json",
        ) from exc


def verify_packet_bundle(bundle_root: Path) -> str:
    """Verify a staged bundle with the loader that owns its packet type.

    Returns the verified packet type. Raises :class:`BundleVerificationError`
    when the manifest is unreadable, the packet type is unsupported, or the
    owning loader rejects the bundle.
    """
    packet_type = bundle_packet_type(bundle_root)
    verifier = BUNDLE_VERIFIERS.get(packet_type)
    if verifier is None:
        supported = ", ".join(sorted(BUNDLE_VERIFIERS))
        raise BundleVerificationError(
            f"no verifier is bound for packet type {packet_type!r}; supported types are {supported}",
            stage="bundle-post-write-verification",
            packet_type=packet_type,
            code="unsupported-bundle-packet-type",
        )
    try:
        verifier(bundle_root)
    except PacketLoadError as exc:
        raise BundleVerificationError(
            str(exc),
            stage="bundle-post-write-verification",
            packet_type=packet_type,
            code="bundle-load-failed",
        ) from exc
    return packet_type
