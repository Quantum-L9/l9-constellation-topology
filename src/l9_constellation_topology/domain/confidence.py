"""Decomposed confidence model used by canonical decisions."""

from __future__ import annotations

from enum import StrEnum

from .base import FrozenModel


class ConfidenceLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class EvidenceStrength(StrEnum):
    none = "none"
    weak = "weak"
    corroborated = "corroborated"
    direct = "direct"


class DerivationMethod(StrEnum):
    declared = "declared"
    deterministic = "deterministic"
    cross_record = "cross-record"
    heuristic = "heuristic"
    model_assisted = "model-assisted"
    unknown = "unknown"


class Authority(StrEnum):
    source = "source"
    validated_machine = "validated-machine"
    derived = "derived"
    candidate = "candidate"
    unknown = "unknown"


class Completeness(StrEnum):
    partial = "partial"
    sufficient = "sufficient"
    complete = "complete"


class ConflictStatus(StrEnum):
    none = "none"
    possible = "possible"
    confirmed = "confirmed"


class ConfidenceAssessment(FrozenModel):
    level: ConfidenceLevel
    evidence_strength: EvidenceStrength
    derivation_method: DerivationMethod
    authority: Authority
    completeness: Completeness
    conflict_status: ConflictStatus = ConflictStatus.none

    @classmethod
    def direct(cls, *, complete: bool = True) -> ConfidenceAssessment:
        return cls(
            level=ConfidenceLevel.high,
            evidence_strength=EvidenceStrength.direct,
            derivation_method=DerivationMethod.declared,
            authority=Authority.source,
            completeness=Completeness.complete if complete else Completeness.sufficient,
        )

    @classmethod
    def deterministic(cls, *, corroborated: bool = False) -> ConfidenceAssessment:
        return cls(
            level=ConfidenceLevel.high if corroborated else ConfidenceLevel.medium,
            evidence_strength=(
                EvidenceStrength.corroborated if corroborated else EvidenceStrength.direct
            ),
            derivation_method=DerivationMethod.deterministic,
            authority=Authority.validated_machine,
            completeness=Completeness.sufficient,
        )

    @classmethod
    def candidate(cls) -> ConfidenceAssessment:
        return cls(
            level=ConfidenceLevel.low,
            evidence_strength=EvidenceStrength.weak,
            derivation_method=DerivationMethod.heuristic,
            authority=Authority.candidate,
            completeness=Completeness.partial,
        )

    @classmethod
    def unknown(cls) -> ConfidenceAssessment:
        return cls(
            level=ConfidenceLevel.low,
            evidence_strength=EvidenceStrength.none,
            derivation_method=DerivationMethod.unknown,
            authority=Authority.unknown,
            completeness=Completeness.partial,
        )
