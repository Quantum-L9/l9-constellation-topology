"""Materialized canonical topology state used during compilation."""

from __future__ import annotations

from l9_constellation_topology.run.evidence import EvidenceRecord

from .artifact import ArtifactRecord
from .assessment import ConflictRecord, ImpactIndex, MaturityAssessment, RiskRecord, UnknownRecord
from .base import FrozenModel
from .candidate import CandidateClusterRecord, CandidateRelationRecord
from .capability import CapabilityRecord
from .claim import SemanticClaimRecord
from .corpus import CorpusRecord, RootRecord
from .diagnostic import DiagnosticRecord
from .edge import EdgeRecord, GraphRecord
from .flow import FlowRecord
from .readiness import ReadinessEvidenceRecord
from .reasoning import TopologyReasoningCandidate
from .repository import RepositoryRecord


class TopologyState(FrozenModel):
    """Materialized topology, split by epistemic class.

    The field layout is the boundary. ``edge_records`` holds canonical relations
    and only those; every consumer that traverses topology — impact, flow,
    maturity, risk — reads it and therefore cannot see a candidate. Candidate
    analysis lives in ``candidate_relations`` and ``candidate_clusters``, which
    nothing canonical reads.

    That separation is enforced by where a record can be *put*, not by a flag on
    it. A boolean would have to be checked at every traversal, and the first
    place it was forgotten would silently promote similarity into dependency.
    """

    # Canonical: source-backed observation and deterministic derivation.
    repository_records: tuple[RepositoryRecord, ...] = ()
    artifact_records: tuple[ArtifactRecord, ...] = ()
    capability_records: tuple[CapabilityRecord, ...] = ()
    semantic_claims: tuple[SemanticClaimRecord, ...] = ()
    edge_records: tuple[EdgeRecord, ...] = ()
    flow_records: tuple[FlowRecord, ...] = ()
    graph_records: tuple[GraphRecord, ...] = ()
    risks: tuple[RiskRecord, ...] = ()
    maturity: tuple[MaturityAssessment, ...] = ()
    impact_indexes: tuple[ImpactIndex, ...] = ()

    # Corpus scope. Empty for a compile with no corpus intelligence input.
    corpus_records: tuple[CorpusRecord, ...] = ()
    root_records: tuple[RootRecord, ...] = ()

    # Candidate: explicitly not canonical, and structurally unable to become so.
    candidate_relations: tuple[CandidateRelationRecord, ...] = ()
    candidate_clusters: tuple[CandidateClusterRecord, ...] = ()

    # Derived measurement and forward-looking requests.
    readiness_evidence: tuple[ReadinessEvidenceRecord, ...] = ()
    topology_reasoning_candidates: tuple[TopologyReasoningCandidate, ...] = ()

    # Provenance and everything that went unresolved.
    evidence: tuple[EvidenceRecord, ...] = ()
    diagnostics: tuple[DiagnosticRecord, ...] = ()
    unknowns: tuple[UnknownRecord, ...] = ()
    conflicts: tuple[ConflictRecord, ...] = ()
