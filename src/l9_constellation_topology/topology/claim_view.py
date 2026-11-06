"""A read model over reconciled semantic claims, at their actual evidentiary strength.

A source observation is useful before it becomes a canonical topology fact. A
header declaring ``injectable: true``, a document naming an owner, and a source
file importing a module can each answer a legitimate question without producing
a capability, an ``OWNED_BY`` edge, or a ``DEPENDS_ON`` edge. The canonical graph
holds only what qualified for projection; this module exposes the rest, and the
graph-backed part too, with the strength each claim actually has.

It is a pure derivation. Every view is computed from a ``SemanticClaimRecord``
and the ``EvidenceRecord`` objects it cites, inside one materialized Topology
packet. Nothing here is a canonical record, nothing is serialized into a packet,
and nothing is written: the original claim stays the source of truth, and a view
is recomputed whenever it is asked for (ADR-0034).

Three readings are kept apart on every view because collapsing them is how a
declaration gets mistaken for a fact:

* ``interpretation`` — what the predicate registry says a claim under this
  predicate establishes: a recognized declaration, an auxiliary observation, a
  key with an unresolved value, a key with no governed meaning, or a predicate
  the registry has no rule for at all.
* ``conflict_status`` — whether the claim competes with another claim on the
  same single-valued subject and predicate.
* ``projection_status`` — whether the claim produced any canonical topology
  entity, and whether its predicate could have.

A query for ``meta.managed.governance.owner`` therefore returns *declared*
ownership with its source location, never verified ownership; a query for
``meta.managed.classification.mcp_primitive`` returns the header's declared
classification, never proof that a working primitive exists.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.domain.claim import (
    ClaimCardinality,
    ClaimSupport,
    SemanticClaimRecord,
)
from l9_constellation_topology.domain.confidence import (
    Authority,
    ConfidenceAssessment,
    ConflictStatus,
)
from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.reconciliation import (
    HEADER_DECLARATION_PREDICATES,
    MANAGED_DECLARATION_PREDICATES,
    PREDICATE_POLICY_ID,
    PREDICATE_POLICY_VERSION,
    PredicateInterpretation,
    predicate_definition,
    predicate_interpretation,
    predicate_policy_hash,
)
from l9_constellation_topology.run import canonical_json
from l9_constellation_topology.run.evidence import EvidenceRecord
from l9_constellation_topology.topology.claim_projection import (
    ProjectionIneligibility,
    projection_ineligibility,
)

#: Whether a claim produced canonical topology, and whether it could have.
#: ``withheld`` means the predicate may project but the shared projection
#: boundary refused this claim because it is conflicted (ADR-0035).
ProjectionStatus = Literal["projected", "not-projected", "not-projectable", "withheld"]

#: Conflict filter a query accepts.
ConflictFilter = Literal["any", "none", "conflicted"]

#: Projection filter a query accepts.
ProjectionFilter = Literal["any", "projected", "unprojected"]

#: Upper bound on claims one query returns. A query is bounded by construction so
#: a large packet can never turn a read into an unbounded dump.
MAXIMUM_QUERY_LIMIT = 10_000

#: Default number of claims one query returns.
DEFAULT_QUERY_LIMIT = 500


class SourceLocation(FrozenModel):
    """Where one piece of evidence for a claim was read, exactly as recorded."""

    evidence_id: str
    source_path: str | None = None
    line_number: int | None = None
    content_hash: str | None = None
    source_revision: str | None = None
    packet_id: str | None = None
    #: The structured locator, when the producer reported one, as recorded.
    locator: dict[str, object] | None = None


class SemanticClaimView(FrozenModel):
    """One claim read through the predicate registry, with its provenance attached.

    Internal read type. It is not part of the Topology packet contract and must
    not be serialized into one without a separate packet-contract decision.
    """

    claim_id: str
    subject_id: str
    subject_kind: str
    predicate: str
    raw_value: str
    #: The declared value kind (``label``, ``boolean``, ``path``, …) when the
    #: registry declares one for this predicate; ``None`` otherwise.
    value_kind: str | None
    interpretation: PredicateInterpretation
    #: Where the predicate's meaning comes from (a ledger or producer-vocabulary
    #: reference), when the registry names one.
    definition_ref: str | None
    support: ClaimSupport
    cardinality: ClaimCardinality
    authority: Authority
    confidence: ConfidenceAssessment
    conflict_status: ConflictStatus
    conflict_ids: tuple[str, ...]
    source_assertion_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    source_locations: tuple[SourceLocation, ...]
    #: Evidence references the packet does not carry. Non-empty means the
    #: packet is internally inconsistent; it is reported, never hidden.
    missing_evidence_refs: tuple[str, ...]
    projection_status: ProjectionStatus
    #: Why the projection boundary refused the claim, when it did.
    projection_withheld_reason: ProjectionIneligibility | None = None
    projected_entity_ids: tuple[str, ...]
    #: ``<policy id>@<version>#<hash>`` of the registry this view was read under.
    interpretation_policy_ref: str


def interpretation_policy_ref() -> str:
    """Return the identity of the predicate registry this build interprets with."""
    return f"{PREDICATE_POLICY_ID}@{PREDICATE_POLICY_VERSION}#{predicate_policy_hash()}"


def subject_kind(subject_id: str) -> str:
    """Return the kind a subject identity names: its prefix, or ``unknown``."""
    prefix, separator, _ = subject_id.partition(":")
    if not separator or not prefix:
        return "unknown"
    return {"repo": "repository"}.get(prefix, prefix)


def _value_kind(predicate: str) -> str | None:
    declaration = HEADER_DECLARATION_PREDICATES.get(
        predicate
    ) or MANAGED_DECLARATION_PREDICATES.get(predicate)
    return declaration["object_type"] if declaration is not None else None


def _location(evidence: EvidenceRecord) -> SourceLocation:
    ref = evidence.source_ref
    return SourceLocation(
        evidence_id=evidence.evidence_id,
        source_path=ref.source_path,
        line_number=ref.line_number,
        content_hash=ref.content_hash,
        source_revision=ref.source_revision,
        packet_id=ref.packet_id,
        locator=ref.locator.model_dump(mode="json") if ref.locator is not None else None,
    )


def _projection_status(claim: SemanticClaimRecord) -> ProjectionStatus:
    if claim.projected:
        return "projected"
    reason = projection_ineligibility(claim)
    if reason == "predicate-not-projectable":
        return "not-projectable"
    return "withheld" if reason is not None else "not-projected"


def _withheld_reason(claim: SemanticClaimRecord) -> ProjectionIneligibility | None:
    reason = projection_ineligibility(claim)
    return None if claim.projected or reason == "predicate-not-projectable" else reason


def claim_view(
    claim: SemanticClaimRecord,
    evidence_by_id: Mapping[str, EvidenceRecord],
    *,
    policy_ref: str | None = None,
) -> SemanticClaimView:
    """Derive the view of one claim. Pure: the claim and evidence are not changed."""
    present = [evidence_by_id[ref] for ref in claim.evidence_refs if ref in evidence_by_id]
    missing = tuple(ref for ref in claim.evidence_refs if ref not in evidence_by_id)
    locations = tuple(
        sorted((_location(item) for item in present), key=lambda item: item.evidence_id)
    )
    return SemanticClaimView(
        claim_id=claim.claim_id,
        subject_id=claim.subject_id,
        subject_kind=subject_kind(claim.subject_id),
        predicate=claim.predicate,
        raw_value=claim.object,
        value_kind=_value_kind(claim.predicate),
        interpretation=predicate_interpretation(claim.predicate),
        definition_ref=predicate_definition(claim.predicate),
        support=claim.support,
        cardinality=claim.cardinality,
        authority=claim.authority,
        confidence=claim.confidence,
        conflict_status=claim.conflict_status,
        conflict_ids=claim.conflict_ids,
        source_assertion_ids=claim.source_assertion_ids,
        evidence_refs=claim.evidence_refs,
        source_locations=locations,
        missing_evidence_refs=missing,
        projection_status=_projection_status(claim),
        projection_withheld_reason=_withheld_reason(claim),
        projected_entity_ids=claim.projected_entity_ids,
        interpretation_policy_ref=policy_ref or interpretation_policy_ref(),
    )


#: One filter a query applies to a view.
_Check = Callable[[SemanticClaimView], bool]


@dataclass(frozen=True)
class ClaimQuery:
    """A bounded, deterministic filter over claim views. Every field narrows.

    ``None`` means "do not filter on this". String matches are exact; the only
    partial match is ``predicate_prefix``, which matches whole dot-separated
    segments, so ``meta.managed`` matches ``meta.managed.classification.injectable``
    and never ``meta.managedx.anything``.
    """

    subject_id: str | None = None
    subject_kind: str | None = None
    predicate: str | None = None
    predicate_prefix: str | None = None
    value: str | None = None
    interpretation: PredicateInterpretation | None = None
    conflict: ConflictFilter = "any"
    projection: ProjectionFilter = "any"
    source_path: str | None = None
    #: Only claims supported by at least this many distinct source locations.
    minimum_locations: int = 0
    limit: int = DEFAULT_QUERY_LIMIT

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= MAXIMUM_QUERY_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAXIMUM_QUERY_LIMIT}: {self.limit}")
        if self.minimum_locations < 0:
            raise ValueError("minimum_locations cannot be negative")
        if self.predicate_prefix is not None and not self.predicate_prefix.strip("."):
            raise ValueError("predicate_prefix must name at least one segment")

    def matches(self, view: SemanticClaimView) -> bool:
        """Return whether ``view`` satisfies every filter this query sets."""
        return all(check(view) for check in self._checks())

    def _checks(self) -> Iterable[_Check]:
        if self.subject_id is not None:
            yield lambda view: view.subject_id == self.subject_id
        if self.subject_kind is not None:
            yield lambda view: view.subject_kind == self.subject_kind
        if self.predicate is not None:
            yield lambda view: view.predicate == self.predicate
        if self.predicate_prefix is not None:
            prefix = self.predicate_prefix.rstrip(".")
            yield lambda view: view.predicate == prefix or view.predicate.startswith(f"{prefix}.")
        if self.value is not None:
            yield lambda view: view.raw_value == self.value
        if self.interpretation is not None:
            yield lambda view: view.interpretation == self.interpretation
        if self.conflict == "none":
            yield lambda view: view.conflict_status is ConflictStatus.none
        elif self.conflict == "conflicted":
            yield lambda view: view.conflict_status is not ConflictStatus.none
        if self.projection == "projected":
            yield lambda view: view.projection_status == "projected"
        elif self.projection == "unprojected":
            yield lambda view: view.projection_status != "projected"
        if self.source_path is not None:
            yield lambda view: any(
                location.source_path == self.source_path for location in view.source_locations
            )
        if self.minimum_locations:
            yield lambda view: _distinct_locations(view) >= self.minimum_locations


def _locator_key(location: SourceLocation) -> str | None:
    """A stable, comparable form of a structured locator, or ``None`` when absent."""
    return canonical_json(location.locator) if location.locator is not None else None


def _distinct_locations(view: SemanticClaimView) -> int:
    """Count distinct places a claim was read: path, line, and structured locator.

    The structured locator is part of the identity because non-line formats
    (PDF pages, slides, workbook cells, document blocks) carry no line number:
    without it, two places in one such file would collapse into one.
    """
    return len(
        {
            (location.source_path, location.line_number, _locator_key(location))
            for location in view.source_locations
        }
    )


class ClaimQueryResult(FrozenModel):
    """What a query matched, how many, and whether the bound truncated it."""

    total_matched: int
    returned: int
    truncated: bool
    claims: tuple[SemanticClaimView, ...]


class ClaimChange(FrozenModel):
    """One logical claim present in both snapshots whose reading differs."""

    claim_id: str
    before: SemanticClaimView
    after: SemanticClaimView
    changed_fields: tuple[str, ...]


class ClaimDifferential(FrozenModel):
    """Logical claims added, removed and re-read between two packet snapshots.

    Claim identity is the logical claim — subject, predicate, object — so the same
    statement in two snapshots is one claim even when its evidence moved.
    """

    added: tuple[SemanticClaimView, ...]
    removed: tuple[SemanticClaimView, ...]
    changed: tuple[ClaimChange, ...]


#: View fields compared by a differential. Evidence and assertion identities are
#: deliberately not compared: they name the packet that carried them, so two
#: independent compiles of the same source would differ on every claim. Where the
#: support was *read* is compared instead (see ``_support_signature``): a claim
#: whose support moved is a change a reader must see.
_DIFFERENTIAL_FIELDS: tuple[str, ...] = (
    "interpretation",
    "support",
    "cardinality",
    "authority",
    "confidence",
    "conflict_status",
    "conflict_ids",
    "projection_status",
    "projection_withheld_reason",
    "projected_entity_ids",
)


def _support_signature(
    view: SemanticClaimView,
) -> tuple[tuple[str | None, int | None, str | None, str | None, str | None], ...]:
    """Where a claim's support was read, independent of the packet that carried it."""
    return tuple(
        sorted(
            {
                (
                    location.source_path,
                    location.line_number,
                    _locator_key(location),
                    location.content_hash,
                    location.source_revision,
                )
                for location in view.source_locations
            },
            key=repr,
        )
    )


class SemanticClaimIndex:
    """An in-memory index of every claim view in one materialized packet.

    Built once per read; never persisted. Ordering is by ``claim_id`` throughout,
    so the same packet answers the same query with the same bytes.
    """

    def __init__(self, views: Iterable[SemanticClaimView]) -> None:
        self._views: tuple[SemanticClaimView, ...] = tuple(
            sorted(views, key=lambda item: item.claim_id)
        )
        self._by_id: dict[str, SemanticClaimView] = {view.claim_id: view for view in self._views}
        if len(self._by_id) != len(self._views):
            raise ValueError("a packet carries two claims with one claim_id")

    @classmethod
    def from_state(cls, state: TopologyState) -> SemanticClaimIndex:
        """Index every semantic claim in ``state`` with the evidence it cites."""
        evidence_by_id = {record.evidence_id: record for record in state.evidence}
        policy_ref = interpretation_policy_ref()
        return cls(
            claim_view(claim, evidence_by_id, policy_ref=policy_ref)
            for claim in state.semantic_claims
        )

    @property
    def views(self) -> tuple[SemanticClaimView, ...]:
        return self._views

    def get(self, claim_id: str) -> SemanticClaimView | None:
        return self._by_id.get(claim_id)

    def query(self, query: ClaimQuery) -> ClaimQueryResult:
        """Return the views ``query`` matches, bounded by ``query.limit``."""
        matched = [view for view in self._views if query.matches(view)]
        returned = tuple(matched[: query.limit])
        return ClaimQueryResult(
            total_matched=len(matched),
            returned=len(returned),
            truncated=len(matched) > len(returned),
            claims=returned,
        )

    def differential(
        self, later: SemanticClaimIndex, query: ClaimQuery | None = None
    ) -> ClaimDifferential:
        """Compare this snapshot with ``later``, optionally within one query's scope.

        The query's ``limit`` does not apply: a differential that silently dropped
        changes past a bound would report two different snapshots as closer than
        they are.
        """

        def scoped(index: SemanticClaimIndex) -> dict[str, SemanticClaimView]:
            return {
                view.claim_id: view for view in index.views if query is None or query.matches(view)
            }

        before, after = scoped(self), scoped(later)
        changed: list[ClaimChange] = []
        for claim_id in sorted(before.keys() & after.keys()):
            old, new = before[claim_id], after[claim_id]
            fields = tuple(
                name for name in _DIFFERENTIAL_FIELDS if getattr(old, name) != getattr(new, name)
            ) + (
                ("source_locations",) if _support_signature(old) != _support_signature(new) else ()
            )
            if fields:
                changed.append(
                    ClaimChange(claim_id=claim_id, before=old, after=new, changed_fields=fields)
                )
        return ClaimDifferential(
            added=tuple(after[claim_id] for claim_id in sorted(after.keys() - before.keys())),
            removed=tuple(before[claim_id] for claim_id in sorted(before.keys() - after.keys())),
            changed=tuple(changed),
        )
