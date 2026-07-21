"""Legacy v4 models retained only for compatibility commands and regression tests."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Confidence(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class EdgeType(StrEnum):
    dependency = "dependency"
    governance = "governance"
    ci = "ci"
    memory = "memory"
    topology = "topology"
    runtime = "runtime"
    documentation = "documentation"


class Direction(StrEnum):
    outbound = "outbound"
    inbound = "inbound"
    bidirectional = "bidirectional"


class RecordType(StrEnum):
    node = "node"
    edge = "edge"


class SourceType(StrEnum):
    file = "file"
    inference = "inference"
    unknown = "unknown"


class EvidenceItem(BaseModel):
    source_file: str
    source_type: SourceType = SourceType.file
    excerpt: str = ""
    line_number: int | None = None


class RepoSource(BaseModel):
    repo_id: str
    name: str
    local_path: str
    remote_url: str = "UNKNOWN"
    group_id: str = "UNKNOWN"
    expected_role: str = "UNKNOWN"


class RepoCard(BaseModel):
    repo_id: str
    name: str
    path: str
    primary_role: str = "UNKNOWN"
    secondary_roles: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    ci_workflows: list[str] = Field(default_factory=list)
    adr_files: list[str] = Field(default_factory=list)
    governance_files: list[str] = Field(default_factory=list)
    upstream_dependencies: list[str] = Field(default_factory=list)
    downstream_dependents: list[str] = Field(default_factory=list)
    owner: str = "UNKNOWN"
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: Confidence = Confidence.low


class EdgeCard(BaseModel):
    source: str
    target: str
    edge_type: EdgeType
    direction: Direction = Direction.outbound
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: Confidence = Confidence.low


class FlowCard(BaseModel):
    flow_id: str
    name: str
    source_repo: str
    target_repo: str
    flow_type: str = "UNKNOWN"
    description: str = "UNKNOWN"
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: Confidence = Confidence.low


class GraphRecord(BaseModel):
    record_type: RecordType
    label: str
    id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    source_file: str = ""
    confidence: Confidence = Confidence.low


class RiskItem(BaseModel):
    risk_id: str
    repo_id: str
    severity: Literal["low", "medium", "high", "critical"]
    category: str
    description: str
    evidence: list[EvidenceItem] = Field(default_factory=list)


class MaturityScore(BaseModel):
    repo_id: str
    score: int
    band: str
    breakdown: dict[str, int] = Field(default_factory=dict)


class TopologyReport(BaseModel):
    constellation_name: str
    generated_at: str
    repo_inventory: list[RepoCard] = Field(default_factory=list)
    dependency_graph: list[EdgeCard] = Field(default_factory=list)
    intelligence_flows: list[FlowCard] = Field(default_factory=list)
    governance_topology: list[dict[str, Any]] = Field(default_factory=list)
    runtime_topology: list[dict[str, Any]] = Field(default_factory=list)
    graphiti_memory_topology: list[dict[str, Any]] = Field(default_factory=list)
    neo4j_topology_boundary: list[dict[str, Any]] = Field(default_factory=list)
    risk_register: list[RiskItem] = Field(default_factory=list)
    maturity_scorecard: list[MaturityScore] = Field(default_factory=list)
    graph_records: list[GraphRecord] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    issue_id: str
    severity: Literal["error", "warning", "info"]
    rule: str
    message: str
    path: str = ""


class ValidationResult(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    checked_at: str = ""
