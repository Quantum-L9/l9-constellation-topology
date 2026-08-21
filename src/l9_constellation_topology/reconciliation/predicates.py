"""Declared reconciliation semantics for repository-model assertion predicates.

An assertion predicate is a string chosen by the producer's interpretation
profile. Treating every such string alike is the mistake this registry exists to
prevent: ``package.dependency`` naming fourteen packages is fourteen true facts,
while ``package.name`` naming two packages is one question with two competing
answers. Without a declared arity the first would be reported as a contradiction
and the second would be silently aggregated, and both readings would be wrong.

Four classifications are declared:

``set``
    Several objects are simultaneously true of one subject. Distinct objects
    aggregate; count alone is never a contradiction.

``single``
    At most one object is true of one subject at a time. Distinct objects are a
    real conflict and stay one: every claim is preserved, a conflict is emitted,
    and no winner is chosen without an explicit authority rule.

``auxiliary``
    Recognized, multi-valued, and deliberately carrying no stronger topology
    meaning. It reconciles exactly like ``set`` and never projects. These
    predicates state that a claim *exists* somewhere (``contract`` files declare
    invariants; an authority reference did not resolve) rather than stating the
    claim itself.

``unsupported``
    The registry has no rule for this predicate. Nothing is aggregated, nothing
    is called a contradiction, and nothing is discarded: every claim and its
    evidence survives, a diagnostic is emitted, and no projection to stronger
    topology semantics is attempted.

The registry is compiler policy, so it is versioned and hashed. The hash is
bound into ``TopologyPacket.policy_hashes``, which participates in topology
semantic identity: changing what a predicate means cannot silently reuse the
identity of a packet compiled under the old meaning.
"""

from __future__ import annotations

from typing import Literal

from l9_constellation_topology.run.evidence import semantic_hash

from .cardinality import Cardinality

#: How this registry classifies a predicate, before it is reduced to a cardinality.
PredicateSupport = Literal["set", "single", "auxiliary", "unsupported"]

PREDICATE_POLICY_ID = "l9-topology-assertion-predicates"

#: 1.0.0 is the first registry. It covers the Meta interpretation profile that
#: repository-model 1.1.0 producers currently emit.
PREDICATE_POLICY_VERSION = "1.0.0"

#: Predicates whose objects are simultaneously true. These aggregate.
SET_VALUED_PREDICATES: frozenset[str] = frozenset(
    {
        "authority.canonical_contract",
        "contract.invariant",
        "http.handler_body_marker",
        "http.route",
        "http.route_handler",
        "package.dependency",
        "repository.disclaimed_role",
        "repository.self_described_role",
        "service.action",
    }
)

#: Predicates admitting at most one true object. Divergence here is a conflict.
SINGLE_VALUED_PREDICATES: frozenset[str] = frozenset(
    {
        "authority.canonical_contract_count",
        "package.build_backend",
        "package.framework",
        "package.name",
        "package.packaging_system",
        "package.python_constraint",
        "package.server",
        "package.version",
        "repository.replaced_by",
        "repository.status",
        "service.name",
        "service.version",
    }
)

#: Recognized multi-valued predicates that deliberately project to nothing.
AUXILIARY_PREDICATES: frozenset[str] = frozenset(
    {
        "authority.unresolved_reference",
        "contract.declares_invariants",
    }
)

_CLASSIFIED = (SET_VALUED_PREDICATES, SINGLE_VALUED_PREDICATES, AUXILIARY_PREDICATES)
for _first_index, _first in enumerate(_CLASSIFIED):
    for _second in _CLASSIFIED[_first_index + 1 :]:
        _overlap = _first & _second
        if _overlap:  # pragma: no cover - guarded at import; a build error
            raise ValueError(f"predicates declared with two classifications: {sorted(_overlap)}")

#: Every predicate this registry has a declared rule for.
SUPPORTED_PREDICATES: frozenset[str] = (
    SET_VALUED_PREDICATES | SINGLE_VALUED_PREDICATES | AUXILIARY_PREDICATES
)

#: Reason recorded on the unknown raised for a predicate the registry does not declare.
UNSUPPORTED_PREDICATE_REASON = (
    "assertion predicate has no declared rule in the predicate registry, so its claims "
    "were preserved with their evidence but neither aggregated, treated as a "
    "contradiction, nor projected into stronger topology semantics"
)

#: Diagnostic code emitted once per unsupported predicate encountered.
UNSUPPORTED_PREDICATE_CODE = "assertion-predicate-unsupported"


def predicate_support(predicate: str) -> PredicateSupport:
    """Return how this registry classifies ``predicate``."""
    if predicate in SET_VALUED_PREDICATES:
        return "set"
    if predicate in SINGLE_VALUED_PREDICATES:
        return "single"
    if predicate in AUXILIARY_PREDICATES:
        return "auxiliary"
    return "unsupported"


def predicate_cardinality(predicate: str) -> Cardinality:
    """Return the reconciliation arity of ``predicate``.

    Auxiliary predicates reconcile as sets: they are recognized and genuinely
    multi-valued, and only their *projection* is withheld. An unsupported
    predicate is ``unknown``, which aggregates nothing and contradicts nothing.
    """
    support = predicate_support(predicate)
    if support in {"set", "auxiliary"}:
        return "set"
    if support == "single":
        return "single"
    return "unknown"


def is_projectable(predicate: str) -> bool:
    """Return whether a predicate may carry meaning beyond the claim itself.

    Auxiliary and unsupported predicates never do. A ``True`` here means only
    that projection is *permitted*; the projection table decides whether one
    exists.
    """
    return predicate_support(predicate) in {"set", "single"}


def predicate_policy_view() -> dict[str, object]:
    """Return the exact predicate semantics this compiler build applies."""
    return {
        "id": PREDICATE_POLICY_ID,
        "version": PREDICATE_POLICY_VERSION,
        "set_valued_predicates": sorted(SET_VALUED_PREDICATES),
        "single_valued_predicates": sorted(SINGLE_VALUED_PREDICATES),
        "auxiliary_predicates": sorted(AUXILIARY_PREDICATES),
        "unsupported_predicate_behavior": "preserve-claim-evidence-and-emit-diagnostic",
    }


def predicate_policy_hash() -> str:
    """Return the hash bound into ``TopologyPacket.policy_hashes``."""
    return semantic_hash(predicate_policy_view())
