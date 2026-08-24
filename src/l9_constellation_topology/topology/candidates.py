"""Compile candidate analysis, and enrich it with structure topology can measure.

The producer proposes groups from what a corpus scan can see: shared keyphrases,
matching declared identifiers, duplicate clusters, embedding scores. Topology
holds something the producer did not — the compiled canonical graph. It knows
which of a candidate's members are byte-identical to each other, which explicitly
reference or depend on each other, which supersede which, and what their
reconciled claims say about status and kind.

That is genuinely new information about a candidate, and this module attaches it.
What it deliberately does not do is *decide* with it.

The asymmetry is the design. Structural contradiction may lower a candidate's
confidence and raise an ambiguity flag: finding that a "project" has members
declaring incompatible statuses is a reason to trust the grouping less, and
saying so costs nothing if the grouping was right anyway. Structural
corroboration may not raise it. Two members referencing each other is a fact
about them, not evidence that the producer's threshold was correct — and the
producer's own pass already had those references available when it assigned the
class. Raising here would silently override a decision made under rules this
compiler does not own, using an input that decision already saw.

So ``structural_support_count`` is a *measurement* published beside the
candidate, never a term in its confidence. A reader can see that a strong project
candidate has zero explicit links between its members, and decide what to do
about that. Nothing here decides it for them.
"""

from __future__ import annotations

from collections import Counter

from l9_constellation_topology.domain.artifact import ArtifactRecord
from l9_constellation_topology.domain.assessment import ConflictRecord
from l9_constellation_topology.domain.candidate import (
    AMBIGUITY_CONFLICTING_STATUS,
    AMBIGUITY_CROSS_ROOT,
    AMBIGUITY_STRUCTURALLY_DISCONNECTED,
    CandidateClusterRecord,
    CandidateMethodScore,
    CandidateRelationRecord,
    CandidateStructuralEvidence,
    weaken_to,
)
from l9_constellation_topology.domain.claim import SemanticClaimRecord
from l9_constellation_topology.domain.confidence import (
    Authority,
    Completeness,
    ConfidenceAssessment,
    ConfidenceLevel,
    ConflictStatus,
    DerivationMethod,
    EvidenceStrength,
)
from l9_constellation_topology.domain.edge import EdgeRecord, EdgeType, GraphRecord
from l9_constellation_topology.packets.corpus_intelligence import (
    CandidateCluster,
    CorpusIntelligencePacket,
    SemanticPairRelation,
)

#: Graph label prefix for every candidate projection.
#:
#: A candidate node and a candidate edge are labelled ``Candidate…`` and carry
#: ``canonical: False``. Both are needed: the label is what a reader sees, and
#: the property is what a query can filter on. Neither is a substitute for the
#: real separation, which is that candidates never enter ``edge_records`` at all.
CANDIDATE_LABEL_PREFIX = "Candidate"

#: Property stamped on every candidate graph record.
CANDIDATE_MARKER = "canonical"

#: Claim predicates read for a candidate's declared work state.
STATUS_PREDICATE = "work.status"
KIND_PREDICATE = "work.kind"

#: Confidence-level ceiling by producer confidence class. A candidate's topology
#: confidence is never higher than what its class supports.
_LEVEL_BY_CLASS = {
    "weak": ConfidenceLevel.low,
    "moderate": ConfidenceLevel.low,
    "strong": ConfidenceLevel.medium,
}


def candidate_confidence(
    confidence_class: str, *, conflicted: bool = False
) -> ConfidenceAssessment:
    """Return the topology confidence of a candidate.

    ``Authority.candidate`` always, and enforced by the record itself. However
    strong the producer's class, a similarity-derived grouping is a candidate:
    the authority names where the claim comes from, not how much the profile
    liked it.
    """
    return ConfidenceAssessment(
        level=_LEVEL_BY_CLASS.get(confidence_class, ConfidenceLevel.low),
        evidence_strength=EvidenceStrength.weak,
        derivation_method=DerivationMethod.heuristic,
        authority=Authority.candidate,
        completeness=Completeness.partial,
        conflict_status=ConflictStatus.possible if conflicted else ConflictStatus.none,
    )


def compile_candidate_relations(
    packet: CorpusIntelligencePacket,
) -> tuple[CandidateRelationRecord, ...]:
    """Lower every semantic pair relation into a candidate relation record."""
    if packet.payload is None:
        return ()
    return tuple(
        sorted(
            (_relation(relation) for relation in packet.payload.semantic_pair_relations),
            key=lambda item: item.relation_id,
        )
    )


def _relation(relation: SemanticPairRelation) -> CandidateRelationRecord:
    profile = relation.analysis_profile
    return CandidateRelationRecord(
        relation_id=relation.relation_id,
        source_artifact_id=relation.source_artifact_id,
        target_artifact_id=relation.target_artifact_id,
        methods=tuple(sorted(set(relation.methods))),
        method_scores=tuple(
            sorted(
                (
                    CandidateMethodScore(method=score.method, score=score.score)
                    for score in relation.method_scores
                ),
                key=lambda item: item.method,
            )
        ),
        evidence_refs=tuple(sorted(set(relation.evidence_refs))),
        confidence_class=relation.confidence_class,
        analysis_profile=f"{profile.profile_id}/{profile.profile_version}",
        upstream_candidate_id=relation.upstream_candidate_id,
        confidence=candidate_confidence(relation.confidence_class),
    )


class _StructuralIndex:
    """Canonical structure, indexed for per-candidate measurement."""

    def __init__(
        self,
        *,
        artifacts: tuple[ArtifactRecord, ...],
        edges: tuple[EdgeRecord, ...],
        claims: tuple[SemanticClaimRecord, ...],
        conflicts: tuple[ConflictRecord, ...],
        root_by_artifact: dict[str, str],
    ) -> None:
        self.repository_by_artifact = {
            record.artifact_id: record.repository_id for record in artifacts
        }
        self.capabilities_by_artifact = {
            record.artifact_id: tuple(record.capabilities) for record in artifacts
        }
        self.archive_members = frozenset(
            record.artifact_id for record in artifacts if "!/" in record.source_path
        )
        self.root_by_artifact = root_by_artifact
        # Edges are indexed as unordered endpoint pairs per type, because a
        # candidate asks "is there a link *inside* this group", which does not
        # depend on which member the producer happened to list first.
        self.edges_by_type: dict[EdgeType, set[frozenset[str]]] = {}
        for edge in edges:
            self.edges_by_type.setdefault(edge.edge_type, set()).add(
                frozenset({edge.source_id, edge.target_id})
            )
        self.external_dependency_targets = {
            edge.target_id
            for edge in edges
            if edge.edge_type is EdgeType.depends_on and edge.target_id.startswith("package:")
        }
        self.blocked_pairs = self.edges_by_type.get(EdgeType.blocked_by, set())
        self.claims_by_subject: dict[str, list[SemanticClaimRecord]] = {}
        for claim in claims:
            self.claims_by_subject.setdefault(claim.subject_id, []).append(claim)
        self.conflicted_subjects = {
            conflict.subject_id
            for conflict in conflicts
            if conflict.field in {STATUS_PREDICATE, KIND_PREDICATE}
        }

    def internal_pairs(self, edge_type: EdgeType, members: frozenset[str]) -> int:
        """Count edges of one type whose *both* endpoints are group members."""
        return sum(
            1
            for pair in self.edges_by_type.get(edge_type, ())
            if len(pair) == 2 and pair <= members
        )

    def subjects_for(self, members: frozenset[str]) -> frozenset[str]:
        """Return the claim subjects a group's members speak for.

        A claim's subject is normally the repository, and a candidate's members
        are files. Mapping through artifact ownership is what makes a candidate's
        declared work state readable at all.
        """
        subjects = set(members)
        subjects.update(
            repository_id
            for artifact_id, repository_id in self.repository_by_artifact.items()
            if artifact_id in members
        )
        return frozenset(subjects)


def _distribution(
    index: _StructuralIndex, subjects: frozenset[str], predicate: str
) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for subject in sorted(subjects):
        for claim in index.claims_by_subject.get(subject, ()):
            if claim.predicate == predicate:
                counter[claim.object] += 1
    return dict(sorted(counter.items()))


def _structural_evidence(
    candidate: CandidateCluster, index: _StructuralIndex
) -> CandidateStructuralEvidence:
    members = frozenset(candidate.member_artifact_ids)
    subjects = index.subjects_for(members)
    status_distribution = _distribution(index, subjects, STATUS_PREDICATE)
    kind_distribution = _distribution(index, subjects, KIND_PREDICATE)
    conflicting = sum(1 for subject in subjects if subject in index.conflicted_subjects)
    return CandidateStructuralEvidence(
        member_count=len(members),
        repository_count=len(
            {
                index.repository_by_artifact[member]
                for member in members
                if member in index.repository_by_artifact
            }
        ),
        root_count=len(
            {
                index.root_by_artifact[member]
                for member in members
                if member in index.root_by_artifact
            }
        ),
        archive_member_count=len(members & index.archive_members),
        internal_exact_duplicate_count=index.internal_pairs(EdgeType.duplicate_of, members),
        internal_explicit_reference_count=index.internal_pairs(EdgeType.references, members),
        internal_dependency_count=index.internal_pairs(EdgeType.depends_on, members),
        internal_supersession_count=index.internal_pairs(EdgeType.supersedes, members),
        blocker_count=sum(1 for pair in index.blocked_pairs if pair & members),
        work_status_distribution=status_distribution,
        work_kind_distribution=kind_distribution,
        conflicting_status_count=conflicting,
        capability_count=len(
            {
                capability
                for member in members
                for capability in index.capabilities_by_artifact.get(member, ())
            }
        ),
        external_dependency_count=len(
            {
                target
                for target in index.external_dependency_targets
                for pair in index.edges_by_type.get(EdgeType.depends_on, ())
                if target in pair and pair & members
            }
        ),
    )


def _ambiguity_flags(
    candidate: CandidateCluster, evidence: CandidateStructuralEvidence
) -> tuple[str, ...]:
    """Return the producer's flags plus the ones topology's structure raises."""
    flags = set(candidate.ambiguity_flags)
    if evidence.conflicting_status_count or len(evidence.work_status_distribution) > 1:
        flags.add(AMBIGUITY_CONFLICTING_STATUS)
    # Zero explicit links between members is worth saying out loud. It does not
    # make the candidate wrong: nothing in the corpus may connect two documents
    # that are unmistakably about one project. It makes it unsupported by
    # structure, which is a different and useful thing for a reader to know.
    if evidence.member_count > 1 and evidence.structural_support_count == 0:
        flags.add(AMBIGUITY_STRUCTURALLY_DISCONNECTED)
    if evidence.root_count > 1:
        flags.add(AMBIGUITY_CROSS_ROOT)
    return tuple(sorted(flags))


def compile_candidate_clusters(
    packet: CorpusIntelligencePacket,
    *,
    artifacts: tuple[ArtifactRecord, ...],
    edges: tuple[EdgeRecord, ...],
    claims: tuple[SemanticClaimRecord, ...],
    conflicts: tuple[ConflictRecord, ...],
    root_by_artifact: dict[str, str],
    readiness_by_subject: dict[str, str] | None = None,
) -> tuple[CandidateClusterRecord, ...]:
    """Lower and structurally enrich every candidate cluster the packet carries."""
    if packet.payload is None:
        return ()
    index = _StructuralIndex(
        artifacts=artifacts,
        edges=edges,
        claims=claims,
        conflicts=conflicts,
        root_by_artifact=root_by_artifact,
    )
    readiness = readiness_by_subject or {}
    records: list[CandidateClusterRecord] = []
    for group in (
        packet.payload.topic_candidates,
        packet.payload.project_candidates,
        packet.payload.consolidation_candidates,
    ):
        for candidate in group:
            evidence = _structural_evidence(candidate, index)
            flags = _ambiguity_flags(candidate, evidence)
            # Lower, never raise. A structural contradiction is a reason to trust
            # the grouping less; structural agreement is not a reason to trust it
            # more, because the producer's own pass already saw those links.
            confidence_class = candidate.confidence_class
            if AMBIGUITY_CONFLICTING_STATUS in flags:
                confidence_class = weaken_to(confidence_class, "weak")
            elif AMBIGUITY_STRUCTURALLY_DISCONNECTED in flags:
                confidence_class = weaken_to(confidence_class, "moderate")
            profile = candidate.analysis_profile
            records.append(
                CandidateClusterRecord(
                    candidate_id=candidate.candidate_id,
                    candidate_type=candidate.candidate_type,
                    member_entity_ids=tuple(sorted(set(candidate.member_artifact_ids))),
                    supporting_relation_ids=tuple(sorted(set(candidate.supporting_relation_ids))),
                    evidence_refs=tuple(sorted(set(candidate.evidence_refs))),
                    confidence_class=confidence_class,
                    ambiguity_flags=flags,
                    cross_root=evidence.root_count > 1 or candidate.cross_root,
                    cross_archive=candidate.cross_archive,
                    analysis_profile=f"{profile.profile_id}/{profile.profile_version}",
                    upstream_candidate_id=candidate.upstream_candidate_id or candidate.candidate_id,
                    structural_evidence=evidence,
                    readiness_evidence_ref=readiness.get(candidate.candidate_id),
                    confidence=candidate_confidence(
                        confidence_class,
                        conflicted=AMBIGUITY_CONFLICTING_STATUS in flags,
                    ),
                )
            )
    return tuple(sorted(records, key=lambda item: item.candidate_id))


def candidate_graph_records(
    relations: tuple[CandidateRelationRecord, ...],
    clusters: tuple[CandidateClusterRecord, ...],
) -> tuple[GraphRecord, ...]:
    """Project candidates into the graph, labelled so they cannot be confused.

    Every record produced here carries ``canonical: False`` and a ``Candidate``
    label. A candidate edge is emitted as a ``node`` record rather than an
    ``edge`` record on purpose: the graph's edge records are built from
    ``edge_records``, and an edge-shaped candidate would be one filter away from
    being traversed as though it were one.
    """
    records: list[GraphRecord] = []
    for cluster in clusters:
        records.append(
            GraphRecord(
                record_type="node",
                label=f"{CANDIDATE_LABEL_PREFIX}Cluster",
                entity_id=cluster.candidate_id,
                properties={
                    CANDIDATE_MARKER: False,
                    "candidate_type": cluster.candidate_type,
                    "confidence_class": cluster.confidence_class,
                    "member_entity_ids": list(cluster.member_entity_ids),
                    "member_count": cluster.structural_evidence.member_count,
                    "structural_support_count": (
                        cluster.structural_evidence.structural_support_count
                    ),
                    "ambiguity_flags": list(cluster.ambiguity_flags),
                    "cross_root": cluster.cross_root,
                    "analysis_profile": cluster.analysis_profile,
                },
                evidence_refs=cluster.evidence_refs,
                confidence=cluster.confidence,
            )
        )
    for relation in relations:
        records.append(
            GraphRecord(
                record_type="node",
                label=f"{CANDIDATE_LABEL_PREFIX}Relation",
                entity_id=relation.relation_id,
                properties={
                    CANDIDATE_MARKER: False,
                    "source_artifact_id": relation.source_artifact_id,
                    "target_artifact_id": relation.target_artifact_id,
                    "confidence_class": relation.confidence_class,
                    "methods": list(relation.methods),
                    "analysis_profile": relation.analysis_profile,
                },
                evidence_refs=relation.evidence_refs,
                confidence=relation.confidence,
            )
        )
    return tuple(sorted(records, key=lambda item: item.entity_id))
