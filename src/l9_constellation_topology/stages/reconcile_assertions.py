"""Reconcile producer statements into canonical semantic claims.

Two producers reach this stage: repository-model assertions read out of source
files, and document work signals read out of Word documents, slide decks,
workbooks, notebooks, and PDFs. Both arrive as ``SemanticInput`` and neither is
distinguishable here, which is the point — a ``.docx`` plan declaring
``work.status = Complete`` and a ``.md`` plan declaring ``work.status = WIP`` are
one subject with two competing answers, and only a single engine reports that as
the conflict it is.

Grouping is by ``(subject_id, predicate)`` — the question being asked — and the
predicate registry decides what several answers to one question mean.

* A **set-valued** predicate takes the deterministic union of its objects. Nothing
  is a contradiction: fourteen dependencies are fourteen facts.
* A **single-valued** predicate resolves when every assertion agrees. Repeated
  agreement aggregates supporting evidence rather than being deduplicated away.
  Disagreement emits a ``ConflictRecord``, keeps *every* competing claim, and
  elects no winner. Authority may lower confidence; it never erases a claim.
* An **auxiliary** predicate reconciles as a set and never projects.
* An **unsupported** predicate is preserved exactly as asserted, with its
  evidence, plus a diagnostic and an unknown scoped to that predicate. Nothing is
  aggregated, nothing is called a contradiction, and nothing is dropped.

The stage adds no facts. Every claim it emits is a statement some producer made,
and every claim cites the evidence records built for those statements.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from l9_constellation_topology.domain.assessment import ConflictRecord, UnknownRecord
from l9_constellation_topology.domain.claim import (
    ClaimCardinality,
    ClaimSupport,
    SemanticClaimRecord,
)
from l9_constellation_topology.domain.confidence import (
    Authority,
    Completeness,
    ConfidenceAssessment,
    ConfidenceLevel,
    ConflictStatus,
    DerivationMethod,
    EvidenceStrength,
)
from l9_constellation_topology.domain.diagnostic import DiagnosticRecord
from l9_constellation_topology.packets.assertion_evidence import (
    ASSERTION_EVIDENCE_STAGE,
    named_authority,
    named_derivation,
    named_level,
)
from l9_constellation_topology.packets.document_signal_evidence import (
    DOCUMENT_SIGNAL_EVIDENCE_STAGE,
)
from l9_constellation_topology.reconciliation import (
    UNSUPPORTED_PREDICATE_CODE,
    UNSUPPORTED_PREDICATE_REASON,
    predicate_cardinality,
    predicate_support,
)
from l9_constellation_topology.reconciliation.inputs import SemanticInput
from l9_constellation_topology.run.evidence import EvidenceRecord, stable_id

STAGE_NAME = "reconcile_assertions"

#: Weakest-first, so aggregating a claim's confidence can only move downward.
_LEVEL_ORDER: tuple[ConfidenceLevel, ...] = (
    ConfidenceLevel.low,
    ConfidenceLevel.medium,
    ConfidenceLevel.high,
)

#: Weakest-first authority. A claim is never granted more authority than the
#: least authoritative assertion supporting it.
_AUTHORITY_ORDER: tuple[Authority, ...] = (
    Authority.unknown,
    Authority.candidate,
    Authority.derived,
    Authority.validated_machine,
    Authority.source,
)


#: Evidence stages that carry a reconcilable producer statement. Both write the
#: statement's identity under ``assertion_id``, so one index serves both.
_STATEMENT_EVIDENCE_STAGES = frozenset({ASSERTION_EVIDENCE_STAGE, DOCUMENT_SIGNAL_EVIDENCE_STAGE})


class AssertionEvidenceIndex:
    """Resolve the evidence record built for each producer statement.

    Statement evidence is created at the packet boundary, where the parent packet
    is available; by the time reconciliation runs, only the flattened statements
    and the evidence pool remain. The link back is the statement identity the
    evidence carries in its value, so the index is rebuilt from the pool rather
    than threaded through every intermediate stage.
    """

    def __init__(self, evidence: tuple[EvidenceRecord, ...]) -> None:
        index: dict[tuple[str, str], str] = {}
        for record in evidence:
            if record.stage not in _STATEMENT_EVIDENCE_STAGES:
                continue
            value: Any = record.value
            if not isinstance(value, dict):
                continue
            assertion_id = value.get("assertion_id")
            if isinstance(assertion_id, str):
                index[(record.subject_id, assertion_id)] = record.evidence_id
        self._by_assertion = index

    def resolve(self, statement: SemanticInput) -> str | None:
        return self._by_assertion.get((statement.subject_id, statement.input_id))

    def resolve_all(self, statements: tuple[SemanticInput, ...]) -> tuple[str, ...]:
        resolved = {
            evidence_id
            for statement in statements
            if (evidence_id := self.resolve(statement)) is not None
        }
        return tuple(sorted(resolved))


def _claim_id(subject_id: str, predicate: str, obj: str) -> str:
    """Return the identity of a logical claim.

    Only the claim participates: the packet that carried it, the topology
    snapshot that compiled it, the wall clock, and the checkout path are all
    outside this identity by construction, because none of them are arguments.
    """
    return stable_id("claim", {"subject_id": subject_id, "predicate": predicate, "object": obj})


def _weakest_level(statements: tuple[SemanticInput, ...]) -> ConfidenceLevel:
    return min(
        (named_level(statement.confidence) for statement in statements),
        key=_LEVEL_ORDER.index,
        default=ConfidenceLevel.low,
    )


def _weakest_authority(statements: tuple[SemanticInput, ...]) -> Authority:
    return min(
        (named_authority(statement.authority) for statement in statements),
        key=_AUTHORITY_ORDER.index,
        default=Authority.unknown,
    )


def _derivation(statements: tuple[SemanticInput, ...]) -> DerivationMethod:
    methods = {named_derivation(statement.evidence_class) for statement in statements}
    if len(methods) == 1:
        return next(iter(methods))
    # Declared prose and observed code agreeing on one claim is corroboration
    # across independent records, which is exactly what cross-record names.
    return DerivationMethod.cross_record


def _claim_confidence(
    statements: tuple[SemanticInput, ...],
    *,
    evidence_count: int,
    conflict_status: ConflictStatus,
) -> ConfidenceAssessment:
    corroborated = evidence_count > 1
    return ConfidenceAssessment(
        level=_weakest_level(statements),
        evidence_strength=(
            EvidenceStrength.corroborated if corroborated else EvidenceStrength.direct
        ),
        derivation_method=_derivation(statements),
        authority=_weakest_authority(statements),
        completeness=(
            Completeness.partial
            if conflict_status is not ConflictStatus.none
            else Completeness.sufficient
        ),
        conflict_status=conflict_status,
    )


def _diagnostic(
    *,
    subject_id: str,
    predicate: str,
    source_packet_id: str,
    code: str,
    message: str,
    evidence_refs: tuple[str, ...],
    details: dict[str, object],
) -> DiagnosticRecord:
    return DiagnosticRecord(
        diagnostic_id=stable_id(
            "diagnostic",
            {"stage": STAGE_NAME, "code": code, "subject_id": subject_id, "field": predicate},
        ),
        source_packet_id=source_packet_id,
        stage=STAGE_NAME,
        severity="warning",
        code=code,
        message=message,
        # Compiler-raised rather than carried through from a producer. The
        # validator conserves *upstream* diagnostics by counting the preserved
        # disposition, so a locally derived one must not claim that disposition.
        category="compiler",
        disposition="translated",
        subject_id=subject_id,
        evidence_refs=evidence_refs,
        details=details,
    )


def _packet_id_for(
    evidence_by_id: dict[str, EvidenceRecord],
    evidence_refs: tuple[str, ...],
) -> str:
    """Return the parent packet a group's evidence came from.

    Every assertion in a group shares a subject, and a subject is produced by one
    repository-model packet, so the first resolvable packet identity is the
    group's. An unresolvable one is reported as such rather than invented.
    """
    for evidence_id in evidence_refs:
        record = evidence_by_id.get(evidence_id)
        if record is not None and record.source_ref.packet_id:
            return record.source_ref.packet_id
    return "packet:unresolved"


def run(
    statements: tuple[SemanticInput, ...],
    evidence: tuple[EvidenceRecord, ...],
) -> tuple[
    tuple[SemanticClaimRecord, ...],
    tuple[ConflictRecord, ...],
    tuple[UnknownRecord, ...],
    tuple[DiagnosticRecord, ...],
]:
    """Return reconciled claims plus the conflicts, unknowns, and diagnostics they raised."""
    index = AssertionEvidenceIndex(evidence)
    evidence_by_id = {record.evidence_id: record for record in evidence}

    # Grouped by the question asked, never by which producer asked it. A source
    # assertion and a document work signal about one subject and predicate land
    # in one group, which is what makes a cross-format contradiction visible.
    grouped: dict[tuple[str, str], list[SemanticInput]] = defaultdict(list)
    for statement in statements:
        grouped[(statement.subject_id, statement.predicate)].append(statement)

    claims: list[SemanticClaimRecord] = []
    conflicts: list[ConflictRecord] = []
    unknowns: list[UnknownRecord] = []
    diagnostics: list[DiagnosticRecord] = []

    for subject_id, predicate in sorted(grouped):
        group = tuple(grouped[(subject_id, predicate)])
        support: ClaimSupport = predicate_support(predicate)
        cardinality: ClaimCardinality = predicate_cardinality(predicate)

        # Objects, grouped so that repeated agreement aggregates evidence rather
        # than being collapsed into a single unsupported assertion.
        by_object: dict[str, list[SemanticInput]] = defaultdict(list)
        for statement in group:
            by_object[statement.object].append(statement)
        objects = tuple(sorted(by_object))

        group_evidence = index.resolve_all(group)
        source_packet_id = _packet_id_for(evidence_by_id, group_evidence)

        conflict_ids: tuple[str, ...] = ()
        conflict_status = ConflictStatus.none
        if cardinality == "single" and len(objects) > 1:
            conflict_id = stable_id(
                "conflict",
                {"subject_id": subject_id, "field": predicate, "values": objects},
            )
            conflicts.append(
                ConflictRecord(
                    conflict_id=conflict_id,
                    subject_id=subject_id,
                    field=predicate,
                    values=objects,
                    evidence_refs=group_evidence,
                    # Recorded, never resolved here: choosing between competing
                    # source claims needs an authority rule this compiler does
                    # not have. Publication holds the claims instead.
                    blocking=False,
                )
            )
            conflict_ids = (conflict_id,)
            conflict_status = ConflictStatus.confirmed
        elif cardinality == "unknown" and len(objects) > 1:
            # No declared arity, so whether these compete is genuinely not known.
            # Saying "possible" is the honest answer and lowers the ceiling;
            # saying "confirmed" would manufacture a contradiction.
            conflict_status = ConflictStatus.possible

        if support == "unsupported":
            unknowns.append(
                UnknownRecord(
                    unknown_id=stable_id(
                        "unknown",
                        {"subject_id": subject_id, "field": predicate, "values": objects},
                    ),
                    subject_id=subject_id,
                    field=predicate,
                    reason=UNSUPPORTED_PREDICATE_REASON,
                    evidence_refs=group_evidence,
                )
            )
            diagnostics.append(
                _diagnostic(
                    subject_id=subject_id,
                    predicate=predicate,
                    source_packet_id=source_packet_id,
                    code=UNSUPPORTED_PREDICATE_CODE,
                    message=(
                        f"assertion predicate {predicate!r} has no declared rule in the "
                        f"predicate registry; {len(group)} claim(s) on {subject_id} were "
                        "preserved with their evidence and not projected"
                    ),
                    evidence_refs=group_evidence,
                    details={
                        "predicate": predicate,
                        "objects": list(objects),
                        "assertion_count": len(group),
                    },
                )
            )

        for obj in objects:
            supporting = tuple(by_object[obj])
            evidence_refs = index.resolve_all(supporting)
            claims.append(
                SemanticClaimRecord(
                    claim_id=_claim_id(subject_id, predicate, obj),
                    subject_id=subject_id,
                    predicate=predicate,
                    object=obj,
                    source_assertion_ids=tuple(
                        sorted({statement.input_id for statement in supporting})
                    ),
                    evidence_refs=evidence_refs,
                    confidence=_claim_confidence(
                        supporting,
                        evidence_count=len(evidence_refs),
                        conflict_status=conflict_status,
                    ),
                    authority=_weakest_authority(supporting),
                    cardinality=cardinality,
                    support=support,
                    conflict_status=conflict_status,
                    conflict_ids=conflict_ids,
                )
            )

    return (
        tuple(sorted(claims, key=lambda item: item.claim_id)),
        tuple(sorted(conflicts, key=lambda item: item.conflict_id)),
        tuple(sorted(unknowns, key=lambda item: item.unknown_id)),
        tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id)),
    )
