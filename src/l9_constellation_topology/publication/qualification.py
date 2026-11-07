"""Evidence-qualified relation publication (ADR-0036).

Publication selection answers "does the policy publish this *kind* of relation?".
Qualification answers a prior question it cannot: "does the evidence behind this
*particular* edge prove the relation it states?". A canonical edge can be
structurally valid -- both endpoints exist, the evidence resolves -- and still be
supported only by the existence or classification of an artifact. Lowered into
durable memory, such an edge reads as an established relationship.

:func:`qualify_relation` is the one pure, reusable decision. It judges an edge by
its semantic family (edge type), the producer that emitted it, the evidence that
producer recorded, and its endpoint identities. It reuses, rather than restates,
two existing rules without turning either into a universal authority gate:

* **D5a** (ADR-0035): an edge projected from a claim qualifies only while that
  claim passes :func:`projection_ineligibility`. A conflicted claim never
  supports a published relation.
* **D5b** (ADR-0035): an edge's target is judged by the rule of the producer that
  emitted it (:func:`dependency_target_resolution`'s constants). An absent
  resolution property is never read as resolved.

It fails closed. An edge type with no declared rule, an edge whose producer
cannot be identified from its own evidence, and an edge whose producer is known
but whose mandatory relation-specific evidence is absent are all unqualified, each
under a reason of its own. A qualified edge carries the basis that qualified it.

The producer is identified from what the edge and topology state already carry.
Nothing here changes the canonical graph, adds a property to an edge, or moves a
Topology Packet identity.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from l9_constellation_topology.domain.artifact import ArtifactRecord
from l9_constellation_topology.domain.capability import CapabilityRecord
from l9_constellation_topology.domain.claim import SemanticClaimRecord
from l9_constellation_topology.domain.edge import EXACT_DUPLICATE_METHOD, EdgeRecord, EdgeType
from l9_constellation_topology.domain.repository import RepositoryRecord
from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.run.evidence import EvidenceRecord
from l9_constellation_topology.topology.claim_projection import projection_ineligibility
from l9_constellation_topology.topology.impact import (
    ENDPOINT_KIND_PROPERTY,
    EXTERNAL_PACKAGE_ENDPOINT,
    RESOLVED_TARGET_RESOLUTION,
    TARGET_RESOLUTION_PROPERTY,
)

#: The producer that emitted an edge, as established from the edge's own record.
RelationOrigin = Literal[
    # Work projector: an explicit document work relation (records target_resolution).
    "work-projector",
    # Claim projector: a reconciled repository-model assertion (records endpoint_kind).
    "claim-projector",
    # Exact duplicate detection: content-hash equality (records method).
    "exact-duplicate",
    # Corpus scope: corpus -> root -> repository containment.
    "corpus-scope",
    # A producer-declared relationship whose evidence names the relation itself.
    "producer-declared",
    # Graph builder: a repository's matched upstream repository dependency.
    "repository-upstream",
    # Graph builder: a repository's recorded owner.
    "repository-owner",
    # Graph builder: a capability record's own implemented_by / exposed_by.
    "capability-record",
    # Graph builder: an artifact record's own capability list.
    "artifact-capability",
    # Graph builder: repository-to-artifact inventory.
    "artifact-containment",
    # Graph builder: a relation promoted from an artifact's type classification.
    "artifact-classification",
    "unrecognized",
]

QualificationStatus = Literal["qualified", "unqualified"]

#: Every reason is namespaced ``qualification.`` so a skip recorded by
#: qualification can never be mistaken for one recorded by policy selection
#: (``policy.``). The one exception is the established work-target reason, which
#: predates this module and keeps its string so existing consumers still match it.
REASON_TYPE_UNRECOGNIZED = "qualification.relation_type_unrecognized"
REASON_ORIGIN_UNSUPPORTED = "qualification.evidence_origin_unsupported"
REASON_EVIDENCE_MISSING = "qualification.relation_evidence_missing"
REASON_CLASSIFICATION_ONLY = "qualification.artifact_classification_only"
REASON_CLAIM_NOT_PROJECTABLE = "qualification.originating_claim_not_projectable"
REASON_ENDPOINT_UNRESOLVED = "qualification.endpoint_unresolved"
REASON_ENDPOINT_MISMATCH = "qualification.endpoint_kind_mismatch"
#: Unchanged from the pre-qualification plan (``SKIP_UNRESOLVED_WORK_TARGET``).
REASON_WORK_TARGET_UNRESOLVED = "relation.work_target_not_exactly_resolved"

#: Every unqualified reason this module can return.
UNQUALIFIED_REASONS: frozenset[str] = frozenset(
    {
        REASON_TYPE_UNRECOGNIZED,
        REASON_ORIGIN_UNSUPPORTED,
        REASON_EVIDENCE_MISSING,
        REASON_CLASSIFICATION_ONLY,
        REASON_CLAIM_NOT_PROJECTABLE,
        REASON_ENDPOINT_UNRESOLVED,
        REASON_ENDPOINT_MISMATCH,
        REASON_WORK_TARGET_UNRESOLVED,
    }
)

#: Evidence classes that can *directly* support a relation. Derived, assisted and
#: projected evidence restate a conclusion rather than observe or declare one.
DIRECT_EVIDENCE_CLASSES: frozenset[str] = frozenset(
    {"observed", "declared", "validated", "committed"}
)

#: The producer origins each semantic family admits. An edge type absent here has
#: no declared rule and is unqualified (fail closed): extending the taxonomy
#: requires deciding what evidence proves the new relation.
ADMISSIBLE_ORIGINS: dict[EdgeType, frozenset[RelationOrigin]] = {
    EdgeType.contains: frozenset({"artifact-containment", "corpus-scope", "producer-declared"}),
    EdgeType.depends_on: frozenset(
        {"work-projector", "claim-projector", "repository-upstream", "producer-declared"}
    ),
    EdgeType.blocked_by: frozenset({"work-projector", "producer-declared"}),
    EdgeType.references: frozenset({"work-projector", "producer-declared"}),
    EdgeType.supersedes: frozenset({"work-projector", "claim-projector", "producer-declared"}),
    EdgeType.governed_by: frozenset({"claim-projector", "producer-declared"}),
    EdgeType.documented_by: frozenset({"producer-declared"}),
    EdgeType.validated_by: frozenset({"producer-declared"}),
    EdgeType.implements: frozenset(
        {"capability-record", "artifact-capability", "producer-declared"}
    ),
    EdgeType.exposes: frozenset({"capability-record", "producer-declared"}),
    EdgeType.owned_by: frozenset({"repository-owner", "producer-declared"}),
    EdgeType.duplicate_of: frozenset({"exact-duplicate"}),
    EdgeType.derived_from: frozenset({"producer-declared"}),
    EdgeType.produces: frozenset({"producer-declared"}),
    EdgeType.consumes: frozenset({"producer-declared"}),
    EdgeType.routes_to: frozenset({"producer-declared"}),
    EdgeType.publishes_to: frozenset({"producer-declared"}),
    EdgeType.member_of: frozenset({"producer-declared"}),
}

#: The endpoint kind the claim projector records for each family it emits. A
#: claim-projected edge whose recorded endpoint kind disagrees with its family
#: was not produced by any declared claim projection.
CLAIM_PROJECTOR_ENDPOINT_BY_TYPE: dict[EdgeType, str] = {
    EdgeType.depends_on: EXTERNAL_PACKAGE_ENDPOINT,
    EdgeType.governed_by: "declared-contract-reference",
    EdgeType.supersedes: "declared-repository-reference",
}

#: Relations an artifact's type classification used to promote (graph builder,
#: ADR-0036 Phase B). Recognized so such an edge is named for what it is rather
#: than reported as an unknown producer.
CLASSIFICATION_PROMOTED_TYPES: frozenset[EdgeType] = frozenset(
    {EdgeType.governed_by, EdgeType.documented_by, EdgeType.validated_by}
)

PROJECTED_FROM_CLAIM_PROPERTY = "projected_from_claim_id"


@dataclass(frozen=True)
class RelationQualification:
    """Why one edge does, or does not, qualify for publication."""

    edge_id: str
    edge_type: str
    origin: RelationOrigin
    status: QualificationStatus
    #: For a qualified edge, the evidence basis that qualified it. For an
    #: unqualified edge, the namespaced reason it did not.
    reason: str

    @property
    def qualified(self) -> bool:
        return self.status == "qualified"

    def as_metadata(self) -> dict[str, str]:
        return {"origin": self.origin, "status": self.status, "basis": self.reason}


@dataclass(frozen=True)
class QualificationIndex:
    """Lookups qualification needs over one topology state. Built once per plan."""

    evidence_by_id: dict[str, EvidenceRecord]
    claims_by_id: dict[str, SemanticClaimRecord]
    repositories: dict[str, RepositoryRecord]
    artifacts: dict[str, ArtifactRecord]
    capabilities: dict[str, CapabilityRecord]
    corpus_scope_ids: frozenset[str]

    @classmethod
    def build(cls, state: TopologyState) -> QualificationIndex:
        return cls(
            evidence_by_id={record.evidence_id: record for record in state.evidence},
            claims_by_id={record.claim_id: record for record in state.semantic_claims},
            repositories={record.repository_id: record for record in state.repository_records},
            artifacts={record.artifact_id: record for record in state.artifact_records},
            capabilities={record.capability_id: record for record in state.capability_records},
            corpus_scope_ids=frozenset(
                {record.corpus_id for record in state.corpus_records}
                | {record.root_id for record in state.root_records}
            ),
        )


def _relation_field(edge_type: EdgeType) -> str:
    """The evidence field a producer uses to declare this relation (``derived_from``)."""
    return edge_type.value.lower()


def _resolved_evidence(edge: EdgeRecord, index: QualificationIndex) -> tuple[EvidenceRecord, ...]:
    return tuple(
        index.evidence_by_id[ref]
        for ref in sorted(set(edge.evidence_refs))
        if ref in index.evidence_by_id
    )


def _relation_field_evidence(
    edge: EdgeRecord, evidence: tuple[EvidenceRecord, ...]
) -> tuple[EvidenceRecord, ...]:
    """Return the direct evidence that declares this relation about this edge.

    The record must name the relation (its ``field``) *and* be about one of the
    edge's own endpoints: a resolvable record with the right field about some
    other subject states a different fact and does not support this edge.
    """
    field = _relation_field(edge.edge_type)
    endpoints = {edge.source_id, edge.target_id}
    return tuple(
        record
        for record in evidence
        if record.field == field
        and str(record.evidence_class) in DIRECT_EVIDENCE_CLASSES
        and record.subject_id in endpoints
    )


def _recorded_origin(edge: EdgeRecord, index: QualificationIndex) -> RelationOrigin | None:
    """Return the producer an edge names by what it records, if any."""
    properties = edge.properties
    if TARGET_RESOLUTION_PROPERTY in properties:
        return "work-projector"
    if PROJECTED_FROM_CLAIM_PROPERTY in properties and ENDPOINT_KIND_PROPERTY in properties:
        return "claim-projector"
    if edge.edge_type is EdgeType.duplicate_of and "method" in properties:
        return "exact-duplicate"
    if edge.edge_type is EdgeType.contains and edge.source_id in index.corpus_scope_ids:
        return "corpus-scope"
    if _relation_field_evidence(edge, _resolved_evidence(edge, index)):
        return "producer-declared"
    return None


def _repository_origin(edge: EdgeRecord, index: QualificationIndex) -> RelationOrigin | None:
    """Return the graph-builder repository rule a property-less edge mirrors, if any."""
    repository = index.repositories.get(edge.source_id)
    if repository is None:
        return None
    artifact = index.artifacts.get(edge.target_id)
    if artifact is not None and artifact.repository_id == repository.repository_id:
        if edge.edge_type is EdgeType.contains:
            return "artifact-containment"
        if edge.edge_type in CLASSIFICATION_PROMOTED_TYPES:
            return "artifact-classification"
    if (
        edge.edge_type is EdgeType.depends_on
        and edge.target_id in repository.upstream_repository_ids
    ):
        return "repository-upstream"
    if edge.edge_type is EdgeType.owned_by and edge.target_id in repository.owner_ids:
        return "repository-owner"
    return None


def _capability_origin(edge: EdgeRecord, index: QualificationIndex) -> RelationOrigin | None:
    """Return the capability or artifact record a property-less edge mirrors, if any."""
    capability = index.capabilities.get(edge.target_id)
    if capability is None:
        return None
    if edge.edge_type is EdgeType.implements and edge.source_id in capability.implemented_by:
        return "capability-record"
    if edge.edge_type is EdgeType.exposes and edge.source_id in capability.exposed_by:
        return "capability-record"
    artifact = index.artifacts.get(edge.source_id)
    if (
        edge.edge_type is EdgeType.implements
        and artifact is not None
        and edge.target_id in artifact.capabilities
    ):
        return "artifact-capability"
    return None


def relation_origin(edge: EdgeRecord, index: QualificationIndex) -> RelationOrigin:
    """Identify the producer that emitted ``edge`` from the edge's own record.

    Producers that record a property are recognized by it. Graph-builder edges
    record none, so each of its rules is recognized by the topology record the
    edge mirrors; an edge matching no rule is ``unrecognized``.
    """
    recorded = _recorded_origin(edge, index)
    if recorded is not None:
        return recorded
    if edge.properties:
        return "unrecognized"
    return _repository_origin(edge, index) or _capability_origin(edge, index) or "unrecognized"


def _result(
    edge: EdgeRecord, origin: RelationOrigin, status: QualificationStatus, reason: str
) -> RelationQualification:
    return RelationQualification(
        edge_id=edge.edge_id,
        edge_type=edge.edge_type.value,
        origin=origin,
        status=status,
        reason=reason,
    )


def _claim_gate(edge: EdgeRecord, index: QualificationIndex) -> str | None:
    """Return why the claim an edge was projected from cannot support it (D5a)."""
    claim = index.claims_by_id.get(str(edge.properties.get(PROJECTED_FROM_CLAIM_PROPERTY)))
    if claim is None:
        return REASON_EVIDENCE_MISSING
    if projection_ineligibility(claim) is not None:
        return REASON_CLAIM_NOT_PROJECTABLE
    return None


#: One producer rule's verdict: a status and its basis or reason.
_Verdict = tuple[QualificationStatus, str]


def _qualified(basis: str) -> _Verdict:
    return ("qualified", basis)


def _unqualified(reason: str) -> _Verdict:
    return ("unqualified", reason)


def _work_projector_rule(edge: EdgeRecord, index: QualificationIndex) -> _Verdict:
    blocked = _claim_gate(edge, index)
    if blocked is not None:
        return _unqualified(blocked)
    if edge.properties.get(TARGET_RESOLUTION_PROPERTY) != RESOLVED_TARGET_RESOLUTION:
        return _unqualified(REASON_WORK_TARGET_UNRESOLVED)
    return _qualified("exact-artifact-resolution")


def _claim_projector_rule(edge: EdgeRecord, index: QualificationIndex) -> _Verdict:
    expected = CLAIM_PROJECTOR_ENDPOINT_BY_TYPE.get(edge.edge_type)
    if edge.properties.get(ENDPOINT_KIND_PROPERTY) != expected:
        return _unqualified(REASON_ENDPOINT_MISMATCH)
    blocked = _claim_gate(edge, index)
    if blocked is not None:
        return _unqualified(blocked)
    return _qualified("projection-eligible-claim")


def _exact_duplicate_rule(edge: EdgeRecord, index: QualificationIndex) -> _Verdict:
    content_hash = edge.properties.get("content_hash")
    if edge.properties.get("method") != EXACT_DUPLICATE_METHOD or not content_hash:
        return _unqualified(REASON_EVIDENCE_MISSING)
    # Byte identity is re-checked against both observed endpoints rather than
    # taken from the edge: a hash no endpoint carries is not equality.
    endpoints = (index.artifacts.get(edge.source_id), index.artifacts.get(edge.target_id))
    if any(artifact is None or artifact.content_hash != content_hash for artifact in endpoints):
        return _unqualified(REASON_EVIDENCE_MISSING)
    return _qualified("content-hash-equality")


def _repository_upstream_rule(edge: EdgeRecord, index: QualificationIndex) -> _Verdict:
    # D5b: a graph-builder dependency resolves only to an observed entity.
    if edge.target_id not in index.repositories:
        return _unqualified(REASON_ENDPOINT_UNRESOLVED)
    return _qualified("observed-repository-target")


def _always(basis: str) -> Callable[[EdgeRecord, QualificationIndex], _Verdict]:
    def rule(_edge: EdgeRecord, _index: QualificationIndex) -> _Verdict:
        return _qualified(basis)

    return rule


#: The rule each admissible producer is judged by, once its evidence resolves.
_ORIGIN_RULES: dict[RelationOrigin, Callable[[EdgeRecord, QualificationIndex], _Verdict]] = {
    "work-projector": _work_projector_rule,
    "claim-projector": _claim_projector_rule,
    "exact-duplicate": _exact_duplicate_rule,
    "producer-declared": _always("relation-field-evidence"),
    "repository-upstream": _repository_upstream_rule,
    "repository-owner": _always("record-membership"),
    "capability-record": _always("record-membership"),
    "artifact-capability": _always("record-membership"),
    "artifact-containment": _always("inventory"),
    "corpus-scope": _always("inventory"),
}


def _admission(edge: EdgeRecord, origin: RelationOrigin, index: QualificationIndex) -> str | None:
    """Return why ``edge`` fails before its producer's rule is consulted, if it does."""
    admissible = ADMISSIBLE_ORIGINS.get(edge.edge_type)
    if admissible is None:
        return REASON_TYPE_UNRECOGNIZED
    if origin == "artifact-classification":
        # The only thing the evidence establishes is that the artifact exists and
        # what kind of file it is. That is inventory, not this relation.
        return REASON_CLASSIFICATION_ONLY
    if origin not in admissible or origin not in _ORIGIN_RULES:
        return REASON_ORIGIN_UNSUPPORTED
    if not _resolved_evidence(edge, index):
        return REASON_EVIDENCE_MISSING
    return None


def qualify_relation(edge: EdgeRecord, index: QualificationIndex) -> RelationQualification:
    """Decide whether ``edge``'s own evidence proves the relation it states.

    Pure and deterministic: the same edge over the same index always yields the
    same decision, and nothing is mutated.
    """
    origin = relation_origin(edge, index)
    refused = _admission(edge, origin, index)
    if refused is not None:
        return _result(edge, origin, "unqualified", refused)
    status, reason = _ORIGIN_RULES[origin](edge, index)
    return _result(edge, origin, status, reason)
