"""Project explicit work relations into canonical edges, resolving exactly or not at all.

A document that says "depends on `engine/main.py`" has stated a real
relationship. Turning it into an edge needs an answer to one question the
document did not give: *which* artifact is `engine/main.py`?

Everything here follows from refusing to guess that answer. Resolution is by
exact artifact identity, then by exact portable source path, then by exact
virtual archive path — and each of the path forms resolves only when it is
*unique* across the corpus. Two files named `README.md` make a reference to
`README.md` ambiguous, and an ambiguous reference is no evidence at all: it
becomes an unknown naming both possibilities, plus an external reference node
that preserves what the document actually said.

The forbidden shortcuts are absent by construction rather than by review:

* no fuzzy or nearest-match filename resolution — only exact keys are indexed;
* no embedding or similarity input — this module imports no candidate domain;
* no membership inference — being in the same project candidate is not evidence
  that a reference means a particular member, so candidate clusters are not
  consulted here at all.

An unresolved target still produces an edge. Dropping it would lose the fact
that the document declared a dependency, which is the strongest part of the
signal; what the edge points at is an explicitly-labelled external reference
node, so a reader of the graph alone can see the endpoint was never observed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from l9_constellation_topology.domain.artifact import ArtifactRecord
from l9_constellation_topology.domain.assessment import UnknownRecord
from l9_constellation_topology.domain.claim import SemanticClaimRecord
from l9_constellation_topology.domain.edge import Direction, EdgeRecord, EdgeType, GraphRecord
from l9_constellation_topology.run.evidence import stable_id

#: Prefix for a target a document named that this compile could not resolve to a
#: single observed artifact. Deliberately not ``artifact:``: the whole point is
#: that a reader must be able to tell this endpoint was never observed.
WORK_REFERENCE_PREFIX = "work-reference"

#: Separator the producer uses between an archive and a member inside it.
ARCHIVE_MEMBER_SEPARATOR = "!/"

#: Reason recorded on the unknown raised for an ambiguous target.
AMBIGUOUS_TARGET_REASON = (
    "an explicit work relation named a target that matches more than one observed "
    "artifact, so it was preserved as an external reference rather than resolved to "
    "one of them by guessing"
)

#: How each work predicate projects. ``reverse`` means the edge is emitted from
#: object to subject, because the taxonomy defines the relation in that
#: direction: "A superseded_by B" is the edge "B SUPERSEDES A", and inverting the
#: meaning to keep the subject on the left would state the opposite fact.
_WORK_EDGE_PROJECTIONS: dict[str, tuple[EdgeType, bool]] = {
    "work.depends_on": (EdgeType.depends_on, False),
    "work.blocked_by": (EdgeType.blocked_by, False),
    "work.references": (EdgeType.references, False),
    "work.supersedes": (EdgeType.supersedes, False),
    "work.superseded_by": (EdgeType.supersedes, True),
}

#: Predicates this module projects. Derived from the table rather than restated
#: beside it, so the set a reader consults and the set applied cannot drift.
WORK_RELATION_PREDICATES: frozenset[str] = frozenset(_WORK_EDGE_PROJECTIONS)


@dataclass(frozen=True)
class WorkTargetIndex:
    """Exact-match lookups from what a document can write to what was observed.

    Every index is exact. There is no normalization beyond the producer's own
    portable-path form, and no fallback that relaxes the match, because each
    relaxation is a place a wrong answer could be produced confidently.
    """

    #: Artifact identity to itself. A document that names an artifact id is rare
    #: and unambiguous.
    by_artifact_id: frozenset[str] = frozenset()
    #: Exact portable source path to every artifact carrying it. A list rather
    #: than a single value: two roots can hold the same relative path, and that
    #: is precisely the ambiguity that must not resolve.
    by_source_path: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: Exact ``archive.zip!/member`` locator to the artifacts carrying it.
    by_archive_path: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @classmethod
    def build(cls, artifacts: tuple[ArtifactRecord, ...]) -> WorkTargetIndex:
        by_path: dict[str, list[str]] = {}
        by_archive: dict[str, list[str]] = {}
        for artifact in artifacts:
            path = artifact.source_path
            by_path.setdefault(path, []).append(artifact.artifact_id)
            if ARCHIVE_MEMBER_SEPARATOR in path:
                by_archive.setdefault(path, []).append(artifact.artifact_id)
        return cls(
            by_artifact_id=frozenset(artifact.artifact_id for artifact in artifacts),
            by_source_path={key: tuple(sorted(value)) for key, value in sorted(by_path.items())},
            by_archive_path={
                key: tuple(sorted(value)) for key, value in sorted(by_archive.items())
            },
        )

    def resolve(self, target: str) -> tuple[str | None, tuple[str, ...]]:
        """Return the resolved artifact and every candidate that matched.

        ``(None, ())`` means nothing matched — free text, or a file this compile
        never saw. ``(None, (a, b))`` means the target was genuinely ambiguous.
        Only ``(artifact_id, (artifact_id,))`` is a resolution.
        """
        if target in self.by_artifact_id:
            return target, (target,)
        for index in (self.by_archive_path, self.by_source_path):
            matches = index.get(target, ())
            if len(matches) == 1:
                return matches[0], matches
            if matches:
                return None, matches
        return None, ()


@dataclass(frozen=True)
class WorkProjection:
    """Everything explicit work claims projected."""

    edges: tuple[EdgeRecord, ...] = ()
    nodes: tuple[GraphRecord, ...] = ()
    unknowns: tuple[UnknownRecord, ...] = ()
    #: ``claim_id`` -> the topology entities that claim produced.
    entities_by_claim: dict[str, tuple[str, ...]] = field(default_factory=dict)


def _external_target_id(target: str) -> str:
    """Return a stable identity for a target that was never observed.

    Hashed rather than interpolated: a raw target can be free prose of any
    length, containing anything, and an identity built by concatenation would be
    unbounded and could collide with a real path.
    """
    return f"{WORK_REFERENCE_PREFIX}:{stable_id('target', {'target': target}).split(':', 1)[1]}"


def _edge(
    source_id: str,
    target_id: str,
    edge_type: EdgeType,
    claim: SemanticClaimRecord,
    properties: dict[str, object],
) -> EdgeRecord:
    identity = {
        "source_id": source_id,
        "target_id": target_id,
        "edge_type": edge_type.value,
        "properties": properties,
    }
    return EdgeRecord(
        edge_id=stable_id("edge", identity),
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        direction=Direction.outbound,
        properties=properties,
        evidence_refs=claim.evidence_refs,
        confidence=claim.confidence,
    )


def _external_target(
    claim: SemanticClaimRecord, target_id: str, matches: tuple[str, ...], resolution: str
) -> GraphRecord:
    """Return the node standing in for a target this compile did not resolve."""
    return GraphRecord(
        record_type="node",
        label="WorkReference",
        entity_id=target_id,
        properties={
            "reference": claim.object,
            "observed_in_corpus": False,
            "resolution": resolution,
            # Named so a reader can see what the ambiguity was between, without
            # this being taken as a resolution.
            "ambiguous_matches": list(matches),
            "projected_from_claim_id": claim.claim_id,
        },
        evidence_refs=claim.evidence_refs,
        confidence=claim.confidence,
    )


def _ambiguous_unknown(claim: SemanticClaimRecord, matches: tuple[str, ...]) -> UnknownRecord:
    """Return the unknown raised for a target that matched several artifacts."""
    return UnknownRecord(
        unknown_id=stable_id(
            "unknown",
            {
                "subject_id": claim.subject_id,
                "field": claim.predicate,
                "values": tuple(sorted(matches)),
                "target": claim.object,
            },
        ),
        subject_id=claim.subject_id,
        field=claim.predicate,
        reason=AMBIGUOUS_TARGET_REASON,
        evidence_refs=claim.evidence_refs,
    )


def _relation_edge(
    claim: SemanticClaimRecord,
    target_id: str,
    edge_type: EdgeType,
    reverse: bool,
    resolution: str,
) -> EdgeRecord:
    """Return the edge one work claim projects, in the taxonomy's direction.

    ``reverse`` emits from object to subject, because the taxonomy defines the
    relation that way: "A superseded_by B" is the edge "B SUPERSEDES A", and
    keeping the subject on the left would state the opposite fact.
    """
    properties: dict[str, object] = {
        "projected_from_claim_id": claim.claim_id,
        "assertion_predicate": claim.predicate,
        "assertion_object": claim.object,
        "target_resolution": resolution,
        "declared_by": claim.subject_id,
    }
    source, target = (target_id, claim.subject_id) if reverse else (claim.subject_id, target_id)
    return _edge(source, target, edge_type, claim, properties)


def project_work_relations(
    claims: tuple[SemanticClaimRecord, ...],
    artifacts: tuple[ArtifactRecord, ...],
) -> WorkProjection:
    """Project every explicit work relation claim into a canonical edge."""
    index = WorkTargetIndex.build(artifacts)
    edges: dict[str, EdgeRecord] = {}
    nodes: dict[str, GraphRecord] = {}
    unknowns: dict[str, UnknownRecord] = {}
    # Accumulated as sets and sorted once at the end. Sorting into a tuple on
    # every iteration only to re-set it on the next was doing the same work
    # twice and reading as though order mattered mid-loop, which it does not.
    produced_by_claim: dict[str, set[str]] = {}

    for claim in sorted(claims, key=lambda item: item.claim_id):
        projection = _WORK_EDGE_PROJECTIONS.get(claim.predicate)
        if projection is None:
            continue
        edge_type, reverse = projection
        resolved, matches = index.resolve(claim.object)

        if resolved is not None:
            target_id, resolution = resolved, "exact-artifact"
        else:
            target_id = _external_target_id(claim.object)
            resolution = "ambiguous" if matches else "unresolved"
            nodes.setdefault(target_id, _external_target(claim, target_id, matches, resolution))
            if matches:
                unknown = _ambiguous_unknown(claim, matches)
                unknowns.setdefault(unknown.unknown_id, unknown)

        edge = _relation_edge(claim, target_id, edge_type, reverse, resolution)
        edges[edge.edge_id] = edge
        produced = produced_by_claim.setdefault(claim.claim_id, set())
        produced.add(edge.edge_id)
        if resolved is None:
            # The external endpoint is an entity this claim produced too, and
            # naming it is what lets a reader trace an unresolved target back.
            produced.add(target_id)

    return WorkProjection(
        edges=tuple(sorted(edges.values(), key=lambda item: item.edge_id)),
        nodes=tuple(sorted(nodes.values(), key=lambda item: item.entity_id)),
        unknowns=tuple(sorted(unknowns.values(), key=lambda item: item.unknown_id)),
        entities_by_claim={
            claim_id: tuple(sorted(produced))
            for claim_id, produced in sorted(produced_by_claim.items())
        },
    )
