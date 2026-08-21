"""Pure canonical graph construction plus v4 compatibility helpers."""

from __future__ import annotations

from l9_constellation_topology.domain import (
    ArtifactRecord,
    CapabilityRecord,
    ConfidenceAssessment,
    RepositoryRecord,
)
from l9_constellation_topology.domain import (
    Direction as CanonicalDirection,
)
from l9_constellation_topology.domain import (
    EdgeRecord as CanonicalEdgeRecord,
)
from l9_constellation_topology.domain import (
    EdgeType as CanonicalEdgeType,
)
from l9_constellation_topology.domain import (
    GraphRecord as CanonicalGraphRecord,
)
from l9_constellation_topology.run import stable_id


def _edge(
    source_id: str,
    target_id: str,
    edge_type: CanonicalEdgeType,
    *,
    evidence_refs: tuple[str, ...],
    confidence: ConfidenceAssessment,
    properties: dict[str, object] | None = None,
) -> CanonicalEdgeRecord:
    identity = {
        "source_id": source_id,
        "target_id": target_id,
        "edge_type": edge_type.value,
        "properties": properties or {},
    }
    return CanonicalEdgeRecord(
        edge_id=stable_id("edge", identity),
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        direction=CanonicalDirection.outbound,
        properties=properties or {},
        evidence_refs=tuple(sorted(set(evidence_refs))),
        confidence=confidence,
    )


def build_topology_graph(
    repositories: tuple[RepositoryRecord, ...],
    artifacts: tuple[ArtifactRecord, ...],
    capabilities: tuple[CapabilityRecord, ...],
    declared_edges: tuple[CanonicalEdgeRecord, ...] = (),
    external_nodes: tuple[CanonicalGraphRecord, ...] = (),
) -> tuple[tuple[CanonicalGraphRecord, ...], tuple[CanonicalEdgeRecord, ...]]:
    # External nodes are seeded first so a repository, artifact, or capability
    # that shares an identity with one wins the dedup below: an entity this
    # compile actually observed always outranks a reference to one it did not.
    nodes: list[CanonicalGraphRecord] = list(external_nodes)
    edges: dict[str, CanonicalEdgeRecord] = {edge.edge_id: edge for edge in declared_edges}

    for repository in repositories:
        nodes.append(
            CanonicalGraphRecord(
                record_type="node",
                label="Repository",
                entity_id=repository.repository_id,
                properties={
                    "name": repository.name,
                    "source_revision": repository.source_revision,
                    "primary_role": repository.primary_role,
                    "secondary_roles": list(repository.secondary_roles),
                    "languages": list(repository.languages),
                    "package_managers": list(repository.package_managers),
                    "confidence": repository.confidence.level.value,
                },
                evidence_refs=repository.evidence_refs,
                confidence=repository.confidence,
            )
        )
        for target_id in repository.upstream_repository_ids:
            edge = _edge(
                repository.repository_id,
                target_id,
                CanonicalEdgeType.depends_on,
                evidence_refs=repository.evidence_refs,
                confidence=repository.confidence,
            )
            edges[edge.edge_id] = edge
        for owner_id in repository.owner_ids:
            nodes.append(
                CanonicalGraphRecord(
                    record_type="node",
                    label="Owner",
                    entity_id=owner_id,
                    properties={"name": owner_id.removeprefix("owner:")},
                    evidence_refs=repository.evidence_refs,
                    confidence=repository.confidence,
                )
            )
            edge = _edge(
                repository.repository_id,
                owner_id,
                CanonicalEdgeType.owned_by,
                evidence_refs=repository.evidence_refs,
                confidence=repository.confidence,
            )
            edges[edge.edge_id] = edge

    for artifact in artifacts:
        nodes.append(
            CanonicalGraphRecord(
                record_type="node",
                label="Artifact",
                entity_id=artifact.artifact_id,
                properties={
                    "repository_id": artifact.repository_id,
                    "source_path": artifact.source_path,
                    "artifact_type": artifact.artifact_type,
                    "content_hash": artifact.content_hash,
                },
                evidence_refs=artifact.evidence_refs,
                confidence=artifact.confidence,
            )
        )
        contains = _edge(
            artifact.repository_id,
            artifact.artifact_id,
            CanonicalEdgeType.contains,
            evidence_refs=artifact.evidence_refs,
            confidence=artifact.confidence,
        )
        edges[contains.edge_id] = contains
        semantic_type = {
            "architecture-decision": CanonicalEdgeType.governed_by,
            "governance": CanonicalEdgeType.governed_by,
            "documentation": CanonicalEdgeType.documented_by,
            "ci-workflow": CanonicalEdgeType.validated_by,
        }.get(artifact.artifact_type)
        if semantic_type is not None:
            relation = _edge(
                artifact.repository_id,
                artifact.artifact_id,
                semantic_type,
                evidence_refs=artifact.evidence_refs,
                confidence=artifact.confidence,
            )
            edges[relation.edge_id] = relation
        for capability_id in artifact.capabilities:
            relation = _edge(
                artifact.artifact_id,
                capability_id,
                CanonicalEdgeType.implements,
                evidence_refs=artifact.evidence_refs,
                confidence=artifact.confidence,
            )
            edges[relation.edge_id] = relation

    for capability in capabilities:
        nodes.append(
            CanonicalGraphRecord(
                record_type="node",
                label="Capability",
                entity_id=capability.capability_id,
                properties={"name": capability.name, "description": capability.description},
                evidence_refs=capability.evidence_refs,
                confidence=capability.confidence,
            )
        )
        for implementer_id in capability.implemented_by:
            relation = _edge(
                implementer_id,
                capability.capability_id,
                CanonicalEdgeType.implements,
                evidence_refs=capability.evidence_refs,
                confidence=capability.confidence,
            )
            edges[relation.edge_id] = relation
        for exposed_by in capability.exposed_by:
            relation = _edge(
                exposed_by,
                capability.capability_id,
                CanonicalEdgeType.exposes,
                evidence_refs=capability.evidence_refs,
                confidence=capability.confidence,
            )
            edges[relation.edge_id] = relation

    deduped_nodes: dict[str, CanonicalGraphRecord] = {}
    for node in nodes:
        deduped_nodes[node.entity_id] = node
    edge_records = tuple(sorted(edges.values(), key=lambda item: item.edge_id))
    graph_edges = tuple(
        CanonicalGraphRecord(
            record_type="edge",
            label=edge.edge_type.value,
            entity_id=edge.edge_id,
            properties={
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "edge_type": edge.edge_type.value,
                "direction": edge.direction.value,
                **edge.properties,
            },
            evidence_refs=edge.evidence_refs,
            confidence=edge.confidence,
        )
        for edge in edge_records
    )
    graph_records = (
        tuple(sorted(deduped_nodes.values(), key=lambda item: item.entity_id)) + graph_edges
    )
    return graph_records, edge_records


# Legacy compatibility surface.
from l9_constellation_topology.compatibility.v4_models import (  # noqa: E402
    Direction,
    EdgeCard,
    EdgeType,
    EvidenceItem,
    GraphRecord,
    RecordType,
    RepoCard,
    SourceType,
)


def _node_id(repo_id: str) -> str:
    return f"repo:{repo_id}"


def build_node(card: RepoCard) -> GraphRecord:
    return GraphRecord(
        record_type=RecordType.node,
        label="Repository",
        id=_node_id(card.repo_id),
        properties={
            "repo_id": card.repo_id,
            "name": card.name,
            "path": card.path,
            "primary_role": card.primary_role,
            "secondary_roles": card.secondary_roles,
            "languages": card.languages,
            "package_managers": card.package_managers,
            "ci_workflows": card.ci_workflows,
            "has_adr": bool(card.adr_files),
            "has_governance": bool(card.governance_files),
            "owner": card.owner,
            "confidence": card.confidence.value,
        },
        evidence=card.evidence[:5],
        source_file=card.path,
        confidence=card.confidence,
    )


def build_dependency_edges(cards: list[RepoCard]) -> list[tuple[GraphRecord, EdgeCard]]:
    repo_names = {card.name.lower(): card.repo_id for card in cards}
    results: list[tuple[GraphRecord, EdgeCard]] = []
    for card in cards:
        for dependency in card.upstream_dependencies:
            target_id = repo_names.get(dependency.lower())
            if not target_id or target_id == card.repo_id:
                continue
            evidence = [
                EvidenceItem(
                    source_file=card.path,
                    source_type=SourceType.file,
                    excerpt=f"dep:{dependency}",
                )
            ]
            edge_card = EdgeCard(
                source=card.repo_id,
                target=target_id,
                edge_type=EdgeType.dependency,
                direction=Direction.outbound,
                evidence=evidence,
                confidence=card.confidence,
            )
            record = GraphRecord(
                record_type=RecordType.edge,
                label="DEPENDS_ON",
                id=f"edge:dep:{card.repo_id}:{target_id}",
                properties={
                    "source": card.repo_id,
                    "target": target_id,
                    "edge_type": "dependency",
                    "direction": "outbound",
                },
                evidence=evidence,
                source_file=card.path,
                confidence=card.confidence,
            )
            results.append((record, edge_card))
    return results


def build_graph(cards: list[RepoCard]) -> tuple[list[GraphRecord], list[EdgeCard]]:
    records = [build_node(card) for card in cards]
    edge_cards: list[EdgeCard] = []
    for record, edge_card in build_dependency_edges(cards):
        records.append(record)
        edge_cards.append(edge_card)
    return records, edge_cards
