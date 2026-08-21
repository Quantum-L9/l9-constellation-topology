#!/usr/bin/env python3
"""Generate checked-in JSON Schemas from canonical Pydantic contracts."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from generated_artifact_sync import GeneratedArtifact, synchronize
from pydantic import BaseModel

from l9_constellation_topology.domain import (
    ArtifactRecord,
    CapabilityRecord,
    DiagnosticRecord,
    EdgeRecord,
    FlowRecord,
    GraphRecord,
    MaturityAssessment,
    RepositoryRecord,
    RiskRecord,
)
from l9_constellation_topology.io import CommitReceipt
from l9_constellation_topology.packets import (
    ExecutionFailure,
    GitHubIngressPayload,
    PacketBundleManifest,
    RenderRequestPayload,
    RenderResult,
    ReplayRequestPayload,
    ReportManifest,
    RepositoryModelPacket,
    StageDispatchPayload,
    StageResult,
    TopologyPacket,
    TransportPacket,
    ValidationReceipt,
    ValidationRequestPayload,
)
from l9_constellation_topology.publication import PublicationPlan
from l9_constellation_topology.run import EvidenceRecord

ROOT = Path(__file__).resolve().parents[1]


def render_schema(model: type[BaseModel], schema_id: str) -> bytes:
    schema = model.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = schema_id
    return (json.dumps(schema, indent=2, sort_keys=True) + "\n").encode()


def build_schema_artifacts() -> tuple[GeneratedArtifact, ...]:
    contracts: dict[str, tuple[type[BaseModel], str]] = {
        "transport-packet.schema.json": (
            TransportPacket,
            "https://quantum-l9.dev/contracts/transport-packet.schema.json",
        ),
        "stage-dispatch.schema.json": (
            StageDispatchPayload,
            "https://quantum-l9.dev/contracts/stage-dispatch.schema.json",
        ),
        "github-ingress.schema.json": (
            GitHubIngressPayload,
            "https://quantum-l9.dev/contracts/github-ingress.schema.json",
        ),
        "replay-request.schema.json": (
            ReplayRequestPayload,
            "https://quantum-l9.dev/contracts/replay-request.schema.json",
        ),
        "render-request.schema.json": (
            RenderRequestPayload,
            "https://quantum-l9.dev/contracts/render-request.schema.json",
        ),
        "validation-request.schema.json": (
            ValidationRequestPayload,
            "https://quantum-l9.dev/contracts/validation-request.schema.json",
        ),
        "render-result.schema.json": (
            RenderResult,
            "https://quantum-l9.dev/contracts/render-result.schema.json",
        ),
        "stage-result.schema.json": (
            StageResult,
            "https://quantum-l9.dev/contracts/stage-result.schema.json",
        ),
        "execution-failure.schema.json": (
            ExecutionFailure,
            "https://quantum-l9.dev/contracts/execution-failure.schema.json",
        ),
        "repository-model-packet.schema.json": (
            RepositoryModelPacket,
            "https://quantum-l9.dev/contracts/repository-model-packet.schema.json",
        ),
        "topology-packet.schema.json": (
            TopologyPacket,
            "https://quantum-l9.dev/contracts/topology-packet.schema.json",
        ),
        "validation-receipt.schema.json": (
            ValidationReceipt,
            "https://quantum-l9.dev/contracts/validation-receipt.schema.json",
        ),
        "report-manifest.schema.json": (
            ReportManifest,
            "https://quantum-l9.dev/contracts/report-manifest.schema.json",
        ),
        "packet-bundle-manifest.schema.json": (
            PacketBundleManifest,
            "https://quantum-l9.dev/contracts/packet-bundle-manifest.schema.json",
        ),
        "commit-receipt.schema.json": (
            CommitReceipt,
            "https://quantum-l9.dev/contracts/commit-receipt.schema.json",
        ),
    }
    domain: dict[str, tuple[type[BaseModel], str]] = {
        "repository-record.schema.json": (
            RepositoryRecord,
            "https://quantum-l9.dev/schemas/repository-record.schema.json",
        ),
        "artifact-record.schema.json": (
            ArtifactRecord,
            "https://quantum-l9.dev/schemas/artifact-record.schema.json",
        ),
        "capability-record.schema.json": (
            CapabilityRecord,
            "https://quantum-l9.dev/schemas/capability-record.schema.json",
        ),
        "edge-record.schema.json": (
            EdgeRecord,
            "https://quantum-l9.dev/schemas/edge-record.schema.json",
        ),
        "flow-record.schema.json": (
            FlowRecord,
            "https://quantum-l9.dev/schemas/flow-record.schema.json",
        ),
        "graph-record.schema.json": (
            GraphRecord,
            "https://quantum-l9.dev/schemas/graph-record.schema.json",
        ),
        "diagnostic-record.schema.json": (
            DiagnosticRecord,
            "https://quantum-l9.dev/schemas/diagnostic-record.schema.json",
        ),
        "evidence-record.schema.json": (
            EvidenceRecord,
            "https://quantum-l9.dev/schemas/evidence-record.schema.json",
        ),
        "risk-record.schema.json": (
            RiskRecord,
            "https://quantum-l9.dev/schemas/risk-record.schema.json",
        ),
        "maturity-assessment.schema.json": (
            MaturityAssessment,
            "https://quantum-l9.dev/schemas/maturity-assessment.schema.json",
        ),
        # The publication plan is a derived artifact, not canonical packet truth,
        # so it lives beside the record schemas. Adding it to contracts/ would
        # change schema_contract_hash and therefore every Topology Packet's
        # semantic identity, which the canonicality invariant forbids.
        "topology-publication-plan.schema.json": (
            PublicationPlan,
            "https://quantum-l9.dev/schemas/topology-publication-plan.schema.json",
        ),
    }
    return tuple(
        GeneratedArtifact(ROOT / directory / name, render_schema(model, schema_id))
        for directory, definitions in (("contracts", contracts), ("schemas", domain))
        for name, (model, schema_id) in definitions.items()
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when checked-in schemas differ; never modify files.",
    )
    args = parser.parse_args(argv)
    findings = synchronize(build_schema_artifacts(), check=args.check)
    if args.check and findings:
        for finding in findings:
            print(f"{finding.kind}: {finding.path.relative_to(ROOT)}")
        return 1
    if not args.check:
        for finding in findings:
            print(f"updated: {finding.path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
