"""Compile exact duplicate relations into ``DUPLICATE_OF`` edges.

``DUPLICATE_OF`` means byte identity. Nothing else qualifies — not a near-
duplicate score, not an embedding cosine, not a matching filename — and the
input type enforces that: this module reads ``exact_duplicate_relations``, which
is the only domain of the corpus packet carrying a content hash both endpoints
share. There is no code path from a similarity score to this edge because there
is no parameter through which one could arrive.

Two properties of exact duplication shape the rest:

**It is symmetric.** Byte equality holds in both directions, so the edge is
bidirectional and its identity must not depend on which endpoint was written
first. Identity is therefore computed over the *ordered* pair — smaller
identity first — so the same relation discovered from either side is one edge.

**It is transitive, and that is expensive.** A cluster of `n` byte-identical
files has `n(n-1)/2` pairs, which for a corpus holding a hundred copies of one
licence file is four thousand nine hundred and fifty edges saying one thing.
So a cluster is emitted as a *star*: every member is joined to the cluster's
deterministically chosen representative, giving `n-1` edges. The full relation
is recoverable — membership of one cluster is exactly what byte equality means —
without the graph carrying the clique.

The representative is a drawing convenience and is labelled as one. Every member
of an exact cluster is byte-equal to every other, so no member is the original,
the canonical copy, or the one to keep, and nothing here says otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

from l9_constellation_topology.domain.edge import (
    EXACT_DUPLICATE_METHOD,
    Direction,
    EdgeRecord,
    EdgeType,
    canonical_pair,
    duplicate_confidence,
)
from l9_constellation_topology.packets.corpus_intelligence import ExactDuplicateRelation
from l9_constellation_topology.run.evidence import stable_id


def duplicate_edge_id(artifact_a: str, artifact_b: str, content_hash: str) -> str:
    """Return the identity of one ``DUPLICATE_OF`` edge."""
    first, second = canonical_pair(artifact_a, artifact_b)
    return stable_id(
        "edge",
        {
            "edge_type": EdgeType.duplicate_of.value,
            "artifact_a_id": first,
            "artifact_b_id": second,
            "content_hash": content_hash,
        },
    )


@dataclass(frozen=True)
class DuplicateCluster:
    """One group of byte-identical artifacts."""

    cluster_id: str
    content_hash: str
    member_ids: tuple[str, ...]

    @property
    def representative_id(self) -> str:
        """The member a star is drawn toward. A convenience, not a verdict."""
        return self.member_ids[0]


def cluster_relations(
    relations: tuple[ExactDuplicateRelation, ...],
) -> tuple[DuplicateCluster, ...]:
    """Group duplicate relations into clusters, in deterministic order."""
    members: dict[str, set[str]] = {}
    hashes: dict[str, str] = {}
    for relation in relations:
        members.setdefault(relation.duplicate_cluster_id, set()).update(
            (relation.artifact_a_id, relation.artifact_b_id)
        )
        hashes[relation.duplicate_cluster_id] = relation.content_hash
    return tuple(
        DuplicateCluster(
            cluster_id=cluster_id,
            content_hash=hashes[cluster_id],
            member_ids=tuple(sorted(members[cluster_id])),
        )
        for cluster_id in sorted(members)
    )


def build_duplicate_edges(
    relations: tuple[ExactDuplicateRelation, ...],
    *,
    evidence_refs_by_relation: dict[str, tuple[str, ...]] | None = None,
) -> tuple[EdgeRecord, ...]:
    """Return one ``DUPLICATE_OF`` edge per cluster member beyond the first.

    A cluster of `n` members yields `n-1` star edges rather than `n(n-1)/2`
    clique edges. Membership of one exact cluster is the whole relation, and it
    is carried on every edge as ``duplicate_cluster_id``, so a consumer that
    wants the clique can reconstruct it from the cluster and a consumer that does
    not is spared a quadratic graph.
    """
    by_relation = evidence_refs_by_relation or {}
    evidence_by_cluster: dict[str, set[str]] = {}
    for relation in relations:
        evidence_by_cluster.setdefault(relation.duplicate_cluster_id, set()).update(
            by_relation.get(relation.relation_id, ())
        )

    confidence = duplicate_confidence()
    edges: dict[str, EdgeRecord] = {}
    for cluster in cluster_relations(relations):
        representative = cluster.representative_id
        evidence_refs = tuple(sorted(evidence_by_cluster.get(cluster.cluster_id, set())))
        for member in cluster.member_ids:
            if member == representative:
                continue
            first, second = canonical_pair(representative, member)
            properties: dict[str, object] = {
                "duplicate_cluster_id": cluster.cluster_id,
                # Both endpoints carry these bytes. One hash, because byte
                # equality admits exactly one.
                "content_hash": cluster.content_hash,
                "method": EXACT_DUPLICATE_METHOD,
                "cluster_member_count": len(cluster.member_ids),
                # Stated so nothing downstream reads the star's centre as a
                # recommendation about which copy to keep.
                "representative_artifact_id": representative,
                "representative_is_arbitrary": True,
            }
            edge = EdgeRecord(
                edge_id=duplicate_edge_id(first, second, cluster.content_hash),
                source_id=first,
                target_id=second,
                edge_type=EdgeType.duplicate_of,
                # Byte equality holds both ways. An outbound edge would imply a
                # direction the relation does not have.
                direction=Direction.bidirectional,
                properties=properties,
                evidence_refs=evidence_refs,
                confidence=confidence,
            )
            edges[edge.edge_id] = edge
    return tuple(sorted(edges.values(), key=lambda item: item.edge_id))
