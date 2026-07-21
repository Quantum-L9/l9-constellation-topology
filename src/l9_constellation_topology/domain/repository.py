"""Canonical repository record."""

from __future__ import annotations

from pydantic import Field

from .base import FrozenModel
from .confidence import ConfidenceAssessment


class RepositoryRecord(FrozenModel):
    repository_id: str
    name: str
    source_revision: str
    packet_ref: str
    primary_role: str = "unknown"
    secondary_roles: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    package_managers: tuple[str, ...] = ()
    entrypoints: tuple[str, ...] = ()
    workflows: tuple[str, ...] = ()
    adr_refs: tuple[str, ...] = ()
    governance_refs: tuple[str, ...] = ()
    capability_ids: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    upstream_repository_ids: tuple[str, ...] = ()
    downstream_repository_ids: tuple[str, ...] = ()
    unresolved_dependencies: tuple[str, ...] = ()
    owner_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    confidence: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment.unknown)
