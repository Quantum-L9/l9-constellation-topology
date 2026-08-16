"""Command dispatch for the packet-native topology compiler."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import yaml

from l9_constellation_topology.compatibility.v4_models import RepoSource
from l9_constellation_topology.compiler import (
    TopologyCompilationError,
    commit_compilation,
    compile_topology,
)
from l9_constellation_topology.config import resolve_configuration
from l9_constellation_topology.domain import ConfidenceLevel, EdgeType
from l9_constellation_topology.io import (
    CommitReceipt,
    FileSystemOutputSink,
    PacketBundleOutputSink,
    RenderedArtifact,
    WriteIntent,
    WritePolicy,
    format_commit_failure,
)
from l9_constellation_topology.packets import (
    PacketLoadError,
    load_repository_model_bundle,
    load_topology_bundle,
)
from l9_constellation_topology.packets.bundle_verification import BundleVerificationError
from l9_constellation_topology.packets.repository_bundle import (
    build_repository_model_bundle_artifacts,
)
from l9_constellation_topology.publication import (
    build_publication_plan_artifacts,
    plan_publication_from_repository,
    validate_publication_plan,
)
from l9_constellation_topology.renderers import (
    DEFAULT_FORMATS,
    SUPPORTED_FORMATS,
    render_neo4j_candidate_artifact,
    render_reports,
)
from l9_constellation_topology.run import canonical_json, semantic_hash
from l9_constellation_topology.scanners.repository_model_scanner import scan_repository_model
from l9_constellation_topology.topology.impact import assess_impact
from l9_constellation_topology.validation.topology_validator import validate_topology


def _print_json(value: object) -> None:
    print(canonical_json(value))


def _report_commit_failure(
    receipt: CommitReceipt,
    *,
    stage: str,
    packet_type: str | None = None,
) -> None:
    """Write the receipt's own reasons to stderr before a nonzero exit."""
    if receipt.status == "passed":
        return
    for line in format_commit_failure(receipt, stage=stage, packet_type=packet_type):
        print(line, file=sys.stderr)


def _format_verification_error(exc: BundleVerificationError) -> tuple[str, ...]:
    """Render a bundle verification failure with its actionable coordinates."""
    lines = [f"ERROR: {exc.stage}: {exc.code}"]
    if exc.packet_type is not None:
        lines.append(f"ERROR: {exc.stage}: packet type {exc.packet_type}")
    if exc.member is not None:
        lines.append(f"ERROR: {exc.stage}: member {exc.member}")
    lines.extend(f"ERROR: {line}" for line in str(exc).splitlines())
    return tuple(lines)


def _commit_exit_code(
    receipt: CommitReceipt,
    *,
    stage: str,
    packet_type: str | None = None,
) -> int:
    _report_commit_failure(receipt, stage=stage, packet_type=packet_type)
    return 0 if receipt.status == "passed" else 2


def _write_artifacts(
    output_root: Path,
    artifacts: tuple[RenderedArtifact, ...],
    *,
    dry_run: bool,
    allow_overwrite: bool,
) -> CommitReceipt:
    kinds = tuple(dict.fromkeys(artifact.artifact_kind for artifact in artifacts))
    sink = FileSystemOutputSink(
        output_root,
        WritePolicy(
            mode="dry-run" if dry_run else "write",
            allowed_output_roots=(".",),
            allowed_artifact_kinds=kinds,
            allow_overwrite=allow_overwrite,
            require_expected_hash_for_replace=False,
            enforce_path_containment=True,
            reject_collisions=True,
            atomic_writes=True,
        ),
    )
    for artifact in artifacts:
        sink.enqueue(WriteIntent(artifact=artifact))
    return sink.commit()


def cmd_compile_packet(args: argparse.Namespace) -> int:
    result = compile_topology(
        Path(args.repo_root),
        tuple(Path(path) for path in args.input_bundle),
    )
    sink = PacketBundleOutputSink(
        Path(args.out),
        mode="dry-run" if args.dry_run else "write",
        allow_overwrite=args.allow_overwrite,
    )
    receipt = commit_compilation(result, sink)
    _print_json(
        {
            "status": receipt.status,
            "packet_id": result.materialized.packet.packet_id,
            "semantic_hash": result.materialized.packet.semantic_hash,
            "validation_status": result.validation_receipt.status,
            "write_plan_id": receipt.plan_id,
            "outputs": [item.model_dump(mode="json") for item in receipt.results],
        }
    )
    return _commit_exit_code(receipt, stage="compile-packet", packet_type="l9.topology")


def cmd_validate_packet(args: argparse.Namespace) -> int:
    materialized, stored_receipt = load_topology_bundle(Path(args.input_bundle))
    if args.repository_bundle:
        input_bundles = tuple(
            load_repository_model_bundle(Path(path)) for path in args.repository_bundle
        )
        receipt = validate_topology(
            materialized.packet,
            materialized.state,
            input_bundles,
            schema_root=Path(args.repo_root),
        )
    else:
        receipt = stored_receipt
    _print_json(
        {
            "status": receipt.status,
            "packet_id": materialized.packet.packet_id,
            "semantic_hash": materialized.packet.semantic_hash,
            "receipt_id": receipt.receipt_id,
            "checks": {
                "schema": len(receipt.schema_results),
                "invariant": len(receipt.invariant_results),
                "evidence": len(receipt.evidence_results),
                "cross_reference": len(receipt.cross_reference_results),
            },
        }
    )
    return 0 if receipt.status == "passed" else 2


def cmd_render_report(args: argparse.Namespace) -> int:
    materialized, _ = load_topology_bundle(Path(args.input_bundle))
    configuration = resolve_configuration(Path(args.repo_root))
    formats = tuple(args.format or DEFAULT_FORMATS)
    projection = render_reports(
        materialized,
        formats=formats,
        report_profile_hash=semantic_hash(configuration.report_profile),
    )
    receipt = _write_artifacts(
        Path(args.out),
        projection.artifacts,
        dry_run=args.dry_run,
        allow_overwrite=args.allow_overwrite,
    )
    _print_json(
        {
            "status": receipt.status,
            "cache_key": projection.manifest.cache_key,
            "report_manifest_hash": projection.manifest.semantic_hash,
            "formats": formats,
            "outputs": [item.model_dump(mode="json") for item in receipt.results],
        }
    )
    return _commit_exit_code(receipt, stage="render-report")


def cmd_impact(args: argparse.Namespace) -> int:
    materialized, _ = load_topology_bundle(Path(args.input_bundle))
    result = assess_impact(
        args.entity,
        materialized.state.edge_records,
        direction=args.direction,
        maximum_depth=args.maximum_depth,
        edge_types={EdgeType(value) for value in args.edge_type} if args.edge_type else None,
        minimum_confidence=ConfidenceLevel(args.minimum_confidence),
    )
    _print_json(result)
    return 0


def cmd_inspect_packet(args: argparse.Namespace) -> int:
    materialized, receipt = load_topology_bundle(Path(args.input_bundle))
    state = materialized.state
    _print_json(
        {
            "packet": materialized.packet.model_dump(mode="json"),
            "validation": {
                "receipt_id": receipt.receipt_id,
                "status": receipt.status,
            },
            "counts": {
                "repositories": len(state.repository_records),
                "artifacts": len(state.artifact_records),
                "capabilities": len(state.capability_records),
                "edges": len(state.edge_records),
                "flows": len(state.flow_records),
                "risks": len(state.risks),
                "unknowns": len(state.unknowns),
                "conflicts": len(state.conflicts),
            },
        }
    )
    return 0


def cmd_verify_determinism(args: argparse.Namespace) -> int:
    paths = tuple(Path(path) for path in args.input_bundle)
    first = compile_topology(
        Path(args.repo_root),
        paths,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = compile_topology(
        Path(args.repo_root),
        paths,
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    semantic_equal = (
        first.materialized.packet.semantic_hash == second.materialized.packet.semantic_hash
    )
    payload_equal = (
        first.materialized.packet.payload_hashes == second.materialized.packet.payload_hashes
    )
    _print_json(
        {
            "status": "passed" if semantic_equal and payload_equal else "failed",
            "semantic_hash_equal": semantic_equal,
            "payload_hashes_equal": payload_equal,
            "first_semantic_hash": first.materialized.packet.semantic_hash,
            "second_semantic_hash": second.materialized.packet.semantic_hash,
            "artifact_hash_equal": (
                first.materialized.packet.artifact_hash == second.materialized.packet.artifact_hash
            ),
        }
    )
    return 0 if semantic_equal and payload_equal else 2


def _write_synthetic_bundle(source: RepoSource, destination: Path) -> None:
    """Commit the synthetic Repository Model bundle for one observed source.

    The bundle is written through ``OutputSink`` and verified back as an
    ``l9.repository-model`` bundle, exactly as the canonical ingress would read
    it. A failure here reports the sink's own reasons rather than its status.
    """
    synthetic = scan_repository_model(source)
    sink = PacketBundleOutputSink(destination, allow_overwrite=True)
    for artifact in build_repository_model_bundle_artifacts(synthetic):
        sink.enqueue(WriteIntent(artifact=artifact))
    receipt = sink.commit()
    if receipt.status != "passed":
        detail = "\n".join(
            format_commit_failure(
                receipt,
                stage=f"scan/{source.repo_id}/repository-model-bundle-commit",
                packet_type=synthetic.packet.packet_type,
            )
        )
        raise RuntimeError(detail)


def _compile_scanned_sources(
    sources: tuple[RepoSource, ...],
    *,
    repo_root: Path,
    output: Path,
    dry_run: bool,
    allow_overwrite: bool,
) -> int:
    with tempfile.TemporaryDirectory(prefix="l9-topology-scan-") as temporary:
        root = Path(temporary)
        bundle_paths: list[Path] = []
        for source in sources:
            bundle_path = root / source.repo_id
            _write_synthetic_bundle(source, bundle_path)
            bundle_paths.append(bundle_path)
        result = compile_topology(repo_root, tuple(bundle_paths))
        receipt = commit_compilation(
            result,
            PacketBundleOutputSink(
                output,
                mode="dry-run" if dry_run else "write",
                allow_overwrite=allow_overwrite,
            ),
        )
    _print_json(
        {
            "status": receipt.status,
            "packet_id": result.materialized.packet.packet_id,
            "repositories": [
                record.repository_id for record in result.materialized.state.repository_records
            ],
            "compatibility_mode": "bounded-direct-observation-to-repository-model-packet",
        }
    )
    return _commit_exit_code(receipt, stage="scan/topology-bundle-commit", packet_type="l9.topology")


def cmd_scan(args: argparse.Namespace) -> int:
    source_root = Path(args.source_repo).resolve()
    if not source_root.is_dir():
        raise ValueError(f"source repository does not exist: {source_root}")
    source = RepoSource(
        repo_id=args.repository_id or source_root.name,
        name=args.name or source_root.name,
        local_path=str(source_root),
        expected_role=args.expected_role,
    )
    return _compile_scanned_sources(
        (source,),
        repo_root=Path(args.repo_root),
        output=Path(args.out),
        dry_run=args.dry_run,
        allow_overwrite=args.allow_overwrite,
    )


def cmd_scan_many(args: argparse.Namespace) -> int:
    source_file = Path(args.sources)
    raw = yaml.safe_load(source_file.read_text(encoding="utf-8"))
    sources = tuple(RepoSource(**item) for item in raw.get("repo_sources", ()))
    if not sources:
        raise ValueError("repo_sources is empty")
    return _compile_scanned_sources(
        sources,
        repo_root=Path(args.repo_root),
        output=Path(args.out),
        dry_run=args.dry_run,
        allow_overwrite=args.allow_overwrite,
    )


def cmd_export_neo4j(args: argparse.Namespace) -> int:
    materialized, _ = load_topology_bundle(Path(args.input_bundle))
    artifact = render_neo4j_candidate_artifact(materialized).model_copy(
        update={"destination_path": Path(args.out).name}
    )
    receipt = _write_artifacts(
        Path(args.out).resolve().parent,
        (artifact,),
        dry_run=args.dry_run,
        allow_overwrite=args.allow_overwrite,
    )
    _print_json(
        {
            "status": receipt.status,
            "note": "candidate projection only; no Neo4j write client is present",
            "outputs": [item.model_dump(mode="json") for item in receipt.results],
        }
    )
    return _commit_exit_code(receipt, stage="export-neo4j")


def cmd_plan_publication(args: argparse.Namespace) -> int:
    repository_root = Path(args.repo_root)
    materialized, _ = load_topology_bundle(Path(args.input_bundle))
    plan = plan_publication_from_repository(materialized, repository_root)
    schema_errors = validate_publication_plan(plan, repository_root=repository_root)
    if schema_errors:
        for error in schema_errors:
            print(f"publication plan schema error: {error}", file=sys.stderr)
        return 2
    receipt = _write_artifacts(
        Path(args.out),
        build_publication_plan_artifacts(plan),
        dry_run=args.dry_run,
        allow_overwrite=args.allow_overwrite,
    )
    _print_json(
        {
            "status": receipt.status,
            "plan_id": plan.plan_id,
            "plan_semantic_hash": plan.semantic_hash,
            "policy_hash": plan.policy_hash,
            "source_topology_packet_id": plan.source_topology_packet.packet_id,
            "source_topology_semantic_hash": plan.source_topology_semantic_hash,
            "counts": {
                "eligible": len(plan.eligible_candidates),
                "held": len(plan.held_candidates),
                "rejected": len(plan.rejected_candidates),
                "skipped": len(plan.skipped_candidates),
            },
            "note": (
                "publication plan only; no memory, Graphiti, or Neo4j client is "
                "present and no intent was dispatched"
            ),
            "outputs": [item.model_dump(mode="json") for item in receipt.results],
        }
    )
    return _commit_exit_code(receipt, stage="plan-publication")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="l9-topology",
        description="Packet-native L9 repository and constellation topology compiler",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    compile_parser = commands.add_parser(
        "compile-packet", help="Compile Repository Model Packet bundles"
    )
    compile_parser.add_argument("--repo-root", default=".")
    compile_parser.add_argument("--input-bundle", action="append", required=True)
    compile_parser.add_argument("--out", required=True)
    compile_parser.add_argument("--dry-run", action="store_true")
    compile_parser.add_argument("--allow-overwrite", action="store_true")
    compile_parser.set_defaults(handler=cmd_compile_packet)

    for name in ("validate-packet", "validate"):
        validate_parser = commands.add_parser(name, help="Validate a Topology Packet bundle")
        validate_parser.add_argument("--input-bundle", required=True)
        validate_parser.add_argument("--repository-bundle", action="append")
        validate_parser.set_defaults(handler=cmd_validate_packet)

    for name in ("render-report", "render"):
        render_parser = commands.add_parser(name, help="Render lazy reports from a Topology Packet")
        render_parser.add_argument("--repo-root", default=".")
        render_parser.add_argument("--input-bundle", required=True)
        render_parser.add_argument("--out", required=True)
        render_parser.add_argument("--format", action="append", choices=SUPPORTED_FORMATS)
        render_parser.add_argument("--dry-run", action="store_true")
        render_parser.add_argument("--allow-overwrite", action="store_true")
        render_parser.set_defaults(handler=cmd_render_report)

    impact_parser = commands.add_parser("impact", help="Compute bounded canonical impact")
    impact_parser.add_argument("--input-bundle", required=True)
    impact_parser.add_argument("--entity", required=True)
    impact_parser.add_argument(
        "--direction", choices=("upstream", "downstream", "both"), default="downstream"
    )
    impact_parser.add_argument("--maximum-depth", type=int, default=10)
    impact_parser.add_argument("--edge-type", action="append")
    impact_parser.add_argument(
        "--minimum-confidence", choices=("low", "medium", "high"), default="low"
    )
    impact_parser.set_defaults(handler=cmd_impact)

    inspect_parser = commands.add_parser(
        "inspect-packet", help="Inspect packet identity and record counts"
    )
    inspect_parser.add_argument("--input-bundle", required=True)
    inspect_parser.set_defaults(handler=cmd_inspect_packet)

    determinism_parser = commands.add_parser(
        "verify-determinism", help="Compile twice and compare semantic identity"
    )
    determinism_parser.add_argument("--repo-root", default=".")
    determinism_parser.add_argument("--input-bundle", action="append", required=True)
    determinism_parser.set_defaults(handler=cmd_verify_determinism)

    scan_parser = commands.add_parser(
        "scan", help="Compatibility: bounded scan through packet compiler"
    )
    scan_parser.add_argument("--repo-root", default=".")
    scan_parser.add_argument("--source-repo", required=True)
    scan_parser.add_argument("--repository-id")
    scan_parser.add_argument("--name")
    scan_parser.add_argument("--expected-role", default="UNKNOWN")
    scan_parser.add_argument("--out", required=True)
    scan_parser.add_argument("--dry-run", action="store_true")
    scan_parser.add_argument("--allow-overwrite", action="store_true")
    scan_parser.set_defaults(handler=cmd_scan)

    scan_many_parser = commands.add_parser(
        "scan-many", help="Compatibility: scan configured repositories"
    )
    scan_many_parser.add_argument("--repo-root", default=".")
    scan_many_parser.add_argument("--sources", required=True)
    scan_many_parser.add_argument("--out", required=True)
    scan_many_parser.add_argument("--dry-run", action="store_true")
    scan_many_parser.add_argument("--allow-overwrite", action="store_true")
    scan_many_parser.set_defaults(handler=cmd_scan_many)

    publication_parser = commands.add_parser(
        "plan-publication",
        help="Plan deterministic memory.ingest intents from a Topology Packet",
    )
    publication_parser.add_argument("--repo-root", default=".")
    publication_parser.add_argument("--input-bundle", required=True)
    publication_parser.add_argument("--out", required=True)
    publication_parser.add_argument("--dry-run", action="store_true")
    publication_parser.add_argument("--allow-overwrite", action="store_true")
    publication_parser.set_defaults(handler=cmd_plan_publication)

    neo4j_parser = commands.add_parser("export-neo4j", help="Render a Neo4j candidate projection")
    neo4j_parser.add_argument("--input-bundle", required=True)
    neo4j_parser.add_argument("--out", required=True)
    neo4j_parser.add_argument("--dry-run", action="store_true")
    neo4j_parser.add_argument("--allow-overwrite", action="store_true")
    neo4j_parser.set_defaults(handler=cmd_export_neo4j)
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except TopologyCompilationError as exc:
        print(str(exc), file=sys.stderr)
        print(canonical_json(exc.receipt), file=sys.stderr)
        return 2
    except BundleVerificationError as exc:
        for line in _format_verification_error(exc):
            print(line, file=sys.stderr)
        return 2
    except (PacketLoadError, ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        for line in str(exc).splitlines() or [repr(exc)]:
            print(f"ERROR: {line}", file=sys.stderr)
        return 2


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
