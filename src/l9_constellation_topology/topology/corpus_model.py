"""Build the corpus and root scope above repositories.

Two records and two containment edges. The interesting decisions are about what
must *not* be here.

**No absolute paths, anywhere.** A root's identity is the producer's root id,
which is derived from content and declaration rather than from a mount point.
``/Volumes/OldSSD/plans`` and ``/mnt/backup/plans`` holding identical bytes are
one root, and a topology whose identity moved when a drive was remounted would
be useless for exactly the archaeology this scope exists to support. The
validator enforces the absence; this module simply never has a filesystem path
to lose.

**A root is not a repository.** They coincide often and are different things: a
root is where bytes were read from, a repository is what the packet decided those
bytes were. A folder of Word documents is a root that owns no repository, and
``RootRecord.repository_id`` is therefore optional rather than derived.

**Declared and inferred roots are not equal.** A declared root was named by an
operator; an inferred one was discovered by finding a marker. The second is a
weaker claim about what the root *is*, and its authority is lowered to match
rather than the two being flattened into one word.
"""

from __future__ import annotations

from l9_constellation_topology.domain.confidence import ConfidenceAssessment
from l9_constellation_topology.domain.corpus import (
    CorpusRecord,
    RootRecord,
    corpus_confidence,
    root_confidence,
)
from l9_constellation_topology.domain.edge import Direction, EdgeRecord, EdgeType, GraphRecord
from l9_constellation_topology.packets.corpus_intelligence import CorpusIntelligencePacket
from l9_constellation_topology.run.evidence import stable_id


def compile_corpus_scope(
    packets: tuple[CorpusIntelligencePacket, ...],
) -> tuple[tuple[CorpusRecord, ...], tuple[RootRecord, ...]]:
    """Return one corpus record per packet, and every root they observed."""
    corpora: list[CorpusRecord] = []
    roots: dict[str, RootRecord] = {}
    for packet in packets:
        descriptor = packet.corpus
        for root in descriptor.root_refs:
            roots.setdefault(
                root.root_id,
                RootRecord(
                    root_id=root.root_id,
                    identity_class=root.identity_class,
                    source_revision=root.source_revision,
                    repository_model_packet_id=root.repository_model_packet.packet_id,
                    repository_id=root.repository_id,
                    confidence=root_confidence(root.identity_class),
                ),
            )
        corpora.append(
            CorpusRecord(
                corpus_id=descriptor.corpus_id,
                corpus_source_snapshot_id=descriptor.corpus_source_snapshot_id,
                corpus_analysis_id=descriptor.corpus_analysis_id,
                root_ids=tuple(sorted(root.root_id for root in descriptor.root_refs)),
                coverage_ref=packet.packet_id,
                confidence=corpus_confidence(),
            )
        )
    return (
        tuple(sorted(corpora, key=lambda item: item.corpus_id)),
        tuple(sorted(roots.values(), key=lambda item: item.root_id)),
    )


def _containment_edge(
    source_id: str,
    target_id: str,
    confidence: ConfidenceAssessment,
    evidence_refs: tuple[str, ...],
) -> EdgeRecord:
    """Return one containment edge, citing the record that established it.

    The evidence is the containing record's own: what says a corpus contains a
    root is the corpus descriptor that named it, and what says a root contains a
    repository is the packet reference that observed it. Emitting the edge
    without those refs would leave a canonical relation with `derived` authority
    and nothing behind it, which the validator refuses — correctly.
    """
    properties: dict[str, object] = {}
    identity = {
        "source_id": source_id,
        "target_id": target_id,
        "edge_type": EdgeType.contains.value,
        "properties": properties,
    }
    return EdgeRecord(
        edge_id=stable_id("edge", identity),
        source_id=source_id,
        target_id=target_id,
        edge_type=EdgeType.contains,
        direction=Direction.outbound,
        properties=properties,
        evidence_refs=evidence_refs,
        confidence=confidence,
    )


def corpus_scope_graph(
    corpora: tuple[CorpusRecord, ...],
    roots: tuple[RootRecord, ...],
) -> tuple[tuple[GraphRecord, ...], tuple[EdgeRecord, ...]]:
    """Return the corpus and root nodes, and their containment edges.

    A root contains a repository only when it observed one. Emitting the edge
    unconditionally would require a target for roots that own no repository, and
    the only available filler would be an invented identity.
    """
    nodes: list[GraphRecord] = []
    edges: dict[str, EdgeRecord] = {}

    for corpus in corpora:
        nodes.append(
            GraphRecord(
                record_type="node",
                label="Corpus",
                entity_id=corpus.corpus_id,
                properties={
                    "corpus_source_snapshot_id": corpus.corpus_source_snapshot_id,
                    "corpus_analysis_id": corpus.corpus_analysis_id,
                    "root_ids": list(corpus.root_ids),
                    "coverage_ref": corpus.coverage_ref,
                },
                evidence_refs=corpus.evidence_refs,
                confidence=corpus.confidence,
            )
        )
        for root_id in corpus.root_ids:
            edge = _containment_edge(
                corpus.corpus_id, root_id, corpus.confidence, corpus.evidence_refs
            )
            edges[edge.edge_id] = edge

    for root in roots:
        nodes.append(
            GraphRecord(
                record_type="node",
                label="Root",
                entity_id=root.root_id,
                properties={
                    "identity_class": root.identity_class,
                    "source_revision": root.source_revision,
                    "repository_model_packet_id": root.repository_model_packet_id,
                    "repository_id": root.repository_id,
                },
                evidence_refs=root.evidence_refs,
                confidence=root.confidence,
            )
        )
        if root.repository_id is not None:
            edge = _containment_edge(
                root.root_id, root.repository_id, root.confidence, root.evidence_refs
            )
            edges[edge.edge_id] = edge

    return (
        tuple(sorted(nodes, key=lambda item: item.entity_id)),
        tuple(sorted(edges.values(), key=lambda item: item.edge_id)),
    )


def root_by_artifact(
    packets: tuple[CorpusIntelligencePacket, ...],
    artifact_repository: dict[str, str],
) -> dict[str, str]:
    """Return ``artifact_id`` -> ``root_id``, via the repository each root owns.

    Artifacts are carried by Repository Model Packets, which know their
    repository but not the corpus root above it. The corpus packet supplies the
    missing hop, so a candidate's ``root_count`` is computed from recorded
    structure rather than from a path prefix.
    """
    root_by_repository: dict[str, str] = {}
    for packet in packets:
        for root in packet.corpus.root_refs:
            if root.repository_id is not None:
                root_by_repository.setdefault(root.repository_id, root.root_id)
    return {
        artifact_id: root_by_repository[repository_id]
        for artifact_id, repository_id in artifact_repository.items()
        if repository_id in root_by_repository
    }
