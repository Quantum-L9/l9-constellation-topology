"""Internal publication boundary for topology-derived memory effects.

This package converts validated topology truth into a deterministic plan of
downstream ``memory.ingest`` intents. It owns eligibility, destination-neutral
lowering, and effect planning only. It contains no graph or memory client, and
durable admission remains owned by ``l9-graphiti-memory``.
"""

from .bundle import (
    PublicationBundleError,
    build_publication_plan_artifacts,
    eligible_intent_document,
    eligible_intents_bytes,
    publication_plan_bytes,
    validate_publication_plan,
)
from .contracts import (
    MEMORY_INGEST_OPERATION,
    PUBLICATION_PLAN_TYPE,
    PUBLICATION_PLAN_VERSION,
    EligibilityDecision,
    LoweringReceipt,
    MemoryAssertion,
    MemoryConfidence,
    MemoryEvidenceRef,
    MemoryIngestIntent,
    MemoryProvenance,
    MemorySourceRange,
    MemoryWriteRequest,
    PublicationCandidate,
    PublicationDiagnostic,
    PublicationPlan,
    SkippedCandidate,
)
from .eligibility import (
    EligibilityContext,
    PublicationEligibilityError,
    decide,
    require_publishable_topology,
)
from .identity import (
    EFFECT_IDENTITY_ALGORITHM_VERSION,
    candidate_id,
    candidate_identity,
    confidence_semantics,
    effect_identity,
    evidence_semantics,
    idempotency_key,
    plan_id,
)
from .lowering import (
    LoweredCandidate,
    LoweringError,
    TopologyIndex,
    lower_capability,
    lower_relationship,
    lower_repository,
    lower_semantic_claim,
)
from .plan import build_publication_plan, plan_publication_from_repository
from .policy import (
    PublicationPolicy,
    PublicationPolicyError,
    load_publication_policy,
)

__all__ = [
    "EFFECT_IDENTITY_ALGORITHM_VERSION",
    "MEMORY_INGEST_OPERATION",
    "PUBLICATION_PLAN_TYPE",
    "PUBLICATION_PLAN_VERSION",
    "EligibilityContext",
    "EligibilityDecision",
    "LoweredCandidate",
    "LoweringError",
    "LoweringReceipt",
    "MemoryAssertion",
    "MemoryConfidence",
    "MemoryEvidenceRef",
    "MemoryIngestIntent",
    "MemoryProvenance",
    "MemorySourceRange",
    "MemoryWriteRequest",
    "PublicationBundleError",
    "PublicationCandidate",
    "PublicationDiagnostic",
    "PublicationEligibilityError",
    "PublicationPlan",
    "PublicationPolicy",
    "PublicationPolicyError",
    "SkippedCandidate",
    "TopologyIndex",
    "build_publication_plan",
    "build_publication_plan_artifacts",
    "candidate_id",
    "candidate_identity",
    "confidence_semantics",
    "decide",
    "effect_identity",
    "eligible_intent_document",
    "eligible_intents_bytes",
    "evidence_semantics",
    "idempotency_key",
    "load_publication_policy",
    "lower_capability",
    "lower_relationship",
    "lower_repository",
    "lower_semantic_claim",
    "plan_id",
    "plan_publication_from_repository",
    "publication_plan_bytes",
    "require_publishable_topology",
    "validate_publication_plan",
]
