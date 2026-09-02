from __future__ import annotations

import json
from datetime import UTC, datetime

from l9_constellation_topology.domain import (
    CapabilityRecord,
    ConfidenceAssessment,
    TopologyState,
)
from l9_constellation_topology.packets import (
    MaterializedTopology,
    PacketValidationRef,
    Producer,
    ProfileRef,
    TopologyInputs,
    TopologyPacket,
)
from l9_constellation_topology.renderers import render_reports


def _materialized() -> MaterializedTopology:
    capability = CapabilityRecord(
        capability_id="capability:planner",
        name="planner",
        description="Plans work.",
        implemented_by=("artifact:planner",),
        evidence_refs=("evidence:planner",),
        confidence=ConfidenceAssessment.direct(),
    )
    state = TopologyState(capability_records=(capability,))
    packet = TopologyPacket(
        packet_id="packet:topology",
        inputs=TopologyInputs(repository_model_packets=()),
        validation=PacketValidationRef(status="passed", receipt_ref="packet://receipt"),
        producer=Producer(name="test", version="1.0.0"),
        profile=ProfileRef(id="topology", version="1.0.0", hash="sha256:profile"),
        schema_hash="sha256:schema",
        policy_hashes={},
        payload_refs={},
        payload_hashes={},
        semantic_hash="sha256:topology",
        artifact_hash="sha256:artifact",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return MaterializedTopology(packet=packet, state=state)


def test_bridge_gap_reports_are_lazy_manifested_artifacts() -> None:
    projection = render_reports(
        _materialized(),
        formats=("bridge-gaps-json", "bridge-gaps-markdown"),
        report_profile_hash="sha256:report-profile",
    )

    assert [item.uri for item in projection.manifest.reports] == [
        "bridge-gaps.json",
        "BRIDGE_GAPS.md",
    ]
    artifacts = {item.destination_path: item for item in projection.artifacts}
    payload = json.loads(artifacts["bridge-gaps.json"].content)
    assert payload["schema_version"] == "l9.bridge-gap-projection/v1"
    assert payload["gaps"][0]["gap_type"] == "BUILT_UNREACHABLE"
    markdown = artifacts["BRIDGE_GAPS.md"].content.decode("utf-8")
    assert "Decision-support projection only" in markdown
    assert "BUILT_UNREACHABLE" in markdown
    assert "report-manifest.json" in artifacts
