"""Fail-closed referential integrity for Corpus Intelligence Packets.

A corpus intelligence packet is an analysis *over* a named set of Repository
Model Packets. Every identity it mentions therefore has to resolve inside that
set, and the checks here are the whole of what that means:

* every root names an input packet, and every input packet is observed by a root;
* every artifact identity — a work signal's subject, a duplicate endpoint, a
  pair endpoint, a candidate member — resolves to an artifact one of those
  packets actually carried;
* every readiness subject is a candidate or a resolvable entity;
* every reasoning candidate names a candidate that exists;
* no work signal decoded from a format without lines claims a line locator.

A packet that fails any of them is refused rather than partially compiled. The
alternative — dropping the unresolvable records and compiling the rest — would
produce a topology that looks complete and silently omits whatever the producer
got wrong, which is the failure this boundary exists to make impossible.
"""

from __future__ import annotations

from l9_constellation_topology.run.evidence import LINE_LOCATOR_KINDS

from .corpus_intelligence import (
    CandidateCluster,
    CorpusIntelligencePacket,
    CorpusIntelligencePayload,
)
from .repository_model import RepositoryModelPacket

#: Document formats that genuinely have lines. A work signal decoded from
#: anything else may not carry a line locator: the coordinate would be a
#: fabrication of the flattening step, not a place in the source document.
LINE_BEARING_FORMATS: frozenset[str] = frozenset({"text", "markdown", "csv", "html", "ipynb"})


class CorpusIntelligenceValidationError(ValueError):
    """Raised when a corpus intelligence packet is not referentially sound."""

    def __init__(self, errors: tuple[str, ...]) -> None:
        self.errors = errors
        super().__init__(
            "corpus intelligence packet failed integrity validation:\n"
            + "\n".join(f"  - {error}" for error in errors)
        )


def _artifact_identities(packets: tuple[RepositoryModelPacket, ...]) -> frozenset[str]:
    """Every artifact identity the input packets carry.

    Repository and capability identities are included because a work signal's
    *subject* is normally the repository rather than the file: the file is where
    the signal was read, and the repository is what it is about.
    """
    identities: set[str] = set()
    for packet in packets:
        identities.add(packet.subject.repository_id)
        if packet.payload is None:
            continue
        identities.update(record.artifact_id for record in packet.payload.artifacts)
        identities.update(record.repository_id for record in packet.payload.repositories)
        identities.update(record.capability_id for record in packet.payload.capabilities)
    return frozenset(identities)


def _artifact_only_identities(packets: tuple[RepositoryModelPacket, ...]) -> frozenset[str]:
    """Artifact identities alone.

    Duplicate and pair endpoints are relations between *files*. Allowing a
    repository identity at either end would let "these two repositories are
    byte-identical" through, which is not a statement byte equality can make.
    """
    identities: set[str] = set()
    for packet in packets:
        if packet.payload is None:
            continue
        identities.update(record.artifact_id for record in packet.payload.artifacts)
    return frozenset(identities)


def _check_roots(
    packet: CorpusIntelligencePacket,
    packets: tuple[RepositoryModelPacket, ...],
    errors: list[str],
) -> None:
    loaded = {model.packet_id for model in packets}
    declared = {ref.packet_id for ref in packet.inputs.repository_model_packets}
    for missing in sorted(declared - loaded):
        errors.append(f"input repository-model packet did not resolve: {missing}")
    for extra in sorted(loaded - declared):
        errors.append(f"repository-model packet was loaded but is not a declared input: {extra}")

    by_id = {model.packet_id: model for model in packets}
    observed: set[str] = set()
    for root in packet.corpus.root_refs:
        reference = root.repository_model_packet
        observed.add(reference.packet_id)
        model = by_id.get(reference.packet_id)
        if model is None:
            errors.append(f"root {root.root_id} references unresolved packet {reference.packet_id}")
            continue
        if reference.semantic_hash != model.semantic_hash:
            errors.append(
                f"root {root.root_id} binds {reference.packet_id} at semantic hash "
                f"{reference.semantic_hash}, but the packet carries {model.semantic_hash}"
            )
        if reference.source_revision is not None and (
            reference.source_revision != model.source_snapshot.revision
        ):
            errors.append(
                f"root {root.root_id} binds {reference.packet_id} at revision "
                f"{reference.source_revision}, but the packet carries "
                f"{model.source_snapshot.revision}"
            )
    for unobserved in sorted(declared - observed):
        errors.append(f"declared input packet {unobserved} is not observed by any corpus root")


def _check_work_signals(
    payload: CorpusIntelligencePayload,
    identities: frozenset[str],
    artifacts: frozenset[str],
    errors: list[str],
) -> None:
    for signal in payload.document_work_signals:
        if signal.artifact_id not in artifacts:
            errors.append(
                f"document work signal {signal.signal_id} was read from artifact "
                f"{signal.artifact_id}, which no input packet carries"
            )
        if signal.subject_id not in identities:
            errors.append(
                f"document work signal {signal.signal_id} is about subject "
                f"{signal.subject_id}, which no input packet observed"
            )
        if (
            signal.locator.kind in LINE_LOCATOR_KINDS
            and signal.document_format not in LINE_BEARING_FORMATS
        ):
            errors.append(
                f"document work signal {signal.signal_id} was decoded from "
                f"{signal.document_format!r}, which has no lines, but cites a line locator; "
                "a structured coordinate is required"
            )


def _check_duplicates(
    payload: CorpusIntelligencePayload,
    artifacts: frozenset[str],
    errors: list[str],
) -> None:
    #: Byte equality is a property of the bytes, so every relation drawn from one
    #: cluster must cite one hash. Two hashes under one cluster id means the
    #: producer's clustering and its hashes disagree, and neither can be trusted.
    hashes_by_cluster: dict[str, set[str]] = {}
    for relation in payload.exact_duplicate_relations:
        for endpoint in (relation.artifact_a_id, relation.artifact_b_id):
            if endpoint not in artifacts:
                errors.append(
                    f"exact duplicate relation {relation.relation_id} names artifact "
                    f"{endpoint}, which no input packet carries"
                )
        hashes_by_cluster.setdefault(relation.duplicate_cluster_id, set()).add(
            relation.content_hash
        )
    for cluster_id, values in sorted(hashes_by_cluster.items()):
        if len(values) > 1:
            errors.append(
                f"duplicate cluster {cluster_id} carries more than one content hash: "
                f"{sorted(values)}; byte equality admits exactly one"
            )


def _check_pairs(
    payload: CorpusIntelligencePayload,
    artifacts: frozenset[str],
    errors: list[str],
) -> None:
    for relation in payload.semantic_pair_relations:
        for endpoint in (relation.source_artifact_id, relation.target_artifact_id):
            if endpoint not in artifacts:
                errors.append(
                    f"semantic pair relation {relation.relation_id} names artifact "
                    f"{endpoint}, which no input packet carries"
                )


def _check_candidate(
    candidate: CandidateCluster,
    artifacts: frozenset[str],
    relation_ids: frozenset[str],
    errors: list[str],
) -> None:
    """Check one candidate's members and supporting relations resolve."""
    for member in candidate.member_artifact_ids:
        if member not in artifacts:
            errors.append(
                f"candidate {candidate.candidate_id} names member {member}, "
                "which no input packet carries"
            )
    for supporting in candidate.supporting_relation_ids:
        if supporting not in relation_ids:
            errors.append(
                f"candidate {candidate.candidate_id} cites supporting relation "
                f"{supporting}, which this packet does not carry"
            )


def _check_candidates(
    payload: CorpusIntelligencePayload,
    artifacts: frozenset[str],
    errors: list[str],
) -> frozenset[str]:
    """Check every candidate domain, and return the identities they declare."""
    # A candidate cites what the producer grouped it by, and for byte identity
    # that is the *cluster* rather than any one edge in it: "these five files
    # are the same bytes" is one fact with one identity, and the four relations
    # carrying it are an encoding of that fact. The cluster is an identity this
    # packet carries — every duplicate relation states it — so accepting it is
    # not widening the check. Rewriting the citation to name one relation
    # instead would make the packet say something the producer did not.
    relation_ids = frozenset(
        {relation.relation_id for relation in payload.semantic_pair_relations}
        | {relation.relation_id for relation in payload.exact_duplicate_relations}
        | {relation.duplicate_cluster_id for relation in payload.exact_duplicate_relations}
    )
    candidates = (
        *payload.topic_candidates,
        *payload.project_candidates,
        *payload.consolidation_candidates,
    )
    for candidate in candidates:
        _check_candidate(candidate, artifacts, relation_ids, errors)
    return frozenset(candidate.candidate_id for candidate in candidates)


def _check_readiness(
    payload: CorpusIntelligencePayload,
    identities: frozenset[str],
    candidate_ids: frozenset[str],
    errors: list[str],
) -> None:
    for readiness in payload.readiness_evidence:
        if readiness.subject_id in candidate_ids or readiness.subject_id in identities:
            continue
        errors.append(
            f"readiness evidence {readiness.readiness_id} measures subject "
            f"{readiness.subject_id}, which is neither a candidate in this packet "
            "nor an entity any input packet observed"
        )


def _check_reasoning(
    payload: CorpusIntelligencePayload,
    candidate_ids: frozenset[str],
    artifacts: frozenset[str],
    errors: list[str],
) -> None:
    packs = set(payload.reasoning_evidence_pack_refs)
    for request in payload.reasoning_candidates:
        if request.candidate_id not in candidate_ids:
            errors.append(
                f"reasoning candidate {request.reasoning_candidate_id} names candidate "
                f"{request.candidate_id}, which this packet does not carry"
            )
        for member in request.member_artifact_ids:
            if member not in artifacts:
                errors.append(
                    f"reasoning candidate {request.reasoning_candidate_id} names member "
                    f"{member}, which no input packet carries"
                )
        if request.evidence_pack_ref is not None and request.evidence_pack_ref not in packs:
            errors.append(
                f"reasoning candidate {request.reasoning_candidate_id} references evidence "
                f"pack {request.evidence_pack_ref}, which this packet does not declare"
            )


def validate_corpus_intelligence_packet(
    packet: CorpusIntelligencePacket,
    repository_model_packets: tuple[RepositoryModelPacket, ...],
) -> None:
    """Refuse a corpus packet whose identities do not resolve against its inputs.

    Raises rather than returning findings: a corrupted or partial corpus packet
    must fail the compile closed, and a caller that had to remember to inspect a
    result would eventually not.
    """
    errors: list[str] = []
    if packet.payload is None:
        raise CorpusIntelligenceValidationError(
            ("corpus intelligence packet carries no materialized payload",)
        )
    payload = packet.payload

    _check_roots(packet, repository_model_packets, errors)
    identities = _artifact_identities(repository_model_packets)
    artifacts = _artifact_only_identities(repository_model_packets)
    _check_work_signals(payload, identities, artifacts, errors)
    _check_duplicates(payload, artifacts, errors)
    _check_pairs(payload, artifacts, errors)
    candidate_ids = _check_candidates(payload, artifacts, errors)
    _check_readiness(payload, identities, candidate_ids, errors)
    _check_reasoning(payload, candidate_ids, artifacts, errors)

    if errors:
        raise CorpusIntelligenceValidationError(tuple(sorted(set(errors))))
