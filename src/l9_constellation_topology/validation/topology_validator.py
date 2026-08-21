"""Fail-closed validation for canonical Topology Packets."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator

from l9_constellation_topology.domain import (
    Authority,
    EdgeType,
    TopologyState,
)
from l9_constellation_topology.packets.common import Producer, ValidationStatus
from l9_constellation_topology.packets.loader import RepositoryModelBundle
from l9_constellation_topology.packets.payloads import topology_payload_hashes
from l9_constellation_topology.packets.topology_packet import (
    TopologyPacket,
    calculate_topology_semantic_hash,
)
from l9_constellation_topology.packets.validation_receipt import (
    ValidationCheck,
    ValidationReceipt,
    finalize_validation_receipt,
)
from l9_constellation_topology.run.evidence import utc_now


def _check(
    *,
    check_id: str,
    check_class: str,
    rule: str,
    passed: bool,
    success: str,
    failure: str,
    path: str | None = None,
    evidence_refs: tuple[str, ...] = (),
    details: dict[str, object] | None = None,
) -> ValidationCheck:
    return ValidationCheck(
        check_id=check_id,
        check_class=check_class,  # type: ignore[arg-type]
        rule=rule,
        status="passed" if passed else "failed",
        message=success if passed else failure,
        path=path,
        evidence_refs=evidence_refs,
        details=details or {},
    )


def _schema_errors(schema_path: Path, value: object) -> tuple[str, ...]:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return (f"cannot load schema {schema_path}: {exc}",)
    validator = Draft202012Validator(schema)
    return tuple(
        sorted(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in validator.iter_errors(value)
        )
    )


def _record_schema_errors(
    schema_root: Path,
    schema_name: str,
    records: Iterable[object],
) -> tuple[str, ...]:
    errors: list[str] = []
    schema_path = schema_root / "schemas" / schema_name
    for index, record in enumerate(records):
        value = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
        for error in _schema_errors(schema_path, value):
            errors.append(f"record[{index}] {error}")
    return tuple(errors)


def _duplicates(values: Iterable[str]) -> tuple[str, ...]:
    counts = Counter(values)
    return tuple(sorted(value for value, count in counts.items() if count > 1))


def _record_evidence_refs(
    state: TopologyState,
) -> list[tuple[str, tuple[str, ...], Authority | None]]:
    records: list[tuple[str, tuple[str, ...], Authority | None]] = []
    records.extend(
        (repository.repository_id, repository.evidence_refs, repository.confidence.authority)
        for repository in state.repository_records
    )
    records.extend(
        (artifact.artifact_id, artifact.evidence_refs, artifact.confidence.authority)
        for artifact in state.artifact_records
    )
    records.extend(
        (capability.capability_id, capability.evidence_refs, capability.confidence.authority)
        for capability in state.capability_records
    )
    records.extend(
        (claim.claim_id, claim.evidence_refs, claim.authority) for claim in state.semantic_claims
    )
    records.extend(
        (edge.edge_id, edge.evidence_refs, edge.confidence.authority) for edge in state.edge_records
    )
    records.extend(
        (flow.flow_id, flow.evidence_refs, flow.confidence.authority) for flow in state.flow_records
    )
    records.extend(
        (graph.entity_id, graph.evidence_refs, graph.confidence.authority)
        for graph in state.graph_records
    )
    records.extend((risk.risk_id, risk.evidence_refs, None) for risk in state.risks)
    records.extend(
        (f"maturity:{assessment.subject_id}", assessment.evidence_refs, None)
        for assessment in state.maturity
    )
    records.extend(
        (unknown.unknown_id, unknown.evidence_refs, Authority.candidate)
        for unknown in state.unknowns
    )
    records.extend(
        (conflict.conflict_id, conflict.evidence_refs, Authority.candidate)
        for conflict in state.conflicts
    )
    records.extend(
        (diagnostic.diagnostic_id, diagnostic.evidence_refs, Authority.candidate)
        for diagnostic in state.diagnostics
    )
    return records


def _dependency_cycles(state: TopologyState) -> tuple[tuple[str, ...], ...]:
    graph: dict[str, set[str]] = defaultdict(set)
    for edge in state.edge_records:
        if edge.edge_type == EdgeType.depends_on:
            graph[edge.source_id].add(edge.target_id)
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, path: tuple[str, ...]) -> None:
        if node in path:
            cycle = (*path[path.index(node) :], node)
            rotations = [
                cycle[index:-1] + cycle[:index] + (cycle[index],) for index in range(len(cycle) - 1)
            ]
            cycles.add(min(rotations))
            return
        if len(path) > len(graph) + 1:
            return
        for target in sorted(graph.get(node, set())):
            visit(target, (*path, node))

    for node in sorted(graph):
        visit(node, ())
    return tuple(sorted(cycles))


def validate_topology(
    packet: TopologyPacket,
    state: TopologyState,
    input_bundles: tuple[RepositoryModelBundle, ...],
    *,
    schema_root: Path,
    created_at: datetime | None = None,
) -> ValidationReceipt:
    """Validate a compiled packet and return its immutable receipt.

    ``created_at`` may be injected for byte-reproducible output. It is stripped
    from the receipt's semantic view, so it never changes receipt identity.
    """
    schema_results: list[ValidationCheck] = []
    invariant_results: list[ValidationCheck] = []
    evidence_results: list[ValidationCheck] = []
    cross_reference_results: list[ValidationCheck] = []

    # Runtime model construction and independent checked-in JSON Schema validation.
    schema_results.append(
        _check(
            check_id="model-topology-packet",
            check_class="schema",
            rule="pydantic_model_construction",
            passed=True,
            success="Topology Packet was constructed through the runtime Pydantic contract.",
            failure="Topology Packet runtime model construction failed.",
            details={"validation_layer": "model-construction", "engine": "pydantic"},
        )
    )
    schema_results.append(
        _check(
            check_id="model-topology-state",
            check_class="schema",
            rule="pydantic_state_construction",
            passed=True,
            success="Topology state collections were constructed through typed runtime models.",
            failure="Topology state runtime model construction failed.",
            details={"validation_layer": "model-construction", "engine": "pydantic"},
        )
    )
    packet_schema_errors = _schema_errors(
        schema_root / "contracts" / "topology-packet.schema.json",
        packet.model_dump(mode="json"),
    )
    schema_results.append(
        _check(
            check_id="json-schema-topology-packet",
            check_class="schema",
            rule="topology_packet_json_schema",
            passed=not packet_schema_errors,
            success="Topology Packet independently validates against the checked-in JSON Schema.",
            failure="Topology Packet failed independent JSON Schema validation.",
            details={
                "validation_layer": "json-schema",
                "engine": "jsonschema.Draft202012Validator",
                "errors": packet_schema_errors,
            },
        )
    )
    record_schemas = (
        ("repository-record.schema.json", state.repository_records),
        ("artifact-record.schema.json", state.artifact_records),
        ("capability-record.schema.json", state.capability_records),
        ("semantic-claim-record.schema.json", state.semantic_claims),
        ("edge-record.schema.json", state.edge_records),
        ("flow-record.schema.json", state.flow_records),
        ("graph-record.schema.json", state.graph_records),
        ("risk-record.schema.json", state.risks),
        ("maturity-assessment.schema.json", state.maturity),
        ("evidence-record.schema.json", state.evidence),
        ("diagnostic-record.schema.json", state.diagnostics),
    )
    record_errors = {
        schema_name: errors
        for schema_name, records in record_schemas
        if (errors := _record_schema_errors(schema_root, schema_name, records))
    }
    schema_results.append(
        _check(
            check_id="json-schema-topology-records",
            check_class="schema",
            rule="topology_record_json_schemas",
            passed=not record_errors,
            success="All canonical topology records independently validate against checked-in schemas.",
            failure="One or more topology records failed independent JSON Schema validation.",
            details={
                "validation_layer": "json-schema",
                "engine": "jsonschema.Draft202012Validator",
                "errors": record_errors,
            },
        )
    )

    # Stable semantic and payload hashes.
    calculated_semantic = calculate_topology_semantic_hash(packet)
    invariant_results.append(
        _check(
            check_id="invariant-semantic-hash",
            check_class="invariant",
            rule="semantic_hash_reproducible",
            passed=packet.semantic_hash == calculated_semantic,
            success="Topology semantic hash is reproducible.",
            failure=(
                f"Topology semantic hash mismatch: expected {packet.semantic_hash}, "
                f"calculated {calculated_semantic}."
            ),
        )
    )
    expected_packet_id = f"packet:{packet.semantic_hash.removeprefix('sha256:')}"
    invariant_results.append(
        _check(
            check_id="invariant-packet-id",
            check_class="invariant",
            rule="packet_id_matches_semantic_hash",
            passed=packet.packet_id == expected_packet_id,
            success="Packet identity is derived from the semantic hash.",
            failure=f"Packet ID must be {expected_packet_id}, got {packet.packet_id}.",
        )
    )
    calculated_payload_hashes = topology_payload_hashes(state)
    invariant_results.append(
        _check(
            check_id="invariant-payload-hashes",
            check_class="invariant",
            rule="payload_hashes_resolve",
            passed=packet.payload_hashes == calculated_payload_hashes,
            success="Every payload hash resolves to the exact materialized bytes.",
            failure="One or more payload hashes do not match the materialized topology state.",
            details={
                "expected": calculated_payload_hashes,
                "actual": packet.payload_hashes,
            },
        )
    )

    id_sets = {
        "repository": tuple(record.repository_id for record in state.repository_records),
        "artifact": tuple(record.artifact_id for record in state.artifact_records),
        "capability": tuple(record.capability_id for record in state.capability_records),
        "semantic-claim": tuple(record.claim_id for record in state.semantic_claims),
        "edge": tuple(record.edge_id for record in state.edge_records),
        "flow": tuple(record.flow_id for record in state.flow_records),
        "graph": tuple(record.entity_id for record in state.graph_records),
        "risk": tuple(record.risk_id for record in state.risks),
        "unknown": tuple(record.unknown_id for record in state.unknowns),
        "conflict": tuple(record.conflict_id for record in state.conflicts),
    }
    for category, values in id_sets.items():
        duplicate_ids = _duplicates(values)
        invariant_results.append(
            _check(
                check_id=f"invariant-unique-{category}-ids",
                check_class="invariant",
                rule="canonical_ids_unique",
                passed=not duplicate_ids,
                success=f"{category.title()} identities are unique.",
                failure=f"Duplicate {category} identities: {', '.join(duplicate_ids)}.",
                details={"duplicates": duplicate_ids},
            )
        )

    node_ids = {record.entity_id for record in state.graph_records if record.record_type == "node"}
    unresolved_endpoints = tuple(
        sorted(
            {
                endpoint
                for edge in state.edge_records
                for endpoint in (edge.source_id, edge.target_id)
                if endpoint not in node_ids
            }
        )
    )
    invariant_results.append(
        _check(
            check_id="invariant-edge-endpoints",
            check_class="invariant",
            rule="every_edge_endpoint_exists",
            passed=not unresolved_endpoints,
            success="Every edge endpoint resolves to a canonical graph node.",
            failure=f"Unresolved edge endpoints: {', '.join(unresolved_endpoints)}.",
            details={"unresolved_endpoints": unresolved_endpoints},
        )
    )

    revisions_missing = tuple(
        sorted(
            record.repository_id
            for record in state.repository_records
            if not record.source_revision
        )
    )
    invariant_results.append(
        _check(
            check_id="invariant-source-revisions",
            check_class="invariant",
            rule="source_revisions_present",
            passed=not revisions_missing,
            success="Every repository has an explicit source revision.",
            failure=f"Repositories missing source revisions: {', '.join(revisions_missing)}.",
        )
    )

    invalid_paths = tuple(
        sorted(
            record.source_path
            for record in state.artifact_records
            if PurePosixPath(record.source_path).is_absolute()
            or record.source_path == ".."
            or record.source_path.startswith("../")
        )
    )
    invariant_results.append(
        _check(
            check_id="invariant-portable-paths",
            check_class="invariant",
            rule="no_absolute_paths_in_semantic_identity",
            passed=not invalid_paths,
            success="All source paths are portable repository-relative paths.",
            failure=f"Non-portable source paths: {', '.join(invalid_paths)}.",
        )
    )

    blocking_conflicts = tuple(
        sorted(
            record.conflict_id
            for record in state.conflicts
            if record.blocking and not record.resolution
        )
    )
    invariant_results.append(
        _check(
            check_id="invariant-blocking-conflicts",
            check_class="invariant",
            rule="blocking_conflicts_resolved",
            passed=not blocking_conflicts,
            success="No unresolved blocking topology conflicts remain.",
            failure=f"Unresolved blocking conflicts: {', '.join(blocking_conflicts)}.",
            details={"blocking_conflicts": blocking_conflicts},
        )
    )

    cycles = _dependency_cycles(state)
    invariant_results.append(
        _check(
            check_id="invariant-dependency-cycles-reported",
            check_class="invariant",
            rule="cycles_reported",
            passed=True,
            success=(
                "Dependency cycle scan completed; cycles are recorded in validation receipt details."
                if cycles
                else "Dependency cycle scan completed with no cycles."
            ),
            failure="Dependency cycle scan failed.",
            details={"cycles": cycles},
        )
    )

    evidence_ids = {record.evidence_id for record in state.evidence}
    unresolved_evidence: dict[str, tuple[str, ...]] = {}
    missing_required_evidence: list[str] = []
    for subject_id, refs, authority in _record_evidence_refs(state):
        missing = tuple(sorted(set(refs) - evidence_ids))
        if missing:
            unresolved_evidence[subject_id] = missing
        if (
            authority in {Authority.source, Authority.validated_machine, Authority.derived}
            and not refs
        ):
            missing_required_evidence.append(subject_id)
    evidence_results.append(
        _check(
            check_id="evidence-references-resolve",
            check_class="evidence",
            rule="every_evidence_reference_resolves",
            passed=not unresolved_evidence,
            success="Every evidence reference resolves within the Topology Packet.",
            failure="One or more topology records reference missing evidence.",
            details={"unresolved": unresolved_evidence},
        )
    )
    evidence_results.append(
        _check(
            check_id="evidence-canonical-claims-backed",
            check_class="evidence",
            rule="canonical_claims_require_evidence",
            passed=not missing_required_evidence,
            success="Every accepted canonical claim carries evidence references.",
            failure=(
                "Canonical claims without evidence: " + ", ".join(sorted(missing_required_evidence))
            ),
            details={"subjects": tuple(sorted(missing_required_evidence))},
        )
    )
    bad_inference = tuple(
        sorted(
            record.evidence_id
            for record in state.evidence
            if record.source_type == "inference" and record.evidence_class == "declared"
        )
    )
    evidence_results.append(
        _check(
            check_id="evidence-inference-labeling",
            check_class="evidence",
            rule="inference_not_marked_declared",
            passed=not bad_inference,
            success="No inferred evidence is misclassified as declared authority.",
            failure=f"Inferred evidence marked declared: {', '.join(bad_inference)}.",
        )
    )

    input_diagnostic_count = sum(
        len(bundle.packet.payload.diagnostics)
        for bundle in input_bundles
        if bundle.packet.payload is not None
    )
    preserved_diagnostic_count = sum(
        1 for diagnostic in state.diagnostics if diagnostic.disposition == "preserved"
    )
    diagnostic_source_packets = {diagnostic.source_packet_id for diagnostic in state.diagnostics}
    expected_diagnostic_sources = {
        bundle.packet.packet_id
        for bundle in input_bundles
        if bundle.packet.payload is not None and bundle.packet.payload.diagnostics
    }
    cross_reference_results.append(
        _check(
            check_id="cross-diagnostic-conservation",
            check_class="cross-reference",
            rule="input_diagnostics_conserved",
            passed=(
                input_diagnostic_count == preserved_diagnostic_count
                and expected_diagnostic_sources <= diagnostic_source_packets
            ),
            success="Every accepted input diagnostic is preserved with source-packet lineage.",
            failure="One or more accepted input diagnostics were lost or lack source lineage.",
            details={
                "input_count": input_diagnostic_count,
                "preserved_count": preserved_diagnostic_count,
                "expected_source_packets": tuple(sorted(expected_diagnostic_sources)),
                "actual_source_packets": tuple(sorted(diagnostic_source_packets)),
            },
        )
    )

    packet_refs = {
        reference.packet_id: reference for reference in packet.inputs.repository_model_packets
    }
    bundle_refs = {bundle.packet.packet_id: bundle for bundle in input_bundles}
    input_mismatch = tuple(sorted(set(packet_refs) ^ set(bundle_refs)))
    cross_reference_results.append(
        _check(
            check_id="cross-input-packet-set",
            check_class="cross-reference",
            rule="input_packet_set_matches",
            passed=not input_mismatch,
            success="Topology input references match the loaded Repository Model Packets.",
            failure=f"Topology input packet set mismatch: {', '.join(input_mismatch)}.",
        )
    )
    failed_parents = tuple(
        sorted(
            bundle.packet.packet_id
            for bundle in input_bundles
            if bundle.packet.validation.status != "passed" or bundle.receipt.status != "passed"
        )
    )
    cross_reference_results.append(
        _check(
            check_id="cross-parent-validation",
            check_class="cross-reference",
            rule="input_validation_passed",
            passed=not failed_parents,
            success="Every input packet has a passed validation receipt.",
            failure=f"Input packets without passed validation: {', '.join(failed_parents)}.",
        )
    )
    reference_mismatches: list[str] = []
    for packet_id in sorted(set(packet_refs) & set(bundle_refs)):
        reference = packet_refs[packet_id]
        bundle = bundle_refs[packet_id]
        if reference.semantic_hash != bundle.packet.semantic_hash:
            reference_mismatches.append(f"{packet_id}:semantic_hash")
        if reference.source_revision != bundle.packet.source_snapshot.revision:
            reference_mismatches.append(f"{packet_id}:source_revision")
        if reference.validation_status != "passed":
            reference_mismatches.append(f"{packet_id}:validation_status")
    cross_reference_results.append(
        _check(
            check_id="cross-input-reference-integrity",
            check_class="cross-reference",
            rule="input_refs_match_packets",
            passed=not reference_mismatches,
            success="Every input reference matches its packet hash, revision, and validation status.",
            failure=f"Input reference mismatches: {', '.join(reference_mismatches)}.",
            details={"mismatches": tuple(reference_mismatches)},
        )
    )

    all_checks = (
        tuple(schema_results)
        + tuple(invariant_results)
        + tuple(evidence_results)
        + tuple(cross_reference_results)
    )
    status: ValidationStatus = (
        "failed" if any(check.status == "failed" for check in all_checks) else "passed"
    )
    candidate = ValidationReceipt(
        receipt_id="receipt:pending",
        subject_packet_id=packet.packet_id,
        subject_semantic_hash=packet.semantic_hash,
        validator=Producer(name="l9-constellation-topology", version="2.0.0"),
        status=status,
        schema_results=tuple(schema_results),
        invariant_results=tuple(invariant_results),
        evidence_results=tuple(evidence_results),
        cross_reference_results=tuple(cross_reference_results),
        semantic_hash="sha256:pending",
        created_at=created_at if created_at is not None else utc_now(),
    )
    return finalize_validation_receipt(candidate)
