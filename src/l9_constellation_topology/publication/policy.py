"""Versioned publication policy resolution.

The publication policy is resolved and hashed independently of
``ResolvedConfiguration``. Keeping it out of ``profile_hash`` is what preserves
the canonicality invariant: adding or changing publication policy must never
change the semantic identity of a Topology Packet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.run.evidence import semantic_hash

from .contracts import (
    ConfidenceMethodName,
    EvidenceKindName,
    MemoryClassName,
)

POLICY_RELATIVE_PATH = Path(".l9") / "publication-policy.yaml"

_REQUIRED_KEYS = (
    "id",
    "version",
    "namespace_root",
    "eligible_entity_kinds",
    "eligible_edge_types",
    "entity_memory_class",
    "relationship_memory_class",
    "confidence_score_by_level",
    "confidence_conflict_ceiling",
    "confidence_method_by_derivation",
    "evidence_kind_by_class",
)


class PublicationPolicyError(ValueError):
    """Raised when the publication policy is missing, malformed, or incomplete."""


class PublicationPolicy(FrozenModel):
    """Resolved, hashable publication policy."""

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    namespace_root: str = Field(min_length=1, max_length=200)
    eligible_entity_kinds: tuple[str, ...]
    eligible_edge_types: tuple[str, ...]
    entity_memory_class: MemoryClassName
    relationship_memory_class: MemoryClassName
    claim_memory_class: MemoryClassName = "semantic"
    confidence_score_by_level: dict[str, float]
    confidence_conflict_ceiling: dict[str, float]
    confidence_method_by_derivation: dict[str, ConfidenceMethodName]
    evidence_kind_by_class: dict[str, EvidenceKindName]
    source_trust_by_authority: dict[str, float] = Field(
        default_factory=lambda: {
            "source": 1.0,
            "validated-machine": 0.9,
            "derived": 0.7,
            "candidate": 0.5,
            "unknown": 0.3,
        }
    )
    require_validated_topology: bool = True
    require_resolved_lineage: bool = True
    hold_on_material_conflict: bool = True
    hold_on_material_unknown: bool = True
    hold_on_missing_required_evidence: bool = True
    #: Hold a claim whose predicate the registry does not declare. Such a
    #: claim is well formed and fully evidenced; what is unknown is what it
    #: *means*, which is not something publication should decide silently.
    hold_on_unsupported_predicate: bool = True
    maximum_evidence_refs_per_candidate: int = Field(default=32, ge=1)

    @property
    def identity(self) -> str:
        return f"{self.id}/{self.version}"

    @property
    def confidence_policy_version(self) -> str:
        """Value recorded as ``Confidence.policy_version`` downstream."""
        return f"l9-topology-publication/{self.version}"

    def raw(self) -> dict[str, Any]:
        """Return the policy as plain data for embedding in a plan."""
        return self.model_dump(mode="json")

    def policy_hash(self) -> str:
        return semantic_hash(self.raw())


def load_publication_policy(repository_root: Path) -> PublicationPolicy:
    """Load and validate the publication policy for a repository checkout."""
    path = repository_root.resolve() / POLICY_RELATIVE_PATH
    if not path.is_file():
        raise PublicationPolicyError(f"publication policy is missing: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PublicationPolicyError(f"publication policy is unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise PublicationPolicyError("publication policy must be a mapping")
    missing = [key for key in _REQUIRED_KEYS if key not in data]
    if missing:
        raise PublicationPolicyError(
            f"publication policy is missing required keys: {', '.join(sorted(missing))}"
        )
    try:
        return PublicationPolicy.model_validate(data)
    except ValueError as exc:
        raise PublicationPolicyError(f"publication policy is invalid: {exc}") from exc
