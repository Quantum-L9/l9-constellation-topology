"""Decision-support records for missing capability lifecycle transitions."""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal

from pydantic import Field

from .base import FrozenModel
from .confidence import ConfidenceAssessment

BRIDGE_GAP_SCHEMA_VERSION: Final = "l9.bridge-gap-projection/v1"


class BridgeGapType(StrEnum):
    """Bridge gaps that current canonical topology can prove without live scanning."""

    built_unreachable = "BUILT_UNREACHABLE"
    exposed_unconsumed = "EXPOSED_UNCONSUMED"
    orphan_output = "ORPHAN_OUTPUT"


class BridgeLifecycleState(StrEnum):
    implemented = "IMPLEMENTED"
    validated = "VALIDATED"
    exposed = "EXPOSED"
    produced = "PRODUCED"
    consumed = "CONSUMED"


class ActivationIntent(StrEnum):
    """Operator intent, kept separate from observed lifecycle state."""

    required = "REQUIRED"
    optional = "OPTIONAL"
    deferred = "DEFERRED"
    prohibited = "PROHIBITED"
    unknown = "UNKNOWN"


class BridgeDisposition(StrEnum):
    """What a reviewer should do with a detected gap."""

    action_required = "ACTION_REQUIRED"
    intentional_dormancy = "INTENTIONAL_DORMANCY"
    correctly_disconnected = "CORRECTLY_DISCONNECTED"
    decision_required = "DECISION_REQUIRED"


class BridgeGapRecord(FrozenModel):
    bridge_gap_id: str
    subject_id: str
    subject_kind: Literal["capability", "output"]
    gap_type: BridgeGapType
    observed_state: BridgeLifecycleState
    expected_state: BridgeLifecycleState
    missing_transition: str
    activation_intent: ActivationIntent = ActivationIntent.unknown
    disposition: BridgeDisposition = BridgeDisposition.decision_required
    producer_ids: tuple[str, ...] = ()
    consumer_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason: str
    recommended_action: str
    confidence: ConfidenceAssessment = Field(default_factory=ConfidenceAssessment.unknown)


class BridgeGapProjection(FrozenModel):
    """Immutable report projection over one validated Topology Packet."""

    schema_version: Literal["l9.bridge-gap-projection/v1"] = BRIDGE_GAP_SCHEMA_VERSION
    source_packet_id: str
    source_semantic_hash: str
    policy_id: str
    policy_version: str
    policy_hash: str
    gaps: tuple[BridgeGapRecord, ...] = ()
    counts_by_type: dict[str, int] = Field(default_factory=dict)
    counts_by_disposition: dict[str, int] = Field(default_factory=dict)
    unknown_intent_count: int = Field(default=0, ge=0)
    semantic_hash: str
