"""Deterministic publication plan serialization and schema validation.

Serialization produces bytes only. Every write reaches the filesystem through
the ``io`` output sink boundary, exactly as canonical packet bundles do.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from l9_constellation_topology.io import RenderedArtifact
from l9_constellation_topology.packets.common import PacketBundleManifest, PacketFileEntry
from l9_constellation_topology.run.evidence import (
    artifact_hash,
    canonical_bytes,
    canonical_data,
    semantic_hash,
    utc_now,
)

from .contracts import MEMORY_INGEST_OPERATION, PublicationPlan

PUBLICATION_PLAN_SCHEMA_PATH = Path("schemas") / "topology-publication-plan.schema.json"
PLAN_DOCUMENT_NAME = "publication-plan.json"
INTENTS_DOCUMENT_NAME = "intents/memory-ingest.json"


class PublicationBundleError(ValueError):
    """Raised when a publication plan fails serialization or schema validation."""


def publication_plan_bytes(plan: PublicationPlan) -> bytes:
    """Return the canonical, deterministic serialization of a plan."""
    return canonical_bytes(plan) + b"\n"


def eligible_intent_document(plan: PublicationPlan) -> dict[str, Any]:
    """Return the downstream-facing document carrying only eligible intents."""
    return {
        "operation": MEMORY_INGEST_OPERATION,
        "plan_id": plan.plan_id,
        "plan_semantic_hash": plan.semantic_hash,
        "source_topology_packet_id": plan.source_topology_packet.packet_id,
        "source_topology_semantic_hash": plan.source_topology_semantic_hash,
        "policy_hash": plan.policy_hash,
        "intents": [
            canonical_data(candidate.memory_intent) for candidate in plan.eligible_candidates
        ],
    }


def eligible_intents_bytes(plan: PublicationPlan) -> bytes:
    """Return the canonical serialization of the eligible-intent document."""
    return canonical_bytes(eligible_intent_document(plan)) + b"\n"


def load_publication_plan_schema(repository_root: Path) -> dict[str, Any]:
    """Load the checked-in publication plan JSON Schema."""
    path = repository_root.resolve() / PUBLICATION_PLAN_SCHEMA_PATH
    if not path.is_file():
        raise PublicationBundleError(f"publication plan schema is missing: {path}")
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationBundleError(f"publication plan schema is unreadable: {exc}") from exc
    if not isinstance(schema, dict):
        raise PublicationBundleError("publication plan schema must be a JSON object")
    return schema


def validate_publication_plan(plan: PublicationPlan, *, repository_root: Path) -> tuple[str, ...]:
    """Validate a plan against the checked-in schema and return ordered errors."""
    schema = load_publication_plan_schema(repository_root)
    document = canonical_data(plan)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    return tuple(f"{list(error.path)}: {error.message}" for error in errors)


def _artifact(
    *,
    logical_id: str,
    destination_path: str,
    content: bytes,
    semantic_digest: str | None,
    source_refs: tuple[str, ...],
) -> RenderedArtifact:
    return RenderedArtifact(
        logical_id=logical_id,
        destination_path=destination_path,
        artifact_kind="publication-plan",
        media_type="application/json",
        content=content,
        content_hash=artifact_hash(content),
        semantic_hash=semantic_digest,
        source_refs=source_refs,
    )


def build_publication_plan_artifacts(
    plan: PublicationPlan,
    *,
    created_at: datetime | None = None,
) -> tuple[RenderedArtifact, ...]:
    """Render a complete publication plan bundle as immutable artifacts."""
    source_refs = (plan.source_topology_packet.packet_id,)
    artifacts = [
        _artifact(
            logical_id="topology-publication-plan",
            destination_path=PLAN_DOCUMENT_NAME,
            content=publication_plan_bytes(plan),
            semantic_digest=plan.semantic_hash,
            source_refs=source_refs,
        ),
        _artifact(
            logical_id="topology-publication-intents",
            destination_path=INTENTS_DOCUMENT_NAME,
            content=eligible_intents_bytes(plan),
            semantic_digest=plan.semantic_hash,
            source_refs=source_refs,
        ),
    ]
    entries = tuple(
        PacketFileEntry(
            path=item.destination_path,
            media_type=item.media_type,
            content_hash=item.content_hash,
            size_bytes=len(item.content),
        )
        for item in sorted(artifacts, key=lambda artifact: artifact.destination_path)
    )
    manifest = PacketBundleManifest(
        packet_id=plan.plan_id,
        packet_type=plan.plan_type,
        packet_version=plan.plan_version,
        semantic_hash=plan.semantic_hash,
        artifact_hash=semantic_hash(entries),
        files=entries,
        created_at=created_at if created_at is not None else utc_now(),
    )
    artifacts.append(
        _artifact(
            logical_id="topology-publication-manifest",
            destination_path="manifest.json",
            content=canonical_bytes(manifest) + b"\n",
            semantic_digest=manifest.artifact_hash,
            source_refs=source_refs,
        )
    )
    return tuple(sorted(artifacts, key=lambda artifact: artifact.destination_path))
