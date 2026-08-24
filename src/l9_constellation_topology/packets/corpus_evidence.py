"""Evidence records for the corpus facts that are not producer statements.

Work signals get their evidence from ``document_signal_evidence``: each one is a
statement read at a coordinate, and the record says where. The rest of a corpus
packet is not statements — a duplicate relation is a comparison, a root is an
identity, a candidate is a grouping — and each still has to be able to say what
it rests on.

``DUPLICATE_OF`` is the one that matters most, because it is the strongest thing
this compiler will assert on a corpus's word. The edge claims two files hold
identical bytes; the evidence behind that claim is the hash both were found to
carry, the cluster the comparison put them in, and the identities compared.
Recording those makes the claim checkable after the fact: a reader can take the
hash, re-read the two files, and confirm or refute it without re-running the
producer. An edge asserting byte identity with nothing behind it would be an
assertion the compiler could not defend.

Root and corpus evidence is thinner and deliberately so. A root's evidence is
that a named packet observed it at a stated revision, which is a fact about
provenance rather than about content, and it is recorded as ``declared`` for a
root an operator named and ``observed`` for one the producer discovered.
"""

from __future__ import annotations

from l9_constellation_topology.domain.corpus import corpus_confidence, root_confidence
from l9_constellation_topology.domain.edge import (
    EXACT_DUPLICATE_METHOD,
    canonical_pair,
    duplicate_confidence,
)
from l9_constellation_topology.run.evidence import (
    EvidenceRecord,
    EvidenceSourceRef,
    make_evidence_record,
)

from .assertion_evidence import ASSERTION_EVIDENCE_CREATED_AT
from .corpus_intelligence import CorpusIntelligencePacket

#: Stage recorded on evidence for byte-identity comparisons.
DUPLICATE_EVIDENCE_STAGE = "ingest_exact_duplicates"

#: Stage recorded on evidence for corpus and root scope.
CORPUS_SCOPE_EVIDENCE_STAGE = "ingest_corpus_scope"


def duplicate_evidence_records(
    packet: CorpusIntelligencePacket,
) -> tuple[EvidenceRecord, ...]:
    """Return one evidence record per exact duplicate relation.

    Keyed by the canonically ordered pair, so the relation discovered from either
    side produces one record — the same reason the edge itself is keyed that way.
    """
    if packet.payload is None:
        return ()
    confidence = duplicate_confidence()
    records: dict[str, EvidenceRecord] = {}
    for relation in packet.payload.exact_duplicate_relations:
        first, second = canonical_pair(relation.artifact_a_id, relation.artifact_b_id)
        record = make_evidence_record(
            # The cluster, not either artifact. Filing this under an artifact's
            # `content_hash` would put it in the same reconciliation group as
            # that artifact's own observed hash, and a single-valued field
            # holding both the hash and this record's structured value reads as
            # a contradiction — one manufactured entirely by the choice of
            # subject. What this evidence is about is the cluster.
            subject_id=relation.duplicate_cluster_id,
            # Set-valued: several relations drawn from one cluster are several
            # true statements about its membership, never competing answers.
            field="artifact_ids",
            stage=DUPLICATE_EVIDENCE_STAGE,
            # A comparison the producer performed and recorded, not something a
            # repository declared about itself.
            evidence_class="observed",
            source_type="packet",
            source_ref=EvidenceSourceRef(
                # The bytes both artifacts were found to carry. This is what
                # makes the claim independently checkable.
                content_hash=relation.content_hash,
                packet_id=packet.packet_id,
            ),
            value={
                "duplicate_cluster_id": relation.duplicate_cluster_id,
                "artifact_a_id": first,
                "artifact_b_id": second,
                "content_hash": relation.content_hash,
                "method": EXACT_DUPLICATE_METHOD,
            },
            confidence=confidence,
            producer=packet.producer.name,
            producer_version=packet.producer.version,
            created_at=ASSERTION_EVIDENCE_CREATED_AT,
        )
        records[record.evidence_id] = record
    return tuple(sorted(records.values(), key=lambda item: item.evidence_id))


def duplicate_evidence_by_relation(
    packet: CorpusIntelligencePacket,
) -> dict[str, tuple[str, ...]]:
    """Return ``relation_id`` -> the evidence ids supporting it."""
    if packet.payload is None:
        return {}
    by_pair = {
        (
            record.value["artifact_a_id"],
            record.value["artifact_b_id"],
        ): record.evidence_id
        for record in duplicate_evidence_records(packet)
        if isinstance(record.value, dict)
    }
    index: dict[str, tuple[str, ...]] = {}
    for relation in packet.payload.exact_duplicate_relations:
        pair = canonical_pair(relation.artifact_a_id, relation.artifact_b_id)
        evidence_id = by_pair.get(pair)
        if evidence_id is not None:
            index[relation.relation_id] = (evidence_id,)
    return index


def corpus_scope_evidence_records(
    packet: CorpusIntelligencePacket,
) -> tuple[EvidenceRecord, ...]:
    """Return evidence for the corpus and each root it observed."""
    records: list[EvidenceRecord] = []
    descriptor = packet.corpus
    records.append(
        make_evidence_record(
            subject_id=descriptor.corpus_id,
            field="corpus_source_snapshot_id",
            stage=CORPUS_SCOPE_EVIDENCE_STAGE,
            evidence_class="declared",
            source_type="packet",
            source_ref=EvidenceSourceRef(packet_id=packet.packet_id),
            value={
                "corpus_source_snapshot_id": descriptor.corpus_source_snapshot_id,
                "corpus_analysis_id": descriptor.corpus_analysis_id,
                "root_ids": sorted(root.root_id for root in descriptor.root_refs),
                "coverage": descriptor.coverage.model_dump(mode="json"),
            },
            confidence=corpus_confidence(),
            producer=packet.producer.name,
            producer_version=packet.producer.version,
            created_at=ASSERTION_EVIDENCE_CREATED_AT,
        )
    )
    for root in descriptor.root_refs:
        records.append(
            make_evidence_record(
                subject_id=root.root_id,
                field="repository_model_packet_id",
                stage=CORPUS_SCOPE_EVIDENCE_STAGE,
                # A declared root was named by an operator; an inferred one was
                # found. The evidence class follows the identity class rather
                # than flattening the two.
                evidence_class=("declared" if root.identity_class == "declared" else "observed"),
                source_type="packet",
                source_ref=EvidenceSourceRef(
                    packet_id=root.repository_model_packet.packet_id,
                    source_revision=root.source_revision or None,
                ),
                value={
                    "identity_class": root.identity_class,
                    "repository_model_packet_id": root.repository_model_packet.packet_id,
                    "repository_model_semantic_hash": (root.repository_model_packet.semantic_hash),
                    "repository_id": root.repository_id,
                    "source_revision": root.source_revision,
                },
                confidence=root_confidence(root.identity_class),
                producer=packet.producer.name,
                producer_version=packet.producer.version,
                created_at=ASSERTION_EVIDENCE_CREATED_AT,
            )
        )
    return tuple(sorted(records, key=lambda item: item.evidence_id))


def corpus_evidence_by_subject(
    packets: tuple[CorpusIntelligencePacket, ...],
) -> dict[str, tuple[str, ...]]:
    """Return ``subject_id`` -> evidence ids, for stamping corpus and root records."""
    index: dict[str, set[str]] = {}
    for packet in packets:
        for record in corpus_scope_evidence_records(packet):
            index.setdefault(record.subject_id, set()).add(record.evidence_id)
    return {key: tuple(sorted(value)) for key, value in sorted(index.items())}
