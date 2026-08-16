"""Declared cardinality of topology facts, and what a conflict actually means.

Multiplicity is not contradiction. A repository written in Python and Shell holds
two true values of one set-valued fact; it does not hold two competing answers to
one question. Treating ``len(values) > 1`` as a conflict manufactures unresolved
contradictions out of ordinary repositories, and — because publication holds a
candidate whose source field is in conflict — silently withholds facts that were
never in doubt.

Three cardinalities are declared:

``single``
    At most one value is true at a time. Distinct incompatible values are a real
    conflict and stay one.

``set``
    Several values are simultaneously true. Distinct supported values aggregate
    deterministically; count alone never produces a conflict.

``unknown``
    The compiler has no declared rule for this fact. Nothing is aggregated and
    nothing is called a contradiction: every value and its evidence is preserved
    and an explicit unknown is emitted instead.

These rules are compiler policy, so they are versioned and hashed. The hash is
bound into ``TopologyPacket.policy_hashes``, which participates in topology
semantic identity: changing reconciliation meaning cannot silently reuse the
identity of a packet compiled under the old meaning.
"""

from __future__ import annotations

from typing import Literal

from l9_constellation_topology.run.evidence import semantic_hash

Cardinality = Literal["single", "set", "unknown"]

RECONCILIATION_POLICY_ID = "l9-topology-reconciliation"

#: 2.0.0 introduced declared cardinality. 1.x treated every repeated value as a
#: conflict regardless of the fact's arity.
RECONCILIATION_POLICY_VERSION = "2.0.0"

#: Facts that admit at most one true value. Divergence here is a real conflict.
SINGLE_VALUED_FIELDS: frozenset[str] = frozenset(
    {
        "artifact_type",
        "body_hash",
        "content_hash",
        "default_branch",
        "description",
        "direction",
        "edge_type",
        "family",
        "license",
        "name",
        "packet_ref",
        "primary_role",
        "repository_id",
        "source",
        "source_path",
        "source_revision",
        "target_id",
        "version",
    }
)

#: Facts that admit several simultaneously true values. These aggregate.
SET_VALUED_FIELDS: frozenset[str] = frozenset(
    {
        "adr_refs",
        "artifact_ids",
        "capabilities",
        "capability_ids",
        "declared_actions",
        "dependencies",
        "downstream_repository_ids",
        "entrypoints",
        "evidence_refs",
        "exposed_by",
        "governance_refs",
        "governed_by",
        "implemented_by",
        "languages",
        "owner_ids",
        "package_managers",
        "secondary_roles",
        "tags",
        "unresolved_dependencies",
        "upstream_repository_ids",
        "validated_by",
        "workflows",
    }
)

_OVERLAP = SINGLE_VALUED_FIELDS & SET_VALUED_FIELDS
if _OVERLAP:  # pragma: no cover - guarded at import; a build error, not a runtime path
    raise ValueError(f"fields declared with two cardinalities: {sorted(_OVERLAP)}")

#: Emitted as the reason of an unknown raised for an undeclared multi-valued fact.
UNDECLARED_CARDINALITY_REASON = (
    "field has no declared cardinality in the reconciliation policy, so divergent "
    "observed values were neither aggregated nor treated as a contradiction"
)


def cardinality_of(field: str | None) -> Cardinality:
    """Return the declared cardinality of a fact.

    An absent field name carries no per-field claim at all, so it is ``unknown``
    rather than a single-valued assertion about the subject as a whole.
    """
    if field is None:
        return "unknown"
    if field in SET_VALUED_FIELDS:
        return "set"
    if field in SINGLE_VALUED_FIELDS:
        return "single"
    return "unknown"


def is_conflicting(field: str | None, values: tuple[str, ...]) -> bool:
    """Return whether divergent observed values are a genuine contradiction.

    Only a single-valued fact can contradict itself. A set-valued fact with many
    values is aggregated, and an undeclared fact is reported as unknown by the
    caller rather than judged either way here.
    """
    return len(values) > 1 and cardinality_of(field) == "single"


def reconciliation_policy_view() -> dict[str, object]:
    """Return the exact reconciliation semantics this compiler build applies."""
    return {
        "id": RECONCILIATION_POLICY_ID,
        "version": RECONCILIATION_POLICY_VERSION,
        "single_valued_fields": sorted(SINGLE_VALUED_FIELDS),
        "set_valued_fields": sorted(SET_VALUED_FIELDS),
        "undeclared_field_behavior": "preserve-evidence-and-emit-unknown",
    }


def reconciliation_policy_hash() -> str:
    """Return the hash bound into ``TopologyPacket.policy_hashes``."""
    return semantic_hash(reconciliation_policy_view())
