"""Project reconciled semantic claims into stronger topology relations.

Preservation comes first: every claim already survives as a
``SemanticClaimRecord`` whether or not anything here fires. Projection is the
*second*, narrower step, and it runs only for predicates with an explicit
mapping in the table below. A predicate with no entry is not a failure and is
never dropped; it simply stays a claim.

Two rules keep a projection from asserting more than the assertion did.

**External identities stay external.** ``package.dependency`` naming ``fastapi``
does not mean a repository called ``fastapi`` was observed in this constellation.
The projected endpoint is an explicitly-labelled external identity
(``package:fastapi``), carrying its own graph node so the relation resolves,
and never a synthesized ``repo:`` identity that would let a downstream reader
mistake a PyPI package for a constellation member.

**Observation is not evaluation.** A projected route says a route was observed at
a path. It does not say the handler is complete, that the service is reachable,
or that an unfinished-work marker in the handler body settles whether the handler
works. The forbidden inferences the build specification names are absent here by
construction: there is no rule that reads ``http.handler_body_marker``, no rule
that turns ``package.framework`` into a service role, and no rule that equates
``package.name`` with ``service.name``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from l9_constellation_topology.domain.capability import CapabilityRecord
from l9_constellation_topology.domain.claim import SemanticClaimRecord
from l9_constellation_topology.domain.edge import Direction, EdgeRecord, EdgeType, GraphRecord
from l9_constellation_topology.reconciliation import is_projectable
from l9_constellation_topology.run.evidence import stable_id

#: Prefix for a package identity named by a dependency claim. Deliberately not
#: ``repo:``: this names a package the repository depends on, which may or may
#: not be an observed constellation repository.
EXTERNAL_PACKAGE_PREFIX = "package"

#: Prefix for a repository *reference* — a repository named in prose that this
#: compile did not observe.
REPOSITORY_REFERENCE_PREFIX = "repository-reference"

#: Prefix for a governance contract named as canonical by a repository.
CONTRACT_REFERENCE_PREFIX = "contract-reference"

#: Prefixes for capabilities projected from claims.
SERVICE_ACTION_PREFIX = "capability:service-action"
HTTP_ROUTE_PREFIX = "capability:http-route"


@dataclass(frozen=True)
class ClaimProjection:
    """Everything a claim set projected, plus which claims projected anything."""

    capabilities: tuple[CapabilityRecord, ...] = ()
    edges: tuple[EdgeRecord, ...] = ()
    nodes: tuple[GraphRecord, ...] = ()
    #: ``claim_id`` -> the topology entities that claim produced.
    entities_by_claim: dict[str, tuple[str, ...]] = field(default_factory=dict)


def _external_id(prefix: str, value: str) -> str:
    return f"{prefix}:{value}"


def _node(
    entity_id: str,
    label: str,
    claim: SemanticClaimRecord,
    properties: dict[str, object],
) -> GraphRecord:
    return GraphRecord(
        record_type="node",
        label=label,
        entity_id=entity_id,
        properties=properties,
        evidence_refs=claim.evidence_refs,
        confidence=claim.confidence,
    )


def _edge(
    source_id: str,
    target_id: str,
    edge_type: EdgeType,
    claim: SemanticClaimRecord,
    properties: dict[str, object],
) -> EdgeRecord:
    identity = {
        "source_id": source_id,
        "target_id": target_id,
        "edge_type": edge_type.value,
        "properties": properties,
    }
    return EdgeRecord(
        edge_id=stable_id("edge", identity),
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        direction=Direction.outbound,
        properties=properties,
        evidence_refs=claim.evidence_refs,
        confidence=claim.confidence,
    )


def _claim_properties(claim: SemanticClaimRecord) -> dict[str, object]:
    """Properties every projected entity carries, naming what it came from."""
    return {
        "projected_from_claim_id": claim.claim_id,
        "assertion_predicate": claim.predicate,
        "assertion_object": claim.object,
    }


def _project_dependency(
    claim: SemanticClaimRecord,
) -> tuple[tuple[CapabilityRecord, ...], tuple[EdgeRecord, ...], tuple[GraphRecord, ...]]:
    target = _external_id(EXTERNAL_PACKAGE_PREFIX, claim.object)
    properties = {
        **_claim_properties(claim),
        # Stated explicitly so a reader of the graph alone cannot mistake this
        # endpoint for a repository this compile actually observed.
        "endpoint_kind": "external-package-reference",
        "package_name": claim.object,
    }
    node = _node(
        target,
        "ExternalPackage",
        claim,
        {
            "package_name": claim.object,
            "observed_as_repository": False,
            "projected_from_claim_id": claim.claim_id,
        },
    )
    edge = _edge(claim.subject_id, target, EdgeType.depends_on, claim, properties)
    return (), (edge,), (node,)


def _project_canonical_contract(
    claim: SemanticClaimRecord,
) -> tuple[tuple[CapabilityRecord, ...], tuple[EdgeRecord, ...], tuple[GraphRecord, ...]]:
    target = _external_id(CONTRACT_REFERENCE_PREFIX, claim.object)
    properties = {
        **_claim_properties(claim),
        "endpoint_kind": "declared-contract-reference",
        "contract_reference": claim.object,
    }
    node = _node(
        target,
        "ContractReference",
        claim,
        {
            "contract_reference": claim.object,
            "resolved_to_artifact": False,
            "projected_from_claim_id": claim.claim_id,
        },
    )
    edge = _edge(claim.subject_id, target, EdgeType.governed_by, claim, properties)
    return (), (edge,), (node,)


def _project_replaced_by(
    claim: SemanticClaimRecord,
) -> tuple[tuple[CapabilityRecord, ...], tuple[EdgeRecord, ...], tuple[GraphRecord, ...]]:
    # "X replaced_by Y" means Y supersedes X. The edge is emitted in the
    # direction the taxonomy actually defines rather than inverting the meaning
    # to keep the subject on the left.
    successor = _external_id(REPOSITORY_REFERENCE_PREFIX, claim.object)
    properties = {
        **_claim_properties(claim),
        "endpoint_kind": "declared-repository-reference",
        "declared_by": claim.subject_id,
    }
    node = _node(
        successor,
        "RepositoryReference",
        claim,
        {
            "reference": claim.object,
            "observed_in_constellation": False,
            "projected_from_claim_id": claim.claim_id,
        },
    )
    edge = _edge(successor, claim.subject_id, EdgeType.supersedes, claim, properties)
    return (), (edge,), (node,)


def _project_service_action(
    claim: SemanticClaimRecord,
) -> tuple[tuple[CapabilityRecord, ...], tuple[EdgeRecord, ...], tuple[GraphRecord, ...]]:
    capability_id = stable_id(
        SERVICE_ACTION_PREFIX, {"subject_id": claim.subject_id, "action": claim.object}
    )
    capability = CapabilityRecord(
        capability_id=capability_id,
        name=claim.object,
        description=(
            f"Service action {claim.object!r} declared by {claim.subject_id}. "
            "Declaration only: no implementation completeness is asserted."
        ),
        implemented_by=(claim.subject_id,),
        evidence_refs=claim.evidence_refs,
        confidence=claim.confidence,
    )
    return (capability,), (), ()


def _project_http_route(
    claim: SemanticClaimRecord,
) -> tuple[tuple[CapabilityRecord, ...], tuple[EdgeRecord, ...], tuple[GraphRecord, ...]]:
    capability_id = stable_id(
        HTTP_ROUTE_PREFIX, {"subject_id": claim.subject_id, "route": claim.object}
    )
    capability = CapabilityRecord(
        capability_id=capability_id,
        name=claim.object,
        description=(
            f"HTTP route {claim.object!r} observed in {claim.subject_id}. "
            "Observation only: neither production reachability nor handler "
            "completeness is asserted."
        ),
        # Exposed rather than implemented: the repository presents the route.
        # Whether anything behind it works is not something a route observation
        # can establish.
        exposed_by=(claim.subject_id,),
        evidence_refs=claim.evidence_refs,
        confidence=claim.confidence,
    )
    return (capability,), (), ()


#: The projection table. Every predicate absent from it — supported, auxiliary,
#: or unsupported — stays a claim and nothing else.
_PROJECTORS = {
    "authority.canonical_contract": _project_canonical_contract,
    "http.route": _project_http_route,
    "package.dependency": _project_dependency,
    "repository.replaced_by": _project_replaced_by,
    "service.action": _project_service_action,
}

#: Derived from the table rather than restated beside it, so the set a reader
#: consults and the set the compiler applies cannot drift apart.
PROJECTED_PREDICATES: frozenset[str] = frozenset(_PROJECTORS)

_UNPROJECTABLE = PROJECTED_PREDICATES - {
    predicate for predicate in PROJECTED_PREDICATES if is_projectable(predicate)
}
if _UNPROJECTABLE:  # pragma: no cover - guarded at import; a build error
    raise ValueError(
        f"projection declared for predicates the registry withholds: {sorted(_UNPROJECTABLE)}"
    )


def project_claims(claims: tuple[SemanticClaimRecord, ...]) -> ClaimProjection:
    """Return the topology entities projected from claims that declare one."""
    capabilities: list[CapabilityRecord] = []
    edges: dict[str, EdgeRecord] = {}
    nodes: dict[str, GraphRecord] = {}
    entities_by_claim: dict[str, tuple[str, ...]] = {}

    for claim in sorted(claims, key=lambda item: item.claim_id):
        projector = _PROJECTORS.get(claim.predicate)
        # Auxiliary and unsupported predicates never project, even if a mapping
        # were added by mistake: the registry is the gate, not this table.
        if projector is None or not is_projectable(claim.predicate):
            continue
        claim_capabilities, claim_edges, claim_nodes = projector(claim)
        capabilities.extend(claim_capabilities)
        for edge in claim_edges:
            edges[edge.edge_id] = edge
        for node in claim_nodes:
            nodes.setdefault(node.entity_id, node)
        produced = tuple(
            sorted(
                {item.capability_id for item in claim_capabilities}
                | {item.edge_id for item in claim_edges}
                | {item.entity_id for item in claim_nodes}
            )
        )
        if produced:
            entities_by_claim[claim.claim_id] = produced

    return ClaimProjection(
        capabilities=tuple(sorted(capabilities, key=lambda item: item.capability_id)),
        edges=tuple(sorted(edges.values(), key=lambda item: item.edge_id)),
        nodes=tuple(sorted(nodes.values(), key=lambda item: item.entity_id)),
        entities_by_claim=entities_by_claim,
    )


def merge_projected_entities(
    *maps: dict[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    """Combine what several projections produced, per claim.

    A claim can project through more than one table: ``work.supersedes`` reaches
    the work projector, and a future predicate could reach both. Taking only one
    map would leave such a claim reporting a subset of what it actually produced.
    """
    merged: dict[str, set[str]] = {}
    for entities_by_claim in maps:
        for claim_id, produced in entities_by_claim.items():
            merged.setdefault(claim_id, set()).update(produced)
    return {claim_id: tuple(sorted(produced)) for claim_id, produced in sorted(merged.items())}


def apply_projection(
    claims: tuple[SemanticClaimRecord, ...],
    projection: ClaimProjection | dict[str, tuple[str, ...]],
) -> tuple[SemanticClaimRecord, ...]:
    """Stamp each claim with the topology entities it produced, if any.

    Accepts either a ``ClaimProjection`` or an already-merged map, because a
    claim's projected entities can come from more than one projector and only the
    caller knows which ran.
    """
    entities_by_claim = (
        projection.entities_by_claim if isinstance(projection, ClaimProjection) else projection
    )
    return tuple(
        claim.model_copy(
            update={
                "projected": claim.claim_id in entities_by_claim,
                "projected_entity_ids": entities_by_claim.get(claim.claim_id, ()),
            }
        )
        for claim in claims
    )
