"""Corpus Intelligence Packet v1 contract — the auxiliary corpus boundary.

A Repository Model Packet answers "what is in this one root, and what does it
say about itself". Corpus intelligence answers questions no single root can:
which byte-identical files live on two different disks, which documents look
like they belong to one body of work, how much test and CI evidence a candidate
carries, and which candidates a later reasoner should look at.

Those are different *kinds* of statement, and this is a separate packet because
of that rather than for tidiness. A repository-model assertion cites an exact
span in a hashed file and is source-authoritative. A topic candidate is the
output of a similarity profile: it is real evidence, it is worth carrying, and
it is not a fact about the corpus in the same sense. Folding derived and
candidate semantics into ``l9.repository-model`` would have made the two
indistinguishable at the point where topology decides what may become canonical
truth — and once a candidate has been admitted to a canonical domain, nothing
downstream can tell it was ever a candidate.

So the split is by epistemic class, and it is carried in the type system:

``document_work_signals``
    Source-backed. A decoder read a hashed document and a work signal cites the
    exact structured coordinate it was read at. These reconcile into semantic
    claims exactly like repository-model assertions do.

``exact_duplicate_relations``
    Deterministic. Byte equality, and nothing else, decided by content hash.

``readiness_evidence``
    Derived measurement. Counts of things observed, never a judgment about them.

``semantic_pair_relations``, ``topic_candidates``, ``project_candidates``,
``consolidation_candidates``
    Candidate analysis. Preserved as candidates, enriched with structural
    evidence, and never promoted into canonical edges.

``reasoning_candidates``
    Requests for future reasoning. Not conclusions at all.

Every artifact identity in every domain must resolve to an artifact carried by
one of the Repository Model Packets this packet names. A corpus intelligence
packet is an *analysis over* exactly those roots; it is not a second, competing
observation of them, and it may not introduce a subject they never saw.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.run.evidence import SourceLocator, utc_now

from .common import PacketLineage, PacketValidationRef, Producer, ProfileRef
from .refs import PacketRef

#: The packet type this module contracts.
CORPUS_INTELLIGENCE_PACKET_TYPE = "l9.corpus-intelligence"

#: 1.0.0 is the first corpus-intelligence contract.
CORPUS_INTELLIGENCE_PACKET_VERSION = "1.0.0"

#: Payload domains, in the order a reader meets them. Every one is serialized to
#: its own file and its own hash; an empty tuple means the producer found
#: nothing, which is a different statement from a domain that was never run.
#:
#: ``reasoning_evidence_pack_refs`` is optional to *populate* and mandatory to
#: *carry*. Leaving it off this tuple would have given it no payload file, and a
#: bundle round-trip would then have silently dropped whatever it held.
CORPUS_PAYLOAD_FIELDS: tuple[str, ...] = (
    "document_work_signals",
    "exact_duplicate_relations",
    "semantic_pair_relations",
    "topic_candidates",
    "project_candidates",
    "consolidation_candidates",
    "readiness_evidence",
    "reasoning_candidates",
    "reasoning_evidence_pack_refs",
)

#: How confident the producer's fusion profile was in a candidate relation.
#: Deliberately a class rather than a score: a number invites arithmetic across
#: candidates that the profile never claimed was meaningful.
ConfidenceClass = Literal["weak", "moderate", "strong"]

#: Candidate cluster kinds. Closed: topology never invents a fourth.
CandidateType = Literal["TOPIC_CANDIDATE", "PROJECT_CANDIDATE", "CONSOLIDATION_CANDIDATE"]

#: How a root's identity was established. A declared root was named by an
#: operator; an inferred root was discovered. The distinction is preserved
#: because an inferred identity is a weaker claim, and topology lowers its
#: authority accordingly rather than treating the two alike.
RootIdentityClass = Literal["declared", "inferred"]

#: Reasoning types the producer may recommend. Identical to the vocabulary
#: topology routes to, so an upstream recommendation and a topology decision are
#: directly comparable rather than needing a translation table.
UpstreamReasoningType = Literal[
    "NONE",
    "SAME_BODY_OF_WORK_ADJUDICATION",
    "PROJECT_IDENTITY_ADJUDICATION",
    "VERSION_EVOLUTION_ANALYSIS",
    "CONSOLIDATION_ANALYSIS",
    "SUPERSESSION_ANALYSIS",
    "CONFLICT_RESOLUTION_ANALYSIS",
]


class CorpusRootRef(FrozenModel):
    """One root of the corpus, bound to the exact packet that observed it."""

    root_id: str = Field(min_length=1)
    identity_class: RootIdentityClass
    source_revision: str
    #: The Repository Model Packet this root produced. Binding the packet rather
    #: than the root's content hash is what makes the corpus checkable: two runs
    #: over the same bytes that modelled them differently are not one corpus.
    repository_model_packet: PacketRef
    #: The repository the root's packet is about, when it names one.
    repository_id: str | None = None

    @model_validator(mode="after")
    def references_a_repository_model_packet(self) -> CorpusRootRef:
        if self.repository_model_packet.packet_type != "l9.repository-model":
            raise ValueError(
                "a corpus root must reference an l9.repository-model packet, got "
                f"{self.repository_model_packet.packet_type!r}"
            )
        return self


class CorpusCoverage(FrozenModel):
    """The corpus's own denominators.

    Carried so no count in any other domain can be read without its base. "Three
    project candidates" is a different claim over two hundred files than over two
    hundred thousand, and a different claim again when half the roots never
    observed at all.
    """

    root_count_requested: int = Field(ge=0)
    root_count_observed: int = Field(ge=0)
    root_count_failed: int = Field(ge=0)
    artifact_count: int = Field(ge=0)
    archive_count: int = Field(ge=0)
    archive_member_count: int = Field(ge=0)
    decoder_eligible_count: int = Field(ge=0)
    normalized_document_count: int = Field(ge=0)
    interpreted_artifact_count: int = Field(ge=0)
    unsupported_format_count: int = Field(ge=0)
    #: Artifacts with no content hash at all: unreadable, or over the budget.
    coverage_gap_count: int = Field(ge=0)


class CorpusDescriptor(FrozenModel):
    """What this packet is an analysis of, and under which analysis identity."""

    #: The operator's label for the corpus. A name, never an identity.
    corpus_id: str = Field(min_length=1)
    #: Identity of what the disks held. Excludes every analysis profile.
    corpus_source_snapshot_id: str = Field(min_length=1)
    #: Identity of what was concluded from them, and under which rules. Moves
    #: when a threshold or an embedding model moves; the source snapshot does not.
    corpus_analysis_id: str = Field(min_length=1)
    root_refs: tuple[CorpusRootRef, ...]
    coverage: CorpusCoverage

    @model_validator(mode="after")
    def root_identities_are_unique(self) -> CorpusDescriptor:
        seen = [root.root_id for root in self.root_refs]
        duplicates = sorted({value for value in seen if seen.count(value) > 1})
        if duplicates:
            raise ValueError(f"corpus roots must have unique identities: {duplicates}")
        return self


class CorpusAnalysisProfileRef(FrozenModel):
    """Identity of the profile a candidate domain was computed under.

    Changing a threshold changes which candidates exist. Binding the profile to
    every candidate is what lets topology say a candidate set moved because the
    rules moved, rather than because the corpus did.
    """

    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    profile_hash: str = Field(min_length=1)


class DocumentWorkSignal(FrozenModel):
    """One work signal a decoder read out of a structured document.

    This is the source-backed domain. It is treated exactly like a
    repository-model assertion downstream — same reconciliation engine, same
    conflict model — and differs only in carrying a structured locator instead
    of a line number, because the formats it comes from have no lines.
    """

    signal_id: str = Field(min_length=1)
    #: The artifact the signal was read from. Must resolve to an artifact
    #: carried by one of this packet's input Repository Model Packets.
    artifact_id: str = Field(min_length=1)
    #: The topology subject the claim is about. Usually the artifact's own
    #: repository; never a subject no input packet observed.
    subject_id: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object: str
    source_path: str = Field(min_length=1)
    #: Exactly where in the document this was read, in that format's own
    #: coordinate system. Required: a work signal that cannot say where it came
    #: from is not evidence this pipeline is willing to carry.
    locator: SourceLocator
    #: Digest of the *source document's* bytes, not of the decoded text and not
    #: of the corpus snapshot. A claim must stay bound to the bytes behind it.
    source_content_hash: str = Field(min_length=1)
    #: The decoded format, e.g. ``docx``. Used to refuse a fake line locator.
    document_format: str = Field(min_length=1)
    evidence_excerpt: str
    extractor_id: str = Field(min_length=1)
    decoder_id: str = Field(min_length=1)
    decoder_version: str = Field(min_length=1)
    evidence_class: Literal["declared", "observed"]
    authority: str = Field(min_length=1)
    confidence: str = Field(min_length=1)


class ExactDuplicateRelation(FrozenModel):
    """Byte identity between two artifacts, and nothing weaker.

    The one decidable relation in this packet. Two artifacts are related here if
    and only if their content hashes are equal — never because their names match,
    never because a similarity score was high.
    """

    relation_id: str = Field(min_length=1)
    duplicate_cluster_id: str = Field(min_length=1)
    artifact_a_id: str = Field(min_length=1)
    artifact_b_id: str = Field(min_length=1)
    #: The hash both endpoints carry. One field, because there is one hash: two
    #: differing hashes are not a duplicate relation, they are a contradiction.
    content_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def endpoints_are_distinct(self) -> ExactDuplicateRelation:
        if self.artifact_a_id == self.artifact_b_id:
            raise ValueError(
                f"an exact duplicate relation needs two artifacts: {self.artifact_a_id}"
            )
        return self


class PairMethodScore(FrozenModel):
    """One scored similarity method behind a candidate relation."""

    method: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)


class SemanticPairRelation(FrozenModel):
    """A candidate relation between two artifacts. Never a canonical edge.

    Whatever combination of lexical overlap, declared identifiers, and embedding
    similarity produced it, this remains a proposal. It informs candidate
    clusters and it may raise or lower a reasoning recommendation. It does not
    become ``DEPENDS_ON``, it does not become ``DUPLICATE_OF``, and it never
    enters canonical impact.
    """

    relation_id: str = Field(min_length=1)
    source_artifact_id: str = Field(min_length=1)
    target_artifact_id: str = Field(min_length=1)
    methods: tuple[str, ...] = ()
    method_scores: tuple[PairMethodScore, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    confidence_class: ConfidenceClass
    analysis_profile: CorpusAnalysisProfileRef
    #: The producer's own identity for this relation, preserved so a topology
    #: candidate can be traced back to the upstream record that proposed it.
    upstream_candidate_id: str | None = None

    @model_validator(mode="after")
    def endpoints_are_distinct(self) -> SemanticPairRelation:
        if self.source_artifact_id == self.target_artifact_id:
            raise ValueError(
                f"a semantic pair relation needs two artifacts: {self.source_artifact_id}"
            )
        return self


class CandidateCluster(FrozenModel):
    """A group of artifacts some analysis profile proposed belong together.

    Topic, project, and consolidation candidates share this shape because they
    share an epistemic class. What separates them is ``candidate_type`` and the
    admission rule behind it, both of which are the producer's; what they have in
    common is that none of them is a decided fact.
    """

    candidate_id: str = Field(min_length=1)
    candidate_type: CandidateType
    member_artifact_ids: tuple[str, ...]
    supporting_relation_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    confidence_class: ConfidenceClass
    #: Named contradictions inside the group: conflicting declared status, more
    #: than one project name, an ambiguous supersession. Carried rather than
    #: resolved.
    ambiguity_flags: tuple[str, ...] = ()
    cross_root: bool = False
    cross_archive: bool = False
    analysis_profile: CorpusAnalysisProfileRef
    upstream_candidate_id: str | None = None

    @model_validator(mode="after")
    def names_at_least_one_member(self) -> CandidateCluster:
        if not self.member_artifact_ids:
            raise ValueError(f"candidate {self.candidate_id} names no members")
        return self


class ReadinessEvidence(FrozenModel):
    """Counts of things observed for one subject. Never a score.

    Every field is a count of artifacts or declarations that were actually seen.
    None is combined with any other, weighted, or projected forward. A strategy
    layer that wants a ratio may divide two of these and will then own the ratio;
    this packet does not compute one, and the topology domain it lowers into
    forbids the fields such a ratio would be recorded in.
    """

    readiness_id: str = Field(min_length=1)
    #: The candidate or topology entity these counts are about.
    subject_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)

    source_artifact_count: int = Field(default=0, ge=0)
    test_artifact_count: int = Field(default=0, ge=0)
    build_manifest_count: int = Field(default=0, ge=0)
    ci_definition_count: int = Field(default=0, ge=0)
    deployment_definition_count: int = Field(default=0, ge=0)
    specification_count: int = Field(default=0, ge=0)
    documentation_count: int = Field(default=0, ge=0)

    plan_count: int = Field(default=0, ge=0)
    roadmap_count: int = Field(default=0, ge=0)
    wip_count: int = Field(default=0, ge=0)
    draft_count: int = Field(default=0, ge=0)
    blocked_count: int = Field(default=0, ge=0)

    open_task_count: int = Field(default=0, ge=0)
    completed_task_count: int = Field(default=0, ge=0)
    milestone_count: int = Field(default=0, ge=0)

    exact_duplicate_count: int = Field(default=0, ge=0)
    near_duplicate_count: int = Field(default=0, ge=0)
    consolidation_candidate_count: int = Field(default=0, ge=0)

    #: Members whose bytes were never read, or never decoded. Carried beside the
    #: counts so thin evidence is not mistaken for a thin body of work.
    coverage_gap_count: int = Field(default=0, ge=0)
    evidence_refs: tuple[str, ...] = ()


class ReasoningCandidateRequest(FrozenModel):
    """The producer's recommendation that a candidate deserves reasoning.

    A recommendation, not an instruction. Topology holds structural evidence the
    producer did not, so it makes the final routing decision and records both.
    """

    reasoning_candidate_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    recommended_reasoning_type: UpstreamReasoningType
    #: Why the producer routed it this way. Present even for ``NONE``.
    reason: str = ""
    member_artifact_ids: tuple[str, ...] = ()
    evidence_pack_ref: str | None = None


class CorpusIntelligencePayload(FrozenModel):
    """Every domain a corpus intelligence packet carries."""

    document_work_signals: tuple[DocumentWorkSignal, ...] = ()
    exact_duplicate_relations: tuple[ExactDuplicateRelation, ...] = ()
    semantic_pair_relations: tuple[SemanticPairRelation, ...] = ()
    topic_candidates: tuple[CandidateCluster, ...] = ()
    project_candidates: tuple[CandidateCluster, ...] = ()
    consolidation_candidates: tuple[CandidateCluster, ...] = ()
    readiness_evidence: tuple[ReadinessEvidence, ...] = ()
    reasoning_candidates: tuple[ReasoningCandidateRequest, ...] = ()
    #: Bounded evidence packs the producer prepared for a later reasoner.
    #: References only: topology never reads a pack's contents, because doing so
    #: would make a bounded excerpt into a second source of corpus truth.
    reasoning_evidence_pack_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def candidate_domains_carry_their_own_type(self) -> CorpusIntelligencePayload:
        """Refuse a candidate filed under the wrong domain.

        The three candidate domains are separate fields *and* carry a type tag.
        Without this check the two could disagree, and a consolidation candidate
        sitting in ``topic_candidates`` would be enriched, reported, and routed
        as a topic candidate while claiming to be something else.
        """
        expected: tuple[tuple[str, str], ...] = (
            ("topic_candidates", "TOPIC_CANDIDATE"),
            ("project_candidates", "PROJECT_CANDIDATE"),
            ("consolidation_candidates", "CONSOLIDATION_CANDIDATE"),
        )
        for field_name, candidate_type in expected:
            for candidate in getattr(self, field_name):
                if candidate.candidate_type != candidate_type:
                    raise ValueError(
                        f"{field_name} carries {candidate.candidate_id} declared as "
                        f"{candidate.candidate_type!r}, expected {candidate_type!r}"
                    )
        return self


class CorpusIntelligenceInputs(FrozenModel):
    """The Repository Model Packets this analysis was computed over."""

    repository_model_packets: tuple[PacketRef, ...]

    @model_validator(mode="after")
    def inputs_are_repository_model_packets(self) -> CorpusIntelligenceInputs:
        wrong = sorted(
            {
                reference.packet_type
                for reference in self.repository_model_packets
                if reference.packet_type != "l9.repository-model"
            }
        )
        if wrong:
            raise ValueError(
                f"corpus intelligence inputs must be repository-model packets: {wrong}"
            )
        return self


class CorpusIntelligencePacket(FrozenModel):
    """The auxiliary corpus-analysis packet topology accepts beside RMPs."""

    packet_type: Literal["l9.corpus-intelligence"] = "l9.corpus-intelligence"
    packet_version: str = CORPUS_INTELLIGENCE_PACKET_VERSION
    packet_id: str
    producer: Producer
    profile: ProfileRef
    inputs: CorpusIntelligenceInputs
    corpus: CorpusDescriptor
    validation: PacketValidationRef
    schema_hash: str
    semantic_hash: str
    artifact_hash: str | None = None
    payload_refs: dict[str, str] = Field(default_factory=dict)
    payload_hashes: dict[str, str] = Field(default_factory=dict)
    payload: CorpusIntelligencePayload | None = None
    lineage: PacketLineage = Field(default_factory=PacketLineage)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def roots_reference_declared_inputs(self) -> CorpusIntelligencePacket:
        """Every root's packet must be one of the packets this analysis names.

        A root bound to a packet outside ``inputs`` would mean the corpus was
        computed over something the consumer is not being shown, which makes the
        whole set of derived counts uncheckable.
        """
        declared = {ref.packet_id for ref in self.inputs.repository_model_packets}
        missing = sorted(
            {
                root.repository_model_packet.packet_id
                for root in self.corpus.root_refs
                if root.repository_model_packet.packet_id not in declared
            }
        )
        if missing:
            raise ValueError(
                f"corpus roots reference repository-model packets absent from inputs: {missing}"
            )
        return self


def corpus_payload_path(field: str) -> str:
    if field not in CORPUS_PAYLOAD_FIELDS:
        raise ValueError(f"unsupported corpus payload field: {field}")
    return f"payload/{field.replace('_', '-')}.json"


def corpus_payload_refs() -> dict[str, str]:
    return {field: corpus_payload_path(field) for field in CORPUS_PAYLOAD_FIELDS}


def corpus_intelligence_semantic_view(packet: CorpusIntelligencePacket) -> dict[str, object]:
    """Return exactly the fields that define immutable corpus-analysis meaning.

    Absent by construction: ``packet_id``, ``semantic_hash``, ``artifact_hash``,
    ``created_at``, and the whole ``payload`` — which is hashed through
    ``payload_hashes`` rather than serialized twice into two identities that
    could drift.
    """
    return {
        "packet_type": packet.packet_type,
        "packet_version": packet.packet_version,
        "producer": packet.producer,
        "profile": packet.profile,
        "inputs": packet.inputs,
        "corpus": packet.corpus,
        "schema_hash": packet.schema_hash,
        "payload_refs": packet.payload_refs,
        "payload_hashes": packet.payload_hashes,
        "lineage": packet.lineage,
    }
