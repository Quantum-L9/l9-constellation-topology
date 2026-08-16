"""Versioned field cardinality contract for evidence reconciliation.

Multiple distinct values observed for a field are not automatically a
contradiction. A field whose declared semantics are set-valued is an
aggregation: two scanners reporting ``python`` and ``typescript`` for
``languages`` agree that both are present, they do not disagree. Only a field
declared single-valued can hold a genuine conflict, because only there can two
values be mutually exclusive claims about the same fact.

A field whose cardinality this contract does not declare stays ``UNKNOWN``.
Unknown cardinality is reported as an unknown, never resolved by guessing and
never promoted into a manufactured conflict.

The contract is versioned and hashed because it changes topology truth: the
same evidence reconciled under a different cardinality declaration can produce
a different conflict set. Its version therefore participates in the compiler's
active contract versions.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

FIELD_CARDINALITY_CONTRACT_ID = "l9.field-cardinality"
FIELD_CARDINALITY_CONTRACT_VERSION = "1.0.0"


class Cardinality(StrEnum):
    """How many values a field may legitimately hold at once."""

    #: Exactly one value is correct; competing values are a real conflict.
    SINGLE = "single"
    #: Many values coexist; competing values aggregate and never conflict.
    SET = "set"
    #: Not declared by this contract; preserved as an unknown.
    UNKNOWN = "unknown"


#: Single-valued fields, grounded in the frozen domain records. Each names one
#: fact about a subject, so two distinct observed values are incompatible.
_SINGLE_VALUED: frozenset[str] = frozenset(
    {
        # RepositoryRecord
        "repository_id",
        "name",
        "source_revision",
        "packet_ref",
        "primary_role",
        # CapabilityRecord
        "capability_id",
        "description",
        # ArtifactRecord
        "artifact_id",
        "source_path",
        "artifact_type",
        "family",
        "content_hash",
        "body_hash",
    }
)

#: Set-valued fields, grounded in the tuple-typed members of the frozen domain
#: records. Every one of these is an aggregation across sources.
_SET_VALUED: frozenset[str] = frozenset(
    {
        # RepositoryRecord
        "secondary_roles",
        "languages",
        "package_managers",
        "entrypoints",
        "workflows",
        "adr_refs",
        "governance_refs",
        "capability_ids",
        "artifact_ids",
        "upstream_repository_ids",
        "downstream_repository_ids",
        "unresolved_dependencies",
        "owner_ids",
        "evidence_refs",
        # CapabilityRecord
        "implemented_by",
        "exposed_by",
        "validated_by",
        "governed_by",
        # ArtifactRecord
        "capabilities",
        "dependencies",
    }
)

_DECLARED: Mapping[str, Cardinality] = MappingProxyType(
    {
        **{field: Cardinality.SINGLE for field in _SINGLE_VALUED},
        **{field: Cardinality.SET for field in _SET_VALUED},
    }
)


def cardinality_of(field: str | None) -> Cardinality:
    """Return the declared cardinality of ``field``.

    An undeclared field is ``UNKNOWN``; it is never assumed to be singular.
    """
    if field is None:
        return Cardinality.UNKNOWN
    return _DECLARED.get(field, Cardinality.UNKNOWN)


def declared_fields() -> Mapping[str, Cardinality]:
    """Return the full declaration, for contract hashing and introspection."""
    return _DECLARED


def contract_identity() -> dict[str, object]:
    """Return the canonical identity of this contract."""
    return {
        "contract_id": FIELD_CARDINALITY_CONTRACT_ID,
        "contract_version": FIELD_CARDINALITY_CONTRACT_VERSION,
        "fields": {field: str(value) for field, value in sorted(_DECLARED.items())},
    }
