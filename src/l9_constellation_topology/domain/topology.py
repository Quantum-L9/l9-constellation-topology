"""Materialized canonical topology state used during compilation."""

from __future__ import annotations

from l9_constellation_topology.run.evidence import EvidenceRecord

from .artifact import ArtifactRecord
from .assessment import ConflictRecord, ImpactIndex, MaturityAssessment, RiskRecord, UnknownRecord
from .base import FrozenModel
from .capability import CapabilityRecord
from .diagnostic import DiagnosticRecord
from .edge import EdgeRecord, GraphRecord
from .flow import FlowRecord
from .repository import RepositoryRecord


class TopologyState(FrozenModel):
    repository_records: tuple[RepositoryRecord, ...] = ()
    artifact_records: tuple[ArtifactRecord, ...] = ()
    capability_records: tuple[CapabilityRecord, ...] = ()
    edge_records: tuple[EdgeRecord, ...] = ()
    flow_records: tuple[FlowRecord, ...] = ()
    graph_records: tuple[GraphRecord, ...] = ()
    risks: tuple[RiskRecord, ...] = ()
    maturity: tuple[MaturityAssessment, ...] = ()
    impact_indexes: tuple[ImpactIndex, ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()
    diagnostics: tuple[DiagnosticRecord, ...] = ()
    unknowns: tuple[UnknownRecord, ...] = ()
    conflicts: tuple[ConflictRecord, ...] = ()
