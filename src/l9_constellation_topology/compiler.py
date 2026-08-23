"""Deterministic packet-native topology compiler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from l9_constellation_topology.config import ResolvedConfiguration
from l9_constellation_topology.domain import TopologyState
from l9_constellation_topology.domain.edge import (
    EDGE_TAXONOMY_VERSION,
    edge_taxonomy_hash,
)
from l9_constellation_topology.io import CommitReceipt, OutputSink, RenderedArtifact, WriteIntent
from l9_constellation_topology.packets import (
    PacketLineage,
    PacketRef,
    PacketValidationRef,
    Producer,
    ProfileRef,
    TopologyInputs,
    TopologyPacket,
    ValidationReceipt,
)
from l9_constellation_topology.packets.assertion_evidence import assertion_semantic_inputs
from l9_constellation_topology.packets.bundle import build_topology_bundle_artifacts
from l9_constellation_topology.packets.corpus_bundle import (
    CorpusIntelligenceBundle,
    load_corpus_intelligence_bundle,
)
from l9_constellation_topology.packets.corpus_evidence import (
    corpus_evidence_by_subject,
    corpus_scope_evidence_records,
    duplicate_evidence_by_relation,
    duplicate_evidence_records,
)
from l9_constellation_topology.packets.corpus_intelligence import CorpusIntelligencePacket
from l9_constellation_topology.packets.corpus_validator import (
    validate_corpus_intelligence_packet,
)
from l9_constellation_topology.packets.document_signal_evidence import (
    signal_evidence_records,
    signal_semantic_inputs,
)
from l9_constellation_topology.packets.loader import (
    RepositoryModelBundle,
    load_repository_model_bundle,
)
from l9_constellation_topology.packets.payloads import (
    topology_payload_hashes,
    topology_payload_refs,
)
from l9_constellation_topology.packets.repository_model import RepositoryModelPacket
from l9_constellation_topology.packets.topology_packet import (
    MaterializedTopology,
    calculate_topology_semantic_hash,
)
from l9_constellation_topology.reconciliation import (
    PREDICATE_POLICY_VERSION,
    RECONCILIATION_POLICY_VERSION,
    predicate_policy_hash,
    reconciliation_policy_hash,
)
from l9_constellation_topology.run import artifact_hash, canonical_bytes, semantic_hash
from l9_constellation_topology.stages import aggregate_capabilities, aggregate_repositories
from l9_constellation_topology.stages.assess_impact import run as assess_impact
from l9_constellation_topology.stages.assess_maturity import run as assess_maturity
from l9_constellation_topology.stages.assess_risk import run as assess_risk
from l9_constellation_topology.stages.build_graph import run as build_graph
from l9_constellation_topology.stages.classify_roles import run as classify_roles
from l9_constellation_topology.stages.derive_unknowns import run as derive_unknowns
from l9_constellation_topology.stages.ingest_packets import adapt_packets
from l9_constellation_topology.stages.normalize_models import run as normalize_models
from l9_constellation_topology.stages.reconcile_assertions import run as reconcile_assertions
from l9_constellation_topology.stages.reconcile_evidence import run as reconcile_evidence
from l9_constellation_topology.stages.resolve_config import run as resolve_config
from l9_constellation_topology.stages.validate_topology import run as validate_topology
from l9_constellation_topology.topology.candidates import (
    candidate_graph_records,
    compile_candidate_clusters,
    compile_candidate_relations,
)
from l9_constellation_topology.topology.capability_builder import build_capabilities
from l9_constellation_topology.topology.claim_projection import (
    apply_projection,
    project_claims,
)
from l9_constellation_topology.topology.corpus_model import (
    compile_corpus_scope,
    corpus_scope_graph,
    root_by_artifact,
)
from l9_constellation_topology.topology.duplicates import build_duplicate_edges
from l9_constellation_topology.topology.flow_builder import build_flows
from l9_constellation_topology.topology.readiness import (
    compile_readiness_evidence,
    readiness_by_subject,
)
from l9_constellation_topology.topology.reasoning_router import route_reasoning_candidates
from l9_constellation_topology.topology.work_projection import project_work_relations

COMPILER_NAME = "l9-constellation-topology"
COMPILER_VERSION = "2.0.0"

#: The ``created_at`` stamped into a canonical compile.
#:
#: Canonical compilation must be byte-reproducible: the same semantic inputs
#: must produce the same emitted bytes and therefore the same ``artifact_hash``.
#: Reading the wall clock here would break that for a value that carries no
#: semantic meaning, so canonical compiles stamp a fixed, obviously synthetic
#: instant instead. Real execution time belongs in operational and validation
#: receipts, which record it in their own right.
#:
#: A caller may still inject a deliberate ``created_at``. That changes the
#: emitted packet bytes and so must change ``artifact_hash``, while leaving
#: ``semantic_hash`` untouched — ``created_at`` is outside the semantic view.
CANONICAL_CREATED_AT = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class CompilationResult:
    materialized: MaterializedTopology
    validation_receipt: ValidationReceipt
    input_bundles: tuple[RepositoryModelBundle, ...]
    configuration: ResolvedConfiguration
    artifacts: tuple[RenderedArtifact, ...]
    #: Defaults to empty, so a compile with no corpus input constructs exactly as
    #: it did before this domain existed.
    corpus_bundles: tuple[CorpusIntelligenceBundle, ...] = ()


class TopologyCompilationError(RuntimeError):
    def __init__(self, message: str, receipt: ValidationReceipt) -> None:
        super().__init__(message)
        self.receipt = receipt


def _packet_ref(bundle: RepositoryModelBundle) -> PacketRef:
    packet = bundle.packet
    return PacketRef(
        packet_id=packet.packet_id,
        packet_type=packet.packet_type,
        packet_version=packet.packet_version,
        uri=f"packet://{packet.packet_id}",
        semantic_hash=packet.semantic_hash,
        artifact_hash=packet.artifact_hash,
        validation_status=packet.validation.status,
        subject_id=packet.subject.repository_id,
        source_revision=packet.source_snapshot.revision,
    )


def _corpus_packet_ref(bundle: CorpusIntelligenceBundle) -> PacketRef:
    packet = bundle.packet
    return PacketRef(
        packet_id=packet.packet_id,
        packet_type=packet.packet_type,
        packet_version=packet.packet_version,
        uri=f"packet://{packet.packet_id}",
        semantic_hash=packet.semantic_hash,
        artifact_hash=packet.artifact_hash,
        validation_status=packet.validation.status,
        subject_id=packet.corpus.corpus_id,
        source_revision=packet.corpus.corpus_source_snapshot_id,
    )


def _check_corpus_inputs(
    corpus_packets: tuple[CorpusIntelligencePacket, ...],
    packets: tuple[RepositoryModelPacket, ...],
) -> None:
    """Refuse a corpus packet analysing packets this compile was not given.

    A corpus packet may cover a *subset* of the compile's Repository Model
    Packets — analysing two roots of a three-root compile is a coherent thing to
    do. It may not name one the compile does not have: those artifacts would be
    unresolvable, and every count drawn over them would be computed against a
    denominator the consumer cannot see.
    """
    available = {packet.packet_id for packet in packets}
    for corpus in corpus_packets:
        declared = {ref.packet_id for ref in corpus.inputs.repository_model_packets}
        missing = sorted(declared - available)
        if missing:
            raise ValueError(
                f"corpus intelligence packet {corpus.packet_id} analyses repository-model "
                f"packets absent from this compile: {', '.join(missing)}"
            )
        # Validated against exactly the packets it names, not the whole compile,
        # so a subset-scoped corpus is not reported as missing roots.
        validate_corpus_intelligence_packet(
            corpus,
            tuple(packet for packet in packets if packet.packet_id in declared),
        )


def _policy_hashes(configuration: ResolvedConfiguration) -> dict[str, str]:
    """Return every policy whose meaning can change compiled topology truth.

    ``reconciliation`` is compiler-owned rather than a checked-in profile, but it
    decides what counts as an aggregate versus a contradiction. Binding it here
    puts it inside the topology semantic view.
    """
    return {
        "topology": semantic_hash(configuration.topology_profile),
        "risk": semantic_hash(configuration.risk_profile),
        "maturity": semantic_hash(configuration.maturity_profile),
        "report": semantic_hash(configuration.report_profile),
        "packet": semantic_hash(configuration.packet_profile),
        "output": semantic_hash(configuration.output_policy),
        "reconciliation": reconciliation_policy_hash(),
        # The edge taxonomy decides what a relation means and which relations
        # canonical impact traverses. Adding DUPLICATE_OF changed both, so the
        # taxonomy belongs inside the topology semantic view: a packet compiled
        # when byte identity was a dependency hop must not share identity with
        # one compiled after it stopped being one.
        "edge_taxonomy": edge_taxonomy_hash(),
        # The predicate registry decides whether two assertions on one subject
        # aggregate, contradict, or stay unresolved, and which claims project
        # into relations. That is compiled topology truth, so it belongs inside
        # the topology semantic view alongside the other reconciliation rules.
        "assertion_predicates": predicate_policy_hash(),
    }


def calculate_idempotency_key(
    input_refs: tuple[PacketRef, ...],
    configuration: ResolvedConfiguration,
    *,
    compiler_build_identity: str | None = None,
    adapter_mode: str = "canonical",
) -> str:
    """Hash every semantic input capable of changing the compiled packet.

    ``configuration.profile_hash`` covers topology, risk, maturity, report, packet,
    and output profiles. The build identity binds reuse to the exact compiler source
    revision when supplied by the stage dispatch.
    """

    identity = {
        "packet_type": "l9.topology",
        "packet_version": "1.0.0",
        "input_semantic_hashes": tuple(sorted(ref.semantic_hash for ref in input_refs)),
        "compiler_name": COMPILER_NAME,
        "compiler_version": COMPILER_VERSION,
        "compiler_build_identity": compiler_build_identity or f"version:{COMPILER_VERSION}",
        "configuration_profile_hash": configuration.profile_hash,
        "schema_contract_hash": configuration.schema_contract_hash,
        "active_contract_versions": configuration.active_contract_versions,
        "reconciliation_policy_version": RECONCILIATION_POLICY_VERSION,
        "reconciliation_policy_hash": reconciliation_policy_hash(),
        "predicate_policy_version": PREDICATE_POLICY_VERSION,
        "predicate_policy_hash": predicate_policy_hash(),
        "edge_taxonomy_version": EDGE_TAXONOMY_VERSION,
        "edge_taxonomy_hash": edge_taxonomy_hash(),
        "adapter_mode": adapter_mode,
    }
    return semantic_hash(identity)


def compile_topology(
    repository_root: Path,
    input_bundle_paths: tuple[Path, ...],
    *,
    corpus_bundle_paths: tuple[Path, ...] = (),
    created_at: datetime | None = None,
) -> CompilationResult:
    """Compile a Topology Packet from repository observation and corpus analysis.

    ``corpus_bundle_paths`` is optional and empty by default, so a compile with
    no corpus input behaves exactly as it did before this domain existed: the
    corpus, candidate, readiness, and reasoning payloads come out empty, and
    nothing else moves.
    """
    if not input_bundle_paths:
        raise ValueError("at least one Repository Model Packet bundle is required")
    configuration = resolve_config(repository_root)
    bundles = tuple(load_repository_model_bundle(path) for path in input_bundle_paths)
    packets = tuple(bundle.packet for bundle in bundles)
    corpus_bundles = tuple(load_corpus_intelligence_bundle(path) for path in corpus_bundle_paths)
    corpus_packets = tuple(bundle.packet for bundle in corpus_bundles)
    # Fail closed before any compilation work: a corpus packet whose identities
    # do not resolve must not produce a partial topology that looks complete.
    _check_corpus_inputs(corpus_packets, packets)

    normalized = normalize_models(adapt_packets(packets))

    # Document work signals become evidence at the packet boundary, exactly as
    # repository-model assertions do, and join the same pool.
    # Every corpus fact gets a first-class evidence record, not just the work
    # signals: a DUPLICATE_OF edge asserting byte identity has to be able to name
    # the hash behind it, and a root has to name the packet that observed it.
    signal_evidence = tuple(
        record
        for packet in corpus_packets
        for record in (
            *signal_evidence_records(packet),
            *duplicate_evidence_records(packet),
            *corpus_scope_evidence_records(packet),
        )
    )
    evidence, evidence_conflicts, evidence_unknowns = reconcile_evidence(
        normalized.evidence + signal_evidence
    )
    declared_unknowns = derive_unknowns(normalized.diagnostics)
    repositories, repository_conflicts, repository_unknowns = aggregate_repositories.run(
        normalized.repositories
    )
    repositories = classify_roles(
        repositories,
        {
            str(key): tuple(str(value) for value in values)
            for key, values in configuration.topology_profile.get("role_taxonomy", {}).items()
        },
    )
    # One reconciliation over both producers. A source assertion and a document
    # work signal about the same subject and predicate land in one group, so a
    # `.docx` saying `Complete` beside a `.md` saying `WIP` is reported as the
    # conflict it is rather than as two self-consistent facts.
    statements = assertion_semantic_inputs(normalized.assertions) + tuple(
        statement for packet in corpus_packets for statement in signal_semantic_inputs(packet)
    )
    claims, claim_conflicts, claim_unknowns, claim_diagnostics = reconcile_assertions(
        statements, evidence
    )
    projection = project_claims(claims)
    work = project_work_relations(claims, normalized.artifacts)
    claims = apply_projection(claims, projection)

    capabilities = build_capabilities(
        repositories,
        normalized.artifacts,
        normalized.capabilities,
    )
    capabilities, capability_conflicts = aggregate_capabilities.run(
        capabilities + projection.capabilities
    )

    # Corpus scope, above repositories. Records are stamped with the evidence
    # built for them above, so the corpus and its roots cite their provenance
    # like every other canonical record does.
    corpus_records, root_records = compile_corpus_scope(corpus_packets)
    scope_evidence = corpus_evidence_by_subject(corpus_packets)
    corpus_records = tuple(
        record.model_copy(update={"evidence_refs": scope_evidence.get(record.corpus_id, ())})
        for record in corpus_records
    )
    root_records = tuple(
        record.model_copy(update={"evidence_refs": scope_evidence.get(record.root_id, ())})
        for record in root_records
    )
    corpus_nodes, corpus_edges = corpus_scope_graph(corpus_records, root_records)

    # Byte identity. Sourced only from `exact_duplicate_relations`, so no
    # similarity score can reach this edge type.
    duplicate_evidence_index: dict[str, tuple[str, ...]] = {}
    for corpus_packet in corpus_packets:
        duplicate_evidence_index.update(duplicate_evidence_by_relation(corpus_packet))
    duplicate_edges = build_duplicate_edges(
        tuple(
            relation
            for packet in corpus_packets
            if packet.payload is not None
            for relation in packet.payload.exact_duplicate_relations
        ),
        evidence_refs_by_relation=duplicate_evidence_index,
    )

    graph_records, edge_records = build_graph(
        repositories,
        normalized.artifacts,
        capabilities,
        normalized.relationships + projection.edges + work.edges + duplicate_edges + corpus_edges,
        projection.nodes + work.nodes + corpus_nodes,
    )
    flows = build_flows(edge_records)
    impacts = assess_impact(repositories, edge_records)
    maturity = assess_maturity(repositories, evidence, configuration.maturity_profile)
    risks = assess_risk(repositories, configuration.risk_profile)

    # Candidate and readiness domains, compiled after the canonical graph so
    # they can be measured against it — and kept out of `edge_records`, which is
    # what every canonical consumer above already read.
    readiness = tuple(
        record for packet in corpus_packets for record in compile_readiness_evidence(packet)
    )
    candidate_relations = tuple(
        relation for packet in corpus_packets for relation in compile_candidate_relations(packet)
    )
    artifact_repository = {
        record.artifact_id: record.repository_id for record in normalized.artifacts
    }
    roots_by_artifact = root_by_artifact(corpus_packets, artifact_repository)
    all_conflicts = (
        evidence_conflicts + repository_conflicts + capability_conflicts + claim_conflicts
    )
    all_unknowns = (
        repository_unknowns + evidence_unknowns + declared_unknowns + claim_unknowns + work.unknowns
    )
    candidate_clusters = tuple(
        cluster
        for packet in corpus_packets
        for cluster in compile_candidate_clusters(
            packet,
            artifacts=normalized.artifacts,
            edges=edge_records,
            claims=claims,
            conflicts=all_conflicts,
            root_by_artifact=roots_by_artifact,
            readiness_by_subject=readiness_by_subject(readiness),
        )
    )
    reasoning_candidates = route_reasoning_candidates(
        candidate_clusters,
        corpus_packets,
        edges=edge_records,
        conflicts=all_conflicts,
        unknowns=all_unknowns,
    )
    # Candidates project into the graph labelled `Candidate…` and marked
    # `canonical: False`. They are appended to `graph_records` and never to
    # `edge_records`: impact, flow, maturity, and risk read the latter, so the
    # separation holds by construction rather than by a filter somebody must
    # remember to apply.
    graph_records = tuple(
        sorted(
            graph_records + candidate_graph_records(candidate_relations, candidate_clusters),
            key=lambda item: (item.record_type, item.entity_id),
        )
    )

    state = TopologyState(
        repository_records=tuple(sorted(repositories, key=lambda item: item.repository_id)),
        artifact_records=tuple(sorted(normalized.artifacts, key=lambda item: item.artifact_id)),
        capability_records=tuple(sorted(capabilities, key=lambda item: item.capability_id)),
        semantic_claims=tuple(sorted(claims, key=lambda item: item.claim_id)),
        edge_records=tuple(sorted(edge_records, key=lambda item: item.edge_id)),
        flow_records=tuple(sorted(flows, key=lambda item: item.flow_id)),
        graph_records=tuple(
            sorted(graph_records, key=lambda item: (item.record_type, item.entity_id))
        ),
        risks=tuple(sorted(risks, key=lambda item: item.risk_id)),
        maturity=tuple(sorted(maturity, key=lambda item: item.subject_id)),
        impact_indexes=tuple(sorted(impacts, key=lambda item: item.subject_id)),
        corpus_records=tuple(sorted(corpus_records, key=lambda item: item.corpus_id)),
        root_records=tuple(sorted(root_records, key=lambda item: item.root_id)),
        candidate_relations=tuple(sorted(candidate_relations, key=lambda item: item.relation_id)),
        candidate_clusters=tuple(sorted(candidate_clusters, key=lambda item: item.candidate_id)),
        readiness_evidence=tuple(sorted(readiness, key=lambda item: item.readiness_id)),
        topology_reasoning_candidates=tuple(
            sorted(reasoning_candidates, key=lambda item: item.reasoning_candidate_id)
        ),
        evidence=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
        diagnostics=tuple(
            sorted(
                normalized.diagnostics + claim_diagnostics,
                key=lambda item: item.diagnostic_id,
            )
        ),
        unknowns=tuple(sorted(all_unknowns, key=lambda item: item.unknown_id)),
        conflicts=tuple(sorted(all_conflicts, key=lambda item: item.conflict_id)),
    )

    input_refs = tuple(
        sorted((_packet_ref(bundle) for bundle in bundles), key=lambda ref: ref.packet_id)
    )
    corpus_refs = tuple(
        sorted(
            (_corpus_packet_ref(bundle) for bundle in corpus_bundles),
            key=lambda ref: ref.packet_id,
        )
    )
    timestamp = created_at if created_at is not None else CANONICAL_CREATED_AT
    candidate = TopologyPacket(
        packet_id="packet:pending",
        producer=Producer(name=COMPILER_NAME, version=COMPILER_VERSION),
        profile=ProfileRef(
            id=configuration.profile_id,
            version=configuration.profile_version,
            hash=semantic_hash(configuration.topology_profile),
        ),
        inputs=TopologyInputs(
            repository_model_packets=input_refs,
            corpus_intelligence_packets=corpus_refs,
        ),
        schema_hash=configuration.schema_contract_hash,
        policy_hashes=_policy_hashes(configuration),
        payload_refs=topology_payload_refs(),
        payload_hashes=topology_payload_hashes(state),
        validation=PacketValidationRef(status="not_run"),
        semantic_hash="sha256:pending",
        artifact_hash="sha256:pending",
        lineage=PacketLineage(
            # Corpus packets are parents too: a topology whose candidate domains
            # came out of one is descended from it, and a lineage naming only the
            # repository packets would not say where those records came from.
            parent_packet_ids=tuple(sorted(ref.packet_id for ref in (*input_refs, *corpus_refs))),
            generation=1,
        ),
        created_at=timestamp,
    )
    digest = calculate_topology_semantic_hash(candidate)
    packet_id = f"packet:{digest.removeprefix('sha256:')}"
    candidate = candidate.model_copy(update={"packet_id": packet_id, "semantic_hash": digest})
    receipt = validate_topology(
        candidate,
        state,
        bundles,
        corpus_bundles=corpus_bundles,
        schema_root=repository_root,
        created_at=timestamp,
    )
    if receipt.status != "passed":
        raise TopologyCompilationError(
            "topology validation failed; no outputs were committed", receipt
        )

    final_without_artifact_hash = candidate.model_copy(
        update={
            "validation": PacketValidationRef(
                status="passed",
                receipt_ref="receipts/validation-receipt.json",
            )
        }
    )
    packet_core_hash = artifact_hash(
        canonical_bytes(final_without_artifact_hash.model_dump(exclude={"artifact_hash"}))
    )
    packet = final_without_artifact_hash.model_copy(update={"artifact_hash": packet_core_hash})
    materialized = MaterializedTopology(packet=packet, state=state)
    artifacts = build_topology_bundle_artifacts(packet, state, receipt, created_at=timestamp)
    return CompilationResult(
        materialized=materialized,
        validation_receipt=receipt,
        input_bundles=bundles,
        corpus_bundles=corpus_bundles,
        configuration=configuration,
        artifacts=artifacts,
    )


def commit_compilation(result: CompilationResult, sink: OutputSink) -> CommitReceipt:
    if result.validation_receipt.status != "passed":
        raise ValueError("failed validation may not be committed")
    for artifact in result.artifacts:
        sink.enqueue(WriteIntent(artifact=artifact))
    plan = sink.plan()
    if plan.status == "blocked":
        return sink.commit()
    return sink.commit()
