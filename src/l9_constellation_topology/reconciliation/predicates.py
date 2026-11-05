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

#: 1.1.0 adds the document work vocabulary: the predicates a decoder reads out of
#: plans, roadmaps, trackers, and WIP documents. 1.0.0 covered only the Meta
#: interpretation profile for source repositories.
#:
#: The work predicates are declared here, in the same registry, on purpose. A
#: separate conflict model for Word documents would mean two answers to the
#: question "does this repository have one status or several", decided by which
#: file format happened to state it — and a `.docx` saying ``Complete`` beside a
#: `.md` saying ``WIP`` is exactly the contradiction a reader needs surfaced, not
#: one routed into a different subsystem.
#:
#: 1.2.0 registers the native ``L9_META`` header predicates whose meaning the
#: Semantic Foundation now governs: ``l9.artifact-header-model/global@1``
#: (Quantum-L9/.github v3.27.0, ADR-024), transcribed by the producer's governed
#: mapping (l9-meta-injector ADR-084). Each is a declaration the carrying file
#: makes about itself. Scalars reconcile as ``single``, so two different
#: declarations about one file are a conflict; lists reconcile as ``set``; the
#: carrier and schema claims are ``auxiliary``. None of them may project: the
#: ledger's projection boundary admits no canonical relation from a header
#: (ADR-0033).
PREDICATE_POLICY_VERSION = "1.2.0"

#: The ledger every header predicate below takes its meaning from.
HEADER_SEMANTICS_LEDGER = "l9.artifact-header-model/global@1"

#: Predicate namespaces of the declared schemas the ledger recognizes (``l9_schema`` 1 and 2).
HEADER_SCHEMA_NAMESPACES: tuple[str, ...] = ("l9v1", "l9v2")

#: ``(field, category, value_kind)`` exactly as the ledger defines them, in its order.
#: List value kinds are set-valued; every other kind declares one value.
HEADER_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("id", "identity", "label"),
    ("origin", "identity", "label"),
    ("engine", "identity", "label"),
    ("namespace", "identity", "label"),
    ("component", "identity", "label"),
    ("canonical_path", "identity", "path"),
    ("version", "identity", "label"),
    ("title", "identity", "text"),
    ("source_repo", "identity", "text"),
    ("source_file", "identity", "text"),
    ("source_adr", "identity", "label"),
    ("layer", "classification", "label_list"),
    ("tags", "classification", "label_list"),
    ("artifact_type", "classification", "label"),
    ("status", "classification", "label"),
    ("ring", "classification", "label"),
    ("category", "classification", "label"),
    ("owner", "governance", "label"),
    ("ssot_for", "governance", "label_list"),
    ("canonical", "governance", "label"),
    ("canonical_source", "governance", "url"),
    ("single_source_rule", "governance", "text"),
    ("retrieval", "retrieval", "label"),
    ("load_when", "retrieval", "label_list"),
    ("load_condition", "retrieval", "text"),
    ("references", "retrieval", "reference_list"),
    ("requires", "retrieval", "reference_list"),
    ("amplifies", "retrieval", "reference_list"),
    ("retrieval_keys", "retrieval", "text"),
    ("token_estimate", "retrieval", "count"),
)

_SET_VALUE_KINDS = frozenset({"label_list", "reference_list"})

#: Structural header claims: that a header was found in a carrier, and which
#: schema it declared. Recognized, possibly several per file, never projected.
HEADER_STRUCTURE_PREDICATES: frozenset[str] = frozenset(
    {"meta.declaration.carrier", "meta.declaration.schema"}
)


def _header_declarations() -> dict[str, dict[str, str]]:
    declarations: dict[str, dict[str, str]] = {}
    for namespace in HEADER_SCHEMA_NAMESPACES:
        for field, category, value_kind in HEADER_FIELDS:
            set_valued = value_kind in _SET_VALUE_KINDS
            declarations[f"meta.{namespace}.{category}.{field}"] = {
                "definition": f"{HEADER_SEMANTICS_LEDGER}#fields.{field}",
                "subject_scope": "artifact",
                "object_type": value_kind,
                "cardinality": "set" if set_valued else "single",
                "support": "set" if set_valued else "single",
                "authority": "declared-source-claim; grants no ownership, identity or canonical status",
                "projection": "none",
                "conflict": "aggregate-distinct" if set_valued else "preserve-all-and-conflict",
                "unknown": "unresolved-or-out-of-vocabulary-fields-arrive-as-other-predicates",
            }
    return declarations


#: Every governed header predicate with the nine properties its declaration
#: must carry: definition, subject scope, object type, cardinality, support
#: class, authority, projection eligibility, conflict and unknown behavior.
HEADER_DECLARATION_PREDICATES: dict[str, dict[str, str]] = _header_declarations()

#: Predicates that are recognized for reconciliation but may never project,
#: whatever their cardinality. ``is_projectable`` refuses them before the
#: projection table is ever consulted.
DECLARATION_ONLY_PREDICATES: frozenset[str] = (
    frozenset(HEADER_DECLARATION_PREDICATES) | HEADER_STRUCTURE_PREDICATES
)

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
        # Document work vocabulary. A document has many headings, a plan names
        # many open tasks, and a roadmap names many milestones: several objects
        # of each are simultaneously true, so count alone is never a conflict.
        "document.heading",
        "work.task.open",
        "work.task.completed",
        "work.milestone",
        "work.depends_on",
        "work.blocked_by",
        "work.references",
        "work.supersedes",
        "work.superseded_by",
    }
) | frozenset(
    # Governed list-valued header fields (1.2.0): several declared values at once.
    predicate
    for predicate, declaration in HEADER_DECLARATION_PREDICATES.items()
    if declaration["cardinality"] == "set"
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
        # A document has one title, is in one state, and is one kind of thing at
        # a time. Two answers to any of these is a real contradiction: a plan
        # declaring both `WIP` and `Complete` is the finding, and aggregating the
        # two into a set would report it as two facts and lose it.
        "document.title",
        "work.status",
        "work.kind",
    }
) | frozenset(
    # Governed scalar header fields (1.2.0): one declared value per file, so a
    # second, different declaration is a conflict and no winner is chosen.
    predicate
    for predicate, declaration in HEADER_DECLARATION_PREDICATES.items()
    if declaration["cardinality"] == "single"
)

#: Recognized multi-valued predicates that deliberately project to nothing.
AUXILIARY_PREDICATES: frozenset[str] = (
    frozenset(
        {
            "authority.unresolved_reference",
            "contract.declares_invariants",
        }
    )
    | HEADER_STRUCTURE_PREDICATES
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

    Auxiliary and unsupported predicates never do, and neither does a
    declaration-only predicate (a governed header field), whatever its
    cardinality. A ``True`` here means only that projection is *permitted*; the
    projection table decides whether one exists.
    """
    if predicate in DECLARATION_ONLY_PREDICATES:
        return False
    return predicate_support(predicate) in {"set", "single"}


def predicate_policy_view() -> dict[str, object]:
    """Return the exact predicate semantics this compiler build applies."""
    return {
        "id": PREDICATE_POLICY_ID,
        "version": PREDICATE_POLICY_VERSION,
        "set_valued_predicates": sorted(SET_VALUED_PREDICATES),
        "single_valued_predicates": sorted(SINGLE_VALUED_PREDICATES),
        "auxiliary_predicates": sorted(AUXILIARY_PREDICATES),
        "declaration_only_predicates": sorted(DECLARATION_ONLY_PREDICATES),
        "header_semantics": {
            "ledger": HEADER_SEMANTICS_LEDGER,
            "declarations": {
                predicate: HEADER_DECLARATION_PREDICATES[predicate]
                for predicate in sorted(HEADER_DECLARATION_PREDICATES)
            },
        },
        "unsupported_predicate_behavior": "preserve-claim-evidence-and-emit-diagnostic",
    }


def predicate_policy_hash() -> str:
    """Return the hash bound into ``TopologyPacket.policy_hashes``."""
    return semantic_hash(predicate_policy_view())
