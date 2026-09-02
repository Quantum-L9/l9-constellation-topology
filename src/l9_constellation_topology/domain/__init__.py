"""Canonical topology domain exports."""

from .artifact import ArtifactRecord
from .assessment import ConflictRecord, ImpactIndex, MaturityAssessment, RiskRecord, UnknownRecord
from .bridge_gap import (
    BRIDGE_GAP_SCHEMA_VERSION,
    ActivationIntent,
    BridgeDisposition,
    BridgeGapProjection,
    BridgeGapRecord,
    BridgeGapType,
    BridgeLifecycleState,
)
from .candidate import (
    CandidateClusterRecord,
    CandidateMethodScore,
    CandidateRelationRecord,
    CandidateStructuralEvidence,
    CandidateType,
    ConfidenceClass,
)
from .capability import CapabilityRecord
from .claim import ClaimCardinality, ClaimSupport, SemanticClaimRecord
from .confidence import (
    Authority,
    Completeness,
    ConfidenceAssessment,
    ConfidenceLevel,
    ConflictStatus,
    DerivationMethod,
    EvidenceStrength,
)
from .corpus import CorpusRecord, RootIdentityClass, RootRecord
from .diagnostic import DiagnosticRecord
from .edge import (
    EDGE_TAXONOMY_ID,
    EDGE_TAXONOMY_VERSION,
    NON_TRAVERSABLE_EDGE_TYPES,
    TRAVERSABLE_EDGE_TYPES,
    Direction,
    EdgeRecord,
    EdgeType,
    GraphRecord,
    edge_taxonomy_hash,
    edge_taxonomy_view,
)
from .flow import FlowRecord
from .readiness import FORBIDDEN_READINESS_FIELDS, ReadinessEvidenceRecord
from .reasoning import REASONING_TYPES, ReasoningType, TopologyReasoningCandidate
from .repository import RepositoryRecord
from .topology import TopologyState

__all__ = [
    "EDGE_TAXONOMY_ID",
    "EDGE_TAXONOMY_VERSION",
    "FORBIDDEN_READINESS_FIELDS",
    "NON_TRAVERSABLE_EDGE_TYPES",
    "REASONING_TYPES",
    "TRAVERSABLE_EDGE_TYPES",
    "ArtifactRecord",
    "BRIDGE_GAP_SCHEMA_VERSION",
    "ActivationIntent",
    "BridgeDisposition",
    "BridgeGapProjection",
    "BridgeGapRecord",
    "BridgeGapType",
    "BridgeLifecycleState",
    "Authority",
    "CandidateClusterRecord",
    "CandidateMethodScore",
    "CandidateRelationRecord",
    "CandidateStructuralEvidence",
    "CandidateType",
    "CapabilityRecord",
    "ClaimCardinality",
    "ClaimSupport",
    "Completeness",
    "ConfidenceAssessment",
    "ConfidenceClass",
    "ConfidenceLevel",
    "ConflictRecord",
    "ConflictStatus",
    "CorpusRecord",
    "DerivationMethod",
    "DiagnosticRecord",
    "Direction",
    "EdgeRecord",
    "EdgeType",
    "EvidenceStrength",
    "FlowRecord",
    "GraphRecord",
    "ImpactIndex",
    "MaturityAssessment",
    "ReadinessEvidenceRecord",
    "ReasoningType",
    "RepositoryRecord",
    "RiskRecord",
    "RootIdentityClass",
    "RootRecord",
    "SemanticClaimRecord",
    "TopologyReasoningCandidate",
    "TopologyState",
    "UnknownRecord",
    "edge_taxonomy_hash",
    "edge_taxonomy_view",
]
