"""Fail-closed publication eligibility.

Eligibility never repairs a topology fact. It admits a lowered candidate, holds
it for unresolved evidence, or rejects it outright, and always records why.
"""

from __future__ import annotations

from dataclasses import dataclass

from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.packets.topology_packet import TopologyPacket

from .contracts import EligibilityDecision
from .lowering import LoweredCandidate, TopologyIndex
from .policy import PublicationPolicy

REASON_TOPOLOGY_NOT_VALIDATED = "topology.validation_not_passed"
REASON_MISSING_LINEAGE = "lineage.missing_repository_model_packets"
REASON_UNRESOLVED_ENTITY = "lineage.unresolved_topology_entity"
REASON_MATERIAL_CONFLICT = "conflict.unresolved_material"
REASON_MATERIAL_UNKNOWN = "unknown.unresolved_material"
REASON_MISSING_EVIDENCE = "evidence.required_but_missing"
REASON_UNSUPPORTED_PREDICATE = "predicate.unsupported_by_registry"
REASON_ADMITTED = "policy.admitted"

SKIP_ENTITY_KIND = "policy.entity_kind_not_selected"
SKIP_EDGE_TYPE = "policy.edge_type_not_selected"
#: A candidate domain is held from publication by default, and the hold is
#: recorded rather than left implicit.
#:
#: Candidates are already structurally unable to reach a lowering function: they
#: live in their own ``TopologyState`` fields and publication reads
#: ``edge_records``. Recording the skip anyway is what makes the containment
#: *auditable* — a plan that simply omitted them would look identical to a plan
#: compiled from a corpus that produced none, and "we held six project
#: candidates" and "there were no project candidates" are different facts.
SKIP_CANDIDATE_DOMAIN = "policy.candidate_domain_not_published"
#: Readiness is a measurement over derived analysis. Published as durable memory
#: it would read as a verdict about a body of work, which is exactly what its own
#: domain refuses to compute.
SKIP_READINESS_DOMAIN = "policy.readiness_evidence_not_published"
#: A reasoning candidate is a request for future adjudication, not a conclusion.
SKIP_REASONING_DOMAIN = "policy.reasoning_candidate_not_published"
#: An explicit work relation whose target did not resolve to exactly one observed
#: artifact. The declaration is real and stays in canonical topology; what cannot
#: be published is a durable assertion pointing at an endpoint this compile never
#: observed, which downstream would read as a resolved relation.
SKIP_UNRESOLVED_WORK_TARGET = "relation.work_target_not_exactly_resolved"
#: A claim whose subject, predicate, or object is empty cannot be stated as a
#: triple downstream. Recording it as skipped keeps it visible; letting the
#: lowering error escape would fail the whole plan over one malformed claim.
SKIP_UNSTATEABLE_CLAIM = "claim.not_expressible_as_assertion"


class PublicationEligibilityError(ValueError):
    """Raised when a plan cannot be built because topology truth is not admissible."""


@dataclass(frozen=True)
class EligibilityContext:
    """Everything eligibility needs beyond the candidate itself."""

    policy: PublicationPolicy
    packet: TopologyPacket
    index: TopologyIndex
    known_entity_ids: frozenset[str]

    @classmethod
    def build(
        cls,
        *,
        policy: PublicationPolicy,
        packet: TopologyPacket,
        state: TopologyState,
        index: TopologyIndex,
    ) -> EligibilityContext:
        known = {record.repository_id for record in state.repository_records}
        known |= {record.artifact_id for record in state.artifact_records}
        known |= {record.capability_id for record in state.capability_records}
        known |= {record.entity_id for record in state.graph_records}
        return cls(
            policy=policy,
            packet=packet,
            index=index,
            known_entity_ids=frozenset(known),
        )


def require_publishable_topology(packet: TopologyPacket, policy: PublicationPolicy) -> None:
    """Refuse to build a plan from topology that did not pass validation."""
    if policy.require_validated_topology and packet.validation.status != "passed":
        raise PublicationEligibilityError(
            "publication requires a Topology Packet whose validation status is "
            f"'passed'; received {packet.validation.status!r}"
        )


def _material_conflicts(
    candidate: LoweredCandidate, context: EligibilityContext
) -> tuple[str, ...]:
    fields = set(candidate.receipt.source_fields)
    material = []
    for entity_id in candidate.source_topology_entity_ids:
        for conflict in context.index.conflicts_by_subject.get(entity_id, ()):
            if conflict.blocking or conflict.field in fields:
                material.append(conflict.conflict_id)
    return tuple(sorted(set(material)))


def _material_unknowns(candidate: LoweredCandidate, context: EligibilityContext) -> tuple[str, ...]:
    fields = set(candidate.receipt.source_fields)
    material = []
    for entity_id in candidate.source_topology_entity_ids:
        for unknown in context.index.unknowns_by_subject.get(entity_id, ()):
            if unknown.field is None or unknown.field in fields:
                material.append(unknown.unknown_id)
    return tuple(sorted(set(material)))


def decide(candidate: LoweredCandidate, context: EligibilityContext) -> EligibilityDecision:
    """Return the fail-closed admission decision for one lowered candidate."""
    policy = context.policy
    rejections: list[str] = []
    holds: list[str] = []

    if policy.require_resolved_lineage:
        if not context.packet.inputs.repository_model_packets:
            rejections.append(REASON_MISSING_LINEAGE)
        unresolved = [
            entity_id
            for entity_id in candidate.source_topology_entity_ids
            if entity_id not in context.known_entity_ids
        ]
        if unresolved:
            rejections.append(REASON_UNRESOLVED_ENTITY)

    if policy.hold_on_material_conflict and _material_conflicts(candidate, context):
        holds.append(REASON_MATERIAL_CONFLICT)
    if policy.hold_on_material_unknown and _material_unknowns(candidate, context):
        holds.append(REASON_MATERIAL_UNKNOWN)
    if (
        policy.hold_on_missing_required_evidence
        and candidate.requires_evidence
        and not candidate.has_resolved_evidence
    ):
        holds.append(REASON_MISSING_EVIDENCE)
    # A claim whose predicate the registry does not declare is well formed and
    # fully evidenced; what its objects *mean* together is what is unknown. It is
    # held under a reason of its own so plan diagnostics say so, rather than
    # disappearing into a generic unknown or being skipped without a word.
    if (
        policy.hold_on_unsupported_predicate
        and candidate.receipt.predicate_support == "unsupported"
    ):
        holds.append(REASON_UNSUPPORTED_PREDICATE)

    if rejections:
        return EligibilityDecision(status="rejected", reasons=tuple(sorted(set(rejections))))
    if holds:
        return EligibilityDecision(status="held", reasons=tuple(sorted(set(holds))))
    return EligibilityDecision(status="eligible", reasons=(REASON_ADMITTED,))
