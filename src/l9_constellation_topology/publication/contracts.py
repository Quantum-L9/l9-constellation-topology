"""Publication plan contracts and the destination-neutral memory intent mirror.

The ``Memory*`` models in this module mirror the ``l9-graphiti-memory`` write
contract field-for-field so that a lowered intent is accepted by the downstream
typed boundary without a translation shim. They are structural mirrors only:
this repository never imports a memory, Graphiti, or Neo4j client, and never
dispatches an intent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.packets.common import Producer
from l9_constellation_topology.packets.refs import PacketRef

PUBLICATION_PLAN_TYPE = "l9.topology-publication-plan"
PUBLICATION_PLAN_VERSION = "1.0.0"
MEMORY_INGEST_OPERATION = "memory.ingest"

#: Version of the rules that turn a canonical topology fact into a memory
#: intent. It participates in memory-effect identity because the same fact
#: lowered by different rules is a different effect.
LOWERING_CONTRACT_VERSION = "lowering/v1"

MemoryClassName = Literal[
    "identity",
    "preference",
    "constraint",
    "decision",
    "episodic",
    "semantic",
    "procedural",
    "observation",
    "insight",
    "meta",
]
EvidenceKindName = Literal[
    "explicit",
    "source_excerpt",
    "test",
    "observation",
    "inference",
    "aggregation",
    "governance_approval",
]
ConfidenceMethodName = Literal[
    "explicit",
    "extracted",
    "inferred",
    "aggregated",
    "calibrated",
]
EligibilityStatus = Literal["eligible", "held", "rejected"]
CandidateKind = Literal["entity", "relationship", "claim"]

#: Downstream admission requires one of these kinds when the confidence method
#: is inferred or aggregated.
DERIVATION_EVIDENCE_KINDS: frozenset[str] = frozenset(
    {"inference", "aggregation", "source_excerpt"}
)
#: Downstream confidence methods that require supporting evidence.
EVIDENCE_REQUIRING_METHODS: frozenset[str] = frozenset({"inferred", "aggregated"})

_SHA256_HEX = r"^[a-f0-9]{64}$"


class MemorySourceRange(FrozenModel):
    """Mirror of the downstream ``SourceRange`` contract."""

    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)


class MemoryProvenance(FrozenModel):
    """Mirror of the downstream ``Provenance`` contract."""

    source: str = Field(min_length=1, max_length=200)
    source_id: str | None = Field(default=None, max_length=500)
    source_digest: str | None = Field(default=None, pattern=_SHA256_HEX)
    source_range: MemorySourceRange | None = None
    source_agent_id: str | None = Field(default=None, max_length=200)
    session_id: str | None = Field(default=None, max_length=200)
    repository: str | None = Field(default=None, max_length=300)
    tool: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=200)
    extraction_method: str = Field(default="direct", max_length=100)
    source_trust: float = Field(default=1.0, ge=0.0, le=1.0)
    transformed_at: datetime


class MemoryEvidenceRef(FrozenModel):
    """Mirror of the downstream ``EvidenceRef`` contract."""

    kind: EvidenceKindName
    description: str = Field(min_length=1, max_length=2_000)
    source_id: str | None = Field(default=None, max_length=500)
    source_digest: str | None = Field(default=None, pattern=_SHA256_HEX)
    source_range: MemorySourceRange | None = None
    observed_at: datetime


class MemoryConfidence(FrozenModel):
    """Mirror of the downstream ``Confidence`` contract."""

    score: float = Field(default=1.0, ge=0.0, le=1.0)
    method: ConfidenceMethodName = "explicit"
    evidence_count: int = Field(default=1, ge=0)
    policy_version: str = Field(default="confidence/v1", min_length=1, max_length=100)
    calibrated_at: datetime


class MemoryAssertion(FrozenModel):
    """Mirror of the downstream ``MemoryAssertion`` contract."""

    subject: str | None = Field(default=None, max_length=500)
    predicate: str | None = Field(default=None, max_length=200)
    object: str | None = Field(default=None, max_length=2_000)

    @property
    def is_structured(self) -> bool:
        return bool(self.subject and self.predicate and self.object)


class MemoryWriteRequest(FrozenModel):
    """Mirror of the downstream ``MemoryWriteRequest`` contract.

    ``consent`` is typed as ``None`` because topology never grants consent on
    another subject's behalf, and ``dry_run`` stays at the downstream default
    because this repository plans effects rather than executing them.
    """

    namespace: str = Field(min_length=1, max_length=300)
    memory_class: MemoryClassName = "observation"
    content: str = Field(min_length=1, max_length=64_000)
    assertion: MemoryAssertion | None = None
    provenance: MemoryProvenance
    evidence: tuple[MemoryEvidenceRef, ...] = ()
    confidence: MemoryConfidence
    valid_from: datetime
    valid_to: datetime | None = None
    source_observed_at: datetime | None = None
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=300)
    supersedes: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    consent: None = None
    dry_run: bool = False


class MemoryIngestIntent(FrozenModel):
    """Mirror of the downstream ``IngestMemoryIntent`` discriminated member."""

    operation: Literal["memory.ingest"] = "memory.ingest"
    request: MemoryWriteRequest


class LoweringReceipt(FrozenModel):
    """Record exactly which topology facts and rules produced an intent."""

    source_fields: tuple[str, ...] = ()
    resolved_evidence_ids: tuple[str, ...] = ()
    truncated_evidence_count: int = Field(default=0, ge=0)
    derivation_evidence_kind: EvidenceKindName | None = None
    confidence_level: str
    confidence_method: ConfidenceMethodName
    conflict_status: str
    observed_conflict_ids: tuple[str, ...] = ()
    observed_unknown_ids: tuple[str, ...] = ()
    owning_repository_id: str | None = None
    #: Producer assertions this candidate was reconciled from. Empty for facts
    #: that were not lowered from the assertion domain.
    source_assertion_ids: tuple[str, ...] = ()
    assertion_predicate: str | None = None
    #: How the predicate registry classified the predicate. ``unsupported`` is
    #: recorded rather than hidden: it is why such a candidate is held.
    predicate_support: str | None = None


class EligibilityDecision(FrozenModel):
    """Fail-closed admission decision for a single publication candidate."""

    status: EligibilityStatus
    reasons: tuple[str, ...] = ()


class PublicationCandidate(FrozenModel):
    """A single topology fact lowered to a downstream memory intent."""

    candidate_id: str
    candidate_kind: CandidateKind
    source_topology_entity_ids: tuple[str, ...]
    source_evidence_ids: tuple[str, ...] = ()
    source_repository_model_packet_ids: tuple[str, ...] = ()
    eligibility: EligibilityDecision
    lowering: LoweringReceipt
    memory_intent: MemoryIngestIntent
    idempotency_key: str = Field(min_length=1, max_length=300)


class SkippedCandidate(FrozenModel):
    """A topology fact the versioned policy did not select for publication."""

    source_kind: CandidateKind
    source_id: str
    reason: str


class PublicationDiagnostic(FrozenModel):
    """Operator-visible counter or note about the publication plan."""

    code: str
    detail: str
    count: int = Field(default=0, ge=0)


class PublicationPlan(FrozenModel):
    """Derived, non-canonical plan of downstream memory effects."""

    plan_type: Literal["l9.topology-publication-plan"] = "l9.topology-publication-plan"
    plan_version: str = PUBLICATION_PLAN_VERSION
    plan_id: str
    producer: Producer
    source_topology_packet: PacketRef
    source_topology_semantic_hash: str
    policy: dict[str, Any]
    policy_hash: str
    candidates: tuple[PublicationCandidate, ...] = ()
    skipped_candidates: tuple[SkippedCandidate, ...] = ()
    diagnostics: tuple[PublicationDiagnostic, ...] = ()
    semantic_hash: str
    published_at: datetime

    @property
    def eligible_candidates(self) -> tuple[PublicationCandidate, ...]:
        return tuple(item for item in self.candidates if item.eligibility.status == "eligible")

    @property
    def held_candidates(self) -> tuple[PublicationCandidate, ...]:
        return tuple(item for item in self.candidates if item.eligibility.status == "held")

    @property
    def rejected_candidates(self) -> tuple[PublicationCandidate, ...]:
        return tuple(item for item in self.candidates if item.eligibility.status == "rejected")
