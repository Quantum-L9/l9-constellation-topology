"""Versioned publication policy resolution.

The publication policy is resolved and hashed independently of
``ResolvedConfiguration``. Keeping it out of ``profile_hash`` is what preserves
the canonicality invariant: adding or changing publication policy must never
change the semantic identity of a Topology Packet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, model_validator

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.reconciliation.predicates import (
    DECLARATION_ONLY_PREDICATES,
    SUPPORTED_PREDICATES,
)
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


#: ``legacy`` publishes every selected edge type as before ADR-0036. ``strict``
#: publishes an edge only when :func:`qualify_relation` qualifies it.
RelationQualificationMode = Literal["legacy", "strict"]

#: ``all`` lowers every claim when ``semantic_claim`` is selected, as before
#: ADR-0036. ``selective`` lowers only the predicates the policy names.
ClaimPublicationMode = Literal["all", "selective"]

#: The values a policy file written before ADR-0036 implicitly has. They are
#: omitted from the hashed policy view while they hold, so a pre-ADR-0036 policy
#: keeps its exact identity and produces byte-identical plans.
_PRE_QUALIFICATION_DEFAULTS: dict[str, Any] = {
    "relation_qualification": "legacy",
    "claim_publication": "all",
    "eligible_claim_predicates": [],
    "declaration_only_claim_predicates": [],
}


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
    #: Whether a selected edge must also be qualified by its own evidence (ADR-0036).
    relation_qualification: RelationQualificationMode = "legacy"
    #: Whether claim publication is predicate-selective (ADR-0036).
    claim_publication: ClaimPublicationMode = "all"
    #: Registry predicates whose claims ``selective`` publication lowers. A
    #: declaration-only predicate may not appear here: see the next field.
    eligible_claim_predicates: tuple[str, ...] = ()
    #: Declaration-only predicates (governed or managed header metadata, field
    #: observations) explicitly opted in to durable publication. Empty means none
    #: is published: header metadata never reaches durable memory by default.
    declaration_only_claim_predicates: tuple[str, ...] = ()

    @model_validator(mode="after")
    def claim_selection_is_explicit(self) -> PublicationPolicy:
        selected = (*self.eligible_claim_predicates, *self.declaration_only_claim_predicates)
        if self.claim_publication == "all" and selected:
            raise ValueError(
                "claim predicate lists require claim_publication: selective; under 'all' "
                "they would be silently ignored"
            )
        duplicates = sorted({item for item in selected if selected.count(item) > 1})
        if duplicates:
            raise ValueError(f"claim predicates listed more than once: {duplicates}")
        unknown = sorted(set(selected) - SUPPORTED_PREDICATES)
        if unknown:
            raise ValueError(f"claim predicates the predicate registry does not declare: {unknown}")
        declaration_only = sorted(set(self.eligible_claim_predicates) & DECLARATION_ONLY_PREDICATES)
        if declaration_only:
            raise ValueError(
                "declaration-only predicates must be opted in through "
                f"declaration_only_claim_predicates, not eligible_claim_predicates: {declaration_only}"
            )
        not_declaration_only = sorted(
            set(self.declaration_only_claim_predicates) - DECLARATION_ONLY_PREDICATES
        )
        if not_declaration_only:
            raise ValueError(
                "declaration_only_claim_predicates names predicates that are not "
                f"declaration-only: {not_declaration_only}"
            )
        return self

    @property
    def identity(self) -> str:
        return f"{self.id}/{self.version}"

    @property
    def confidence_policy_version(self) -> str:
        """Value recorded as ``Confidence.policy_version`` downstream."""
        return f"l9-topology-publication/{self.version}"

    def claim_predicate_selection(self, predicate: str) -> bool | None:
        """Return whether a claim under ``predicate`` is selected for lowering.

        ``None`` means selection has no rule for the predicate: under
        ``selective`` an unsupported predicate is lowered and held exactly as
        before, so the registry gap stays visible rather than becoming a skip.
        """
        if self.claim_publication == "all":
            return True
        if predicate not in SUPPORTED_PREDICATES:
            return None
        if predicate in DECLARATION_ONLY_PREDICATES:
            return predicate in self.declaration_only_claim_predicates
        return predicate in self.eligible_claim_predicates

    def raw(self) -> dict[str, Any]:
        """Return the policy as plain data for embedding in a plan.

        When every qualification field still holds its pre-ADR-0036 value they are
        all omitted, so a policy that uses none of them keeps the identity it had
        before they existed. A policy that uses any of them states all of them.
        """
        data = self.model_dump(mode="json")
        if all(data.get(key) == value for key, value in _PRE_QUALIFICATION_DEFAULTS.items()):
            for key in _PRE_QUALIFICATION_DEFAULTS:
                del data[key]
        return data

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
