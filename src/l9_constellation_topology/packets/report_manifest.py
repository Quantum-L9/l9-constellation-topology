"""Report projection manifest contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.run.evidence import semantic_hash, utc_now

from .common import Producer


class ReportRef(FrozenModel):
    report_type: str
    uri: str
    content_hash: str
    media_type: str


class ReportManifest(FrozenModel):
    packet_type: Literal["l9.report-manifest"] = "l9.report-manifest"
    packet_version: str = "1.0.0"
    source_packet_id: str
    source_semantic_hash: str
    renderer: Producer
    report_profile_hash: str
    cache_key: str
    reports: tuple[ReportRef, ...]
    created_at: datetime = Field(default_factory=utc_now)
    semantic_hash: str


def report_manifest_semantic_view(manifest: ReportManifest) -> dict[str, object]:
    return {
        "packet_type": manifest.packet_type,
        "packet_version": manifest.packet_version,
        "source_packet_id": manifest.source_packet_id,
        "source_semantic_hash": manifest.source_semantic_hash,
        "renderer": manifest.renderer,
        "report_profile_hash": manifest.report_profile_hash,
        "cache_key": manifest.cache_key,
        "reports": manifest.reports,
    }


def finalize_report_manifest(candidate: ReportManifest) -> ReportManifest:
    digest = semantic_hash(report_manifest_semantic_view(candidate))
    return candidate.model_copy(update={"semantic_hash": digest})
