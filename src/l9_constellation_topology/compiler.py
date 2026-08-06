"""Deterministic packet-native topology compiler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from l9_constellation_topology.config import ResolvedConfiguration
from l9_constellation_topology.domain import TopologyState
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
from l9_constellation_topology.packets.bundle import build_topology_bundle_artifacts
from l9_constellation_topology.packets.loader import (
    RepositoryModelBundle,
    load_repository_model_bundle,
)
from l9_constellation_topology.packets.payloads import (
    topology_payload_hashes,
    topology_payload_refs,
)
from l9_constellation_topology.packets.topology_packet import (
    MaterializedTopology,
    calculate_topology_semantic_hash,
)
from l9_constellation_topology.run import artifact_hash, canonical_bytes, semantic_hash, utc_now
from l9_constellation_topology.stages import aggregate_capabilities, aggregate_repositories
from l9_constellation_topology.stages.assess_impact import run as assess_impact
from l9_constellation_topology.stages.assess_maturity import run as assess_maturity
from l9_constellation_topology.stages.assess_risk import run as assess_risk
from l9_constellation_topology.stages.build_graph import run as build_graph
from l9_constellation_topology.stages.classify_roles import run as classify_roles
from l9_constellation_topology.stages.ingest_packets import adapt_packets
from l9_constellation_topology.stages.normalize_models import run as normalize_models
from l9_constellation_topology.stages.reconcile_evidence import run as reconcile_evidence
from l9_constellation_topology.stages.resolve_config import run as resolve_config
from l9_constellation_topology.stages.validate_topology import run as validate_topology
from l9_constellation_topology.topology.capability_builder import build_capabilities
from l9_constellation_topology.topology.flow_builder import build_flows

COMPILER_NAME = "l9-constellation-topology"
COMPILER_VERSION = "2.0.0"


@dataclass(frozen=True)
class CompilationResult:
    materialized: MaterializedTopology
    validation_receipt: ValidationReceipt
    input_bundles: tuple[RepositoryModelBundle, ...]
    configuration: ResolvedConfiguration
    artifacts: tuple[RenderedArtifact, ...]


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


def _policy_hashes(configuration: ResolvedConfiguration) -> dict[str, str]:
    return {
        "topology": semantic_hash(configuration.topology_profile),
        "risk": semantic_hash(configuration.risk_profile),
        "maturity": semantic_hash(configuration.maturity_profile),
        "report": semantic_hash(configuration.report_profile),
        "packet": semantic_hash(configuration.packet_profile),
        "output": semantic_hash(configuration.output_policy),
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
        "adapter_mode": adapter_mode,
    }
    return semantic_hash(identity)


def compile_topology(
    repository_root: Path,
    input_bundle_paths: tuple[Path, ...],
    *,
    created_at: datetime | None = None,
) -> CompilationResult:
    if not input_bundle_paths:
        raise ValueError("at least one Repository Model Packet bundle is required")
    configuration = resolve_config(repository_root)
    bundles = tuple(load_repository_model_bundle(path) for path in input_bundle_paths)
    packets = tuple(bundle.packet for bundle in bundles)
    normalized = normalize_models(adapt_packets(packets))

    evidence, evidence_conflicts = reconcile_evidence(normalized.evidence)
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
    capabilities = build_capabilities(
        repositories,
        normalized.artifacts,
        normalized.capabilities,
    )
    capabilities, capability_conflicts = aggregate_capabilities.run(capabilities)
    graph_records, edge_records = build_graph(
        repositories,
        normalized.artifacts,
        capabilities,
        normalized.relationships,
    )
    flows = build_flows(edge_records)
    impacts = assess_impact(repositories, edge_records)
    maturity = assess_maturity(repositories, evidence, configuration.maturity_profile)
    risks = assess_risk(repositories, configuration.risk_profile)

    state = TopologyState(
        repository_records=tuple(sorted(repositories, key=lambda item: item.repository_id)),
        artifact_records=tuple(sorted(normalized.artifacts, key=lambda item: item.artifact_id)),
        capability_records=tuple(sorted(capabilities, key=lambda item: item.capability_id)),
        edge_records=tuple(sorted(edge_records, key=lambda item: item.edge_id)),
        flow_records=tuple(sorted(flows, key=lambda item: item.flow_id)),
        graph_records=tuple(
            sorted(graph_records, key=lambda item: (item.record_type, item.entity_id))
        ),
        risks=tuple(sorted(risks, key=lambda item: item.risk_id)),
        maturity=tuple(sorted(maturity, key=lambda item: item.subject_id)),
        impact_indexes=tuple(sorted(impacts, key=lambda item: item.subject_id)),
        evidence=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
        diagnostics=tuple(sorted(normalized.diagnostics, key=lambda item: item.diagnostic_id)),
        unknowns=tuple(sorted(repository_unknowns, key=lambda item: item.unknown_id)),
        conflicts=tuple(
            sorted(
                evidence_conflicts + repository_conflicts + capability_conflicts,
                key=lambda item: item.conflict_id,
            )
        ),
    )

    input_refs = tuple(
        sorted((_packet_ref(bundle) for bundle in bundles), key=lambda ref: ref.packet_id)
    )
    timestamp = created_at or utc_now()
    candidate = TopologyPacket(
        packet_id="packet:pending",
        producer=Producer(name=COMPILER_NAME, version=COMPILER_VERSION),
        profile=ProfileRef(
            id=configuration.profile_id,
            version=configuration.profile_version,
            hash=semantic_hash(configuration.topology_profile),
        ),
        inputs=TopologyInputs(repository_model_packets=input_refs),
        schema_hash=configuration.schema_contract_hash,
        policy_hashes=_policy_hashes(configuration),
        payload_refs=topology_payload_refs(),
        payload_hashes=topology_payload_hashes(state),
        validation=PacketValidationRef(status="not_run"),
        semantic_hash="sha256:pending",
        artifact_hash="sha256:pending",
        lineage=PacketLineage(
            parent_packet_ids=tuple(ref.packet_id for ref in input_refs),
            generation=1,
        ),
        created_at=timestamp,
    )
    digest = calculate_topology_semantic_hash(candidate)
    packet_id = f"packet:{digest.removeprefix('sha256:')}"
    candidate = candidate.model_copy(update={"packet_id": packet_id, "semantic_hash": digest})
    receipt = validate_topology(candidate, state, bundles, schema_root=repository_root)
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
