#!/usr/bin/env python3
"""Generate checked-in JSON Schemas from canonical Pydantic contracts."""

from __future__ import annotations

import json
from pathlib import Path

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
from l9_constellation_topology.run import EvidenceRecord

ROOT = Path(__file__).resolve().parents[1]


def write_schema(model: type[BaseModel], destination: Path, schema_id: str) -> None:
    schema = model.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = schema_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
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
    }
    for name, (model, schema_id) in contracts.items():
        write_schema(model, ROOT / "contracts" / name, schema_id)
    for name, (model, schema_id) in domain.items():
        write_schema(model, ROOT / "schemas" / name, schema_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
