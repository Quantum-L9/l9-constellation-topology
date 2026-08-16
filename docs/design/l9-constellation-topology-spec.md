> **Status note — publication boundary superseded.**
>
> This design specification predates [ADR-0021](../adr/0021-internalize-publication-planning-and-memory-lowering.md).
> Wherever it names `l9-topology-ingestion-bridge` as the component that owns
> evidence-gated lowering, promotion policy, or effect planning, it describes the
> **superseded** architecture of [ADR-0020](../adr/0020-delegate-publication-planning-to-the-ingestion-bridge.md).
> That repository was never built, and no separate ingestion-bridge component is a
> required runtime component of the current system.
>
> Publication planning is now an **internal module** of this repository at
> `src/l9_constellation_topology/publication/`, reached through the
> `plan-publication` command, and its output is the derived
> `l9.topology-publication-plan`. The authority split ADR-0020 protected is
> unchanged and is now a split between planning and execution rather than between
> two repositories: durable admission remains owned by `l9-graphiti-memory`, and
> this repository still contains no Neo4j client, no Graphiti client, no memory
> service client, and no Gate dispatch.
>
> The current pipeline is:
>
> ```text
> l9-meta-injector
>         ↓ l9.repository-model
> l9-constellation-topology
>         ↓ l9.topology
> internal publication planning
>         ↓ l9.topology-publication-plan
> external downstream admission and execution
> ```
>
> Everything else in this document — the packet contracts, evidence model, worker
> execution model, and compiler stages — remains current. See
> [docs/publication-boundary.md](../publication-boundary.md) and
> [ARCHITECTURE.md](../../ARCHITECTURE.md) for the authoritative current description.

Below is the superseding implementation specification for l9-constellation-topology. It replaces the earlier sealed contract with the recursively refined packet-first, evidence-backed, Postgres-orchestrated Model B architecture.

L9 Constellation Topology

Canonical Repository Topology Compiler and Packet-Native Autonomous Pipeline Specification

Specification ID: l9.constellation-topology.spec
Specification Version: 5.0.0
Status: Proposed superseding contract
Supersedes: l9_constellation_topology_nuclear_coding_contract v4.0.0
Target Repository: Quantum-L9/l9-constellation-topology
Primary Runtime: Python 3.12+
Primary Execution Model: GitHub Actions workers orchestrated by a durable Postgres control plane
Transport Standard: TransportPacket
Primary Input: validated Repository Model Packets
Primary Output: validated Topology Packets
Source Mutation Policy: read-only by default
Canonical Principle: evidence over inference; packets over reports; planned effects over direct writes

⸻

1. Executive Objective

l9-constellation-topology shall become the deterministic middle-end compiler in the foundational L9 repository-intelligence pipeline.

Its responsibility is to consume one or more validated Repository Model Packets, combine them with bounded direct repository observations where necessary, construct a canonical repository and constellation topology, evaluate relationships, impact, maturity, risk, governance, and evidence quality, and emit a validated immutable Topology Packet.

The repository shall no longer be primarily understood as a scanner that emits a directory of reports.

It shall be understood as:

A packet-native topology compiler that transforms validated repository-semantic inputs into a canonical, evidence-backed, graphable topology representation.

The foundational pipeline is:

Source repositories
        ↓
l9-meta-injector
        ↓
Repository Model Packet
        ↓
l9-constellation-topology
        ↓
Topology Packet
        ↓
l9-topology-ingestion-bridge   [SUPERSEDED by ADR-0021: this stage is now the
                                internal publication/ module of this repository]
        ↓
Promotion Plan / Candidate / Publication Receipt Packets
        [current: l9.topology-publication-plan]

The complete autonomous execution path is:

GitHub repository event
        ↓
GitHub Actions ingress
        ↓
TransportPacket task declaration
        ↓
Postgres workflow control plane
        ↓
GitHub Actions stage worker
        ↓
Repository Model Packet consumption
        ↓
Topology compilation
        ↓
Topology Packet publication
        ↓
stage-result callback
        ↓
Postgres dependency resolution
        ↓
ingestion-planning stage activation

The current topology implementation already provides repository scanning, evidence records, graph records, impact analysis, maturity scoring, risk assessment, validation, and multiple renderers. This specification preserves those strengths while replacing directory-coupled input, incremental direct writes, report-to-report handoffs, and coarse evidence semantics with canonical packets, typed stage contracts, a run signal plane, pure renderers, and policy-governed output sinks.

⸻

2. Architectural Role

2.1 Position in the compiler stack

The three foundational repositories have separate responsibilities.

l9-meta-injector

Owns artifact-level understanding:

files
→ observations
→ artifact classification
→ semantic extraction
→ normalized metadata
→ artifact relationships
→ evidence records
→ Repository Model Packet

l9-constellation-topology

Owns repository- and constellation-level understanding:

Repository Model Packets
+ bounded repository observations
→ repository aggregation
→ capability topology
→ dependency relationships
→ governance topology
→ risk and maturity
→ impact graph
→ Topology Packet

l9-topology-ingestion-bridge — **superseded by ADR-0021**

Owned evidence-gated lowering and publication planning. Those responsibilities are
now discharged by the internal `publication/` module of this repository; the
stage description below still holds, but it is an internal boundary rather than a
separate repository:

Topology Packet
→ evidence gate
→ promotion policy
→ effect planning
→ candidate routing
→ Graphiti / Neo4j destination records
→ receipt packets

These repositories shall communicate through versioned packets rather than direct package dependencies, shared filesystem assumptions, or informal neighboring report files.

2.2 Repository boundary

l9-constellation-topology shall:

* consume validated Repository Model Packets;
* optionally perform bounded direct scans for missing topology evidence;
* aggregate artifact semantics into repository semantics;
* generate graph nodes, edges, flows, risks, maturity, and impact;
* validate all outputs before persistence;
* produce immutable Topology Packets;
* render human projections from packets on demand;
* remain read-only against source repositories;
* remain independent of Neo4j and Graphiti write APIs;
* expose candidate graph records but not perform canonical graph promotion;
* report unknowns and conflicts honestly;
* integrate with Postgres orchestration through GitHub Actions callbacks.

It shall not:

* own source metadata injection;
* write directly to Neo4j;
* write directly to Graphiti;
* silently promote inferred claims to canonical facts;
* mutate scanned source repositories;
* use Markdown, CSV, YAML, or Mermaid reports as stage-to-stage transport;
* require the full L9 Gate for foundational-pipeline operation;
* store large packet payloads in GitHub dispatch events;
* call GitHub directly from database triggers;
* distribute filesystem writes across scanner, renderer, CLI, or validation modules.

⸻

3. Core Design Doctrine

3.1 Canonical Repository Model

The Canonical Repository Model is the shared semantic core of the foundational pipeline.

It is a logical model of:

repositories
artifacts
modules
capabilities
commands
dependencies
governance
ownership
decisions
tests
workflows
evidence
validation
generated projections

The model is not one database and not one large JSON document permanently stored in Neo4j.

Its authoritative state is intentionally distributed:

Layer	Responsibility
Source repository	human-declared source authority
Repository Model Packet	immutable artifact-level machine evidence
Topology Packet	immutable repository and constellation topology
Canonical graph	accepted current relationships and packet pointers
Temporal memory	recent observations, rationale, conflicts, and history
Candidate queue	unresolved or insufficiently evidenced claims
Reports	human-readable projections of packets

l9-constellation-topology consumes Repository Model Packets and produces the topology projection of the Canonical Repository Model.

3.2 Run Signal Plane

Every compilation run shall maintain a run-scoped signal plane.

The signal plane records:

* discovered inputs;
* source snapshots;
* packet identities;
* validation receipts;
* stage inputs and outputs;
* evidence;
* derivations;
* conflicts;
* unknowns;
* diagnostics;
* rendered artifacts;
* write intents;
* write plans;
* commit receipts;
* output packet lineage.

The signal plane is not a global mutable singleton.

It is represented through explicit typed objects passed between stages.

3.3 OutputSink

All external effects shall pass through one OutputSink boundary.

Modules shall produce RenderedArtifact and WriteIntent values.

They shall not call filesystem mutation APIs directly.

The sink shall:

* normalize paths;
* enforce output-root containment;
* enforce artifact-kind policy;
* detect collisions;
* compare existing content;
* skip unchanged outputs;
* validate expected existing hashes;
* stage atomic writes;
* commit through one controlled boundary;
* emit a commit receipt;
* support dry-run planning;
* support in-memory testing.

3.4 Packets, not reports

Stages pass packets.

Reports are optional projections of packets.

The ingestion bridge shall consume a validated Topology Packet, not a loose combination of:

topology_report.json
graph_records.jsonl
evidence_hashes.json
repo_inventory.yaml

Those existing outputs are an informal packet and shall be formalized into one typed packet bundle.

3.5 Determinism

The same semantic inputs, compiler version, policy version, and profile shall produce the same semantic output hash.

Exact emitted bytes may differ where explicitly permitted, such as timestamps in a human report.

The system shall distinguish:

semantic hash
    excludes non-semantic timestamps, machine-local paths,
    transient execution identifiers, and presentation ordering
artifact hash
    hashes the exact emitted bytes

Absolute local paths shall not participate in semantic identity.

Source paths shall be normalized relative to an explicitly declared repository root.

⸻

4. TransportPacket Integration

TransportPacket is the only supported control-plane wire shape for foundational pipeline traffic.

It already defines:

* packet identity;
* addressing;
* tenancy;
* governance;
* provenance;
* delegation;
* security hashes;
* signatures;
* attachments;
* hop trace;
* semantic lineage.

Semantic changes use derive() and create a new packet identity.

Observational changes use with_hop() and do not alter the semantic transport hash.

4.1 TransportPacket use in this repository

l9-constellation-topology shall receive and emit the following TransportPacket payload contracts.

Accepted incoming payloads

l9.stage-dispatch/1.0.0
l9.repository-model-ref/1.0.0
l9.replay-request/1.0.0
l9.render-request/1.0.0
l9.validation-request/1.0.0

Emitted payloads

l9.topology-ref/1.0.0
l9.stage-result/1.0.0
l9.execution-failure/1.0.0
l9.validation-receipt/1.0.0
l9.render-result/1.0.0
l9.reuse-receipt/1.0.0

Large payloads shall be referenced through attachments.

The current attachment contract already supports content hash, URI, media type, encryption state, and size, and shall be used for Repository Model Packets, Topology Packets, evidence collections, and reports.

4.2 Required header profile

The foundational topology profile shall require:

{
  "header": {
    "packet_type": "command",
    "action": "compile-topology",
    "schema_version": "transport-packet/1.0.0",
    "idempotency_key": "sha256:...",
    "trace_id": "workflow-run-id",
    "correlation_id": "pipeline-run-id"
  }
}

The final transport implementation should add or conventionally require:

header.payload_schema
header.workflow_id

Until those are first-class fields, the payload shall begin with:

{
  "payload_schema": "l9.stage-dispatch/1.0.0",
  "data": {}
}

4.3 Gate-less foundational profile

The full Gate is not required during the foundational deployment.

Execution authority is temporarily resolved through:

* trusted GitHub Actions workflows;
* GitHub App installation identity;
* packet signatures;
* exact repository allowlists;
* exact workflow allowlists;
* action allowlists;
* schema validation;
* validated parent-packet requirements;
* Postgres dispatch policy.

provenance.resolved_by_gate shall remain false.

The execution record shall identify the temporary resolver:

{
  "payload_schema": "l9.stage-dispatch/1.0.0",
  "data": {
    "resolution": {
      "authority": "github-actions-postgres-control-plane",
      "resolver": "l9-ci-core",
      "gate_required": false
    }
  }
}

No transport-schema fork shall be introduced solely to support the Gate-less phase.

⸻

5. Packet Contracts

5.1 Repository Model Packet input

The topology compiler shall accept one or more validated Repository Model Packets.

A Repository Model Packet shall contain or reference:

packet manifest
repository identity
source revision
repository semantic hash
artifact records
module records
capability records
relationship records
evidence records
diagnostics
validation receipt
producer identity and version
profile hash
schema hash

Minimum required fields:

{
  "packet_type": "l9.repository-model",
  "packet_version": "1.0.0",
  "packet_id": "packet:sha256:...",
  "subject": {
    "repository_id": "repo:l9-meta-injector"
  },
  "source_snapshot": {
    "revision": "git:...",
    "semantic_hash": "sha256:..."
  },
  "validation": {
    "status": "passed",
    "receipt_ref": "packet://..."
  },
  "payload_refs": {
    "artifacts": "packet://...",
    "relationships": "packet://...",
    "evidence": "packet://..."
  }
}

5.2 Topology Packet output

A Topology Packet is the sole canonical machine output of the topology compilation stage.

It shall contain:

packet manifest
compiler identity
compiler version
profile identity
input packet references
repository inventory
artifact aggregation
capability topology
dependency graph
governance topology
documentation topology
CI topology
runtime topology
memory topology
edge records
flow records
graph records
risk register
maturity scorecard
impact indexes
unknowns
conflicts
evidence records
validation receipt
semantic hash
artifact hash
lineage

Minimum structure:

{
  "packet_type": "l9.topology",
  "packet_version": "1.0.0",
  "packet_id": "packet:sha256:...",
  "producer": {
    "name": "l9-constellation-topology",
    "version": "2.0.0"
  },
  "profile": {
    "id": "foundational-topology",
    "version": "1.0.0",
    "hash": "sha256:..."
  },
  "inputs": {
    "repository_model_packets": [
      {
        "packet_id": "packet:...",
        "semantic_hash": "sha256:...",
        "subject_id": "repo:l9-meta-injector"
      }
    ]
  },
  "payload_refs": {
    "repository_records": "packet://...",
    "artifact_records": "packet://...",
    "capability_records": "packet://...",
    "edge_records": "packet://...",
    "flow_records": "packet://...",
    "graph_records": "packet://...",
    "risks": "packet://...",
    "maturity": "packet://...",
    "evidence": "packet://..."
  },
  "validation": {
    "status": "passed",
    "receipt_ref": "packet://..."
  },
  "semantic_hash": "sha256:...",
  "artifact_hash": "sha256:..."
}

5.3 Validation Receipt Packet

Validation shall not mutate the packet under validation.

It shall produce a separate immutable receipt:

{
  "packet_type": "l9.validation-receipt",
  "packet_version": "1.0.0",
  "subject_packet_id": "packet:...",
  "validator": {
    "name": "l9-constellation-topology",
    "version": "2.0.0"
  },
  "status": "passed",
  "schema_results": [],
  "invariant_results": [],
  "evidence_results": [],
  "cross_reference_results": [],
  "created_at": "...",
  "semantic_hash": "sha256:..."
}

A downstream stage shall require both:

Topology Packet
Validation Receipt with status=passed

5.4 Report Manifest Packet

Reports shall be represented through a report-manifest payload that references projections:

{
  "packet_type": "l9.report-manifest",
  "packet_version": "1.0.0",
  "source_packet_id": "packet:topology:...",
  "renderer": {
    "id": "l9-topology-renderer",
    "version": "2.0.0"
  },
  "reports": [
    {
      "report_type": "topology-markdown",
      "uri": "packet://...",
      "content_hash": "sha256:...",
      "media_type": "text/markdown"
    }
  ]
}

Reports shall not be required inputs for topology ingestion.

⸻

6. Internal Domain Model

6.1 Run context

class RunContext(BaseModel):
    run_id: str
    stage_id: str
    workflow_id: str
    trace_id: str
    compiler_version: str
    profile_id: str
    profile_hash: str
    source_snapshot_hash: str
    input_packet_refs: list["PacketRef"]
    artifacts: dict[str, "ArtifactState"]
    evidence: list["EvidenceRecord"]
    diagnostics: list["Diagnostic"]
    stage_receipts: list["StageReceipt"]

6.2 EvidenceRecord

The existing EvidenceItem model is useful but too coarse for the canonical signal plane.

It shall evolve to:

class EvidenceRecord(BaseModel):
    evidence_id: str
    subject_id: str
    field: str | None = None
    stage: str
    evidence_class: Literal[
        "observed",
        "declared",
        "derived",
        "assisted",
        "projected",
        "validated",
        "committed",
    ]
    source_type: Literal[
        "file",
        "packet",
        "inference",
        "validation",
        "unknown",
    ]
    source_ref: "EvidenceSourceRef"
    value: Any
    confidence: "ConfidenceAssessment"
    producer: str
    producer_version: str
    created_at: datetime

6.3 ConfidenceAssessment

Replace the single low/medium/high confidence field as the sole trust model.

class ConfidenceAssessment(BaseModel):
    level: Literal["low", "medium", "high"]
    evidence_strength: Literal["none", "weak", "corroborated", "direct"]
    derivation_method: Literal[
        "declared",
        "deterministic",
        "cross-record",
        "heuristic",
        "model-assisted",
        "unknown",
    ]
    authority: Literal[
        "source",
        "validated-machine",
        "derived",
        "candidate",
        "unknown",
    ]
    completeness: Literal["partial", "sufficient", "complete"]
    conflict_status: Literal["none", "possible", "confirmed"]

Low/medium/high remains available for compatibility and routing, but canonical decisions shall consider the decomposed fields.

6.4 RepositoryRecord

RepoCard shall evolve without immediately breaking compatibility.

class RepositoryRecord(BaseModel):
    repository_id: str
    name: str
    source_revision: str
    packet_ref: str
    primary_role: str
    secondary_roles: list[str]
    languages: list[str]
    package_managers: list[str]
    entrypoints: list[str]
    workflows: list[str]
    adr_refs: list[str]
    governance_refs: list[str]
    capability_ids: list[str]
    artifact_ids: list[str]
    upstream_repository_ids: list[str]
    downstream_repository_ids: list[str]
    owner_ids: list[str]
    evidence_refs: list[str]
    confidence: ConfidenceAssessment

6.5 ArtifactRecord

class ArtifactRecord(BaseModel):
    artifact_id: str
    repository_id: str
    source_path: str
    artifact_type: str
    family: str | None
    content_hash: str
    body_hash: str | None
    capabilities: list[str]
    dependencies: list[str]
    evidence_refs: list[str]
    packet_ref: str
    confidence: ConfidenceAssessment

6.6 CapabilityRecord

class CapabilityRecord(BaseModel):
    capability_id: str
    name: str
    description: str
    implemented_by: list[str]
    exposed_by: list[str]
    validated_by: list[str]
    governed_by: list[str]
    evidence_refs: list[str]
    confidence: ConfidenceAssessment

6.7 EdgeRecord

The current edge taxonomy shall be expanded and versioned.

class EdgeRecord(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    edge_type: Literal[
        "CONTAINS",
        "DEPENDS_ON",
        "IMPLEMENTS",
        "EXPOSES",
        "VALIDATED_BY",
        "GOVERNED_BY",
        "OWNED_BY",
        "DOCUMENTED_BY",
        "PRODUCES",
        "CONSUMES",
        "DERIVED_FROM",
        "SUPERSEDES",
        "ROUTES_TO",
        "PUBLISHES_TO",
        "MEMBER_OF",
    ]
    direction: Literal["outbound", "inbound", "bidirectional"]
    properties: dict[str, Any]
    evidence_refs: list[str]
    confidence: ConfidenceAssessment

6.8 FlowRecord

class FlowRecord(BaseModel):
    flow_id: str
    name: str
    source_id: str
    target_id: str
    flow_type: str
    packet_type: str | None
    description: str
    stage_sequence: list[str]
    evidence_refs: list[str]
    confidence: ConfidenceAssessment

6.9 RiskRecord

Risk records shall include policy identity and remediation state.

class RiskRecord(BaseModel):
    risk_id: str
    subject_id: str
    severity: Literal["low", "medium", "high", "critical"]
    category: str
    description: str
    rule_id: str
    rule_version: str
    evidence_refs: list[str]
    remediation: str | None
    status: Literal["open", "accepted", "mitigated", "resolved"]

6.10 MaturityAssessment

The existing fixed score shall become profile-based.

class MaturityAssessment(BaseModel):
    subject_id: str
    profile_id: str
    profile_version: str
    score: int
    maximum_score: int
    band: str
    dimensions: dict[str, int]
    evidence_refs: list[str]

The current scoring profile may remain available as:

legacy-maturity-v1

but shall not be hard-coded as the only maturity definition.

⸻

7. Compilation Stages

The compiler shall use explicit stages.

resolve configuration
→ ingest packet references
→ validate input packets
→ normalize repository models
→ perform bounded direct observation
→ reconcile evidence
→ aggregate repositories
→ classify roles
→ aggregate capabilities
→ build graph
→ calculate impact
→ assess maturity
→ assess risk
→ validate topology
→ render packet
→ plan outputs
→ commit outputs
→ emit stage result

7.1 Configuration resolution

Inputs:

* stage dispatch packet;
* compiler profile;
* topology-role taxonomy;
* scanner policy;
* risk profile;
* maturity profile;
* output policy;
* report profile.

Outputs:

* resolved configuration;
* configuration hash;
* active contract versions;
* policy hashes;
* validation errors.

Invalid combinations shall fail before packet loading.

7.2 Packet input resolution

The compiler shall:

1. read packet references from the dispatch payload;
2. fetch packet bundles;
3. verify attachment hashes;
4. validate transport signatures where required;
5. validate packet schemas;
6. validate parent validation receipts;
7. ensure repository IDs are allowlisted;
8. ensure source revisions are present;
9. ensure duplicate or conflicting packet versions are explicitly resolved.

7.3 Repository model normalization

Repository Model Packets from different producer versions shall be adapted into the current internal canonical model through versioned adapters.

RepositoryModelV1Adapter
RepositoryModelV2Adapter

Unsupported versions shall fail closed.

7.4 Direct observation fallback

The topology compiler may scan source repositories only when:

* the profile permits fallback scanning;
* the exact source revision is available;
* the Repository Model Packet lacks a required topology signal;
* the observation can be performed deterministically;
* the result is marked as newly observed topology evidence;
* the result does not silently override packet evidence.

Direct scans shall remain read-only.

7.5 Evidence reconciliation

The authority order is:

human-declared source
> validated Repository Model Packet evidence
> deterministic direct observation
> cross-record deterministic derivation
> heuristic derivation
> model-assisted inference
> prior generated topology

Conflicts shall produce conflict records.

They shall not be resolved by arbitrary last-write-wins behavior.

7.6 Repository aggregation

Artifacts and capabilities shall be aggregated by repository.

The compiler must not repeat the current fixture defect where a directory containing multiple repositories is represented as one repository node.

A constellation root containing:

sample_constellation/
├── l9-gate-sdk/
└── l9-mcp-server/

must produce two repository nodes unless the operator explicitly declares the containing directory itself to be one repository.

Repository boundaries shall be established by:

1. Repository Model Packet subject identity;
2. explicit repository registry;
3. .git boundary;
4. explicit manifest declaration;
5. configured fallback rules.

7.7 Capability topology

The compiler shall build capability relationships from artifact-level signals.

Examples:

Repository IMPLEMENTS Capability
Artifact IMPLEMENTS Capability
Capability VALIDATED_BY Test
Capability GOVERNED_BY ADR
Capability DOCUMENTED_BY README section
Capability DEPENDS_ON Capability

7.8 Graph construction

Graph construction shall be pure.

It accepts canonical records and returns graph records.

It shall not write files.

Stable graph identity shall be based on canonical entity IDs, not absolute local paths.

7.9 Impact analysis

Impact shall support:

* upstream traversal;
* downstream traversal;
* bounded depth;
* edge-type filters;
* confidence filters;
* packet-version scoping;
* current versus historical topology;
* affected repository summary;
* affected capability summary;
* unresolved edge warnings.

7.10 Maturity assessment

Maturity is a projection, not canonical truth.

Profiles shall define:

* dimensions;
* weights;
* evidence requirements;
* maximum score;
* band boundaries;
* unknown handling;
* conflict handling.

7.11 Risk assessment

Risk rules shall be configuration-driven.

Examples:

missing CI
missing governance
missing ADR
low evidence quality
dependency isolation
stale repository packet
conflicting repository identity
unvalidated packet dependency
missing owner
unresolved candidate relationship
packet lineage break
non-deterministic output

7.12 Topology validation

Validation shall include:

Schema validation

* packet manifest;
* repository records;
* artifact records;
* capability records;
* edge records;
* flow records;
* risk records;
* maturity records;
* evidence records.

Invariant validation

* every edge endpoint exists;
* every evidence reference resolves;
* every repository has one canonical identity;
* no duplicate current packet per repository/profile;
* no graph record points to an unsupported packet version;
* no source-local absolute path is part of semantic identity;
* no accepted fact lacks evidence;
* inference is not marked as declared;
* packet lineage is valid;
* source revisions are present;
* semantic hashes are reproducible;
* graph cycles are either allowed by edge type or reported;
* validation receipt corresponds to exact packet semantic hash.

Cross-packet validation

* input packet validation status is passed;
* input semantic hashes match references;
* repository identities do not conflict;
* source revisions are compatible with the compilation profile;
* all required repositories are present for full-topology profiles.

⸻

8. OutputSink Architecture

8.1 Required contract

class OutputSink(Protocol):
    def enqueue(self, intent: WriteIntent) -> None: ...
    def plan(self) -> WritePlan: ...
    def commit(self) -> CommitReceipt: ...
    def clear(self) -> None: ...

8.2 RenderedArtifact

class RenderedArtifact(BaseModel):
    logical_id: str
    destination_path: str
    artifact_kind: Literal[
        "topology-packet",
        "validation-receipt",
        "report-manifest",
        "human-report",
        "graph-export",
        "risk-report",
        "maturity-report",
        "diagram",
        "debug-artifact",
        "commit-receipt",
    ]
    media_type: str
    content: bytes
    content_hash: str
    semantic_hash: str | None
    source_refs: list[str]

8.3 Write policy

class WritePolicy(BaseModel):
    mode: Literal["dry-run", "write"]
    allowed_output_roots: list[str]
    allowed_artifact_kinds: list[str]
    allow_overwrite: bool
    require_expected_hash_for_replace: bool
    enforce_path_containment: bool
    reject_collisions: bool
    atomic_writes: bool
    maximum_output_count: int
    maximum_output_bytes: int

8.4 Required sink implementations

MemoryOutputSink
FileSystemOutputSink
PacketBundleOutputSink
CompositeOutputSink

Future optional sinks:

OCIOutputSink
ObjectStoreOutputSink

The topology compiler itself shall not know GHCR credentials or registry implementation details.

Packet publication may occur through the GitHub Actions worker or a publishing adapter after local packet construction.

8.5 Atomicity

Filesystem commit is atomic per file, not globally transactional.

The commit receipt shall report partial failures honestly.

Packet publication shall not be reported as successful until all required packet objects and their manifest have been persisted and verified.

8.6 Architectural enforcement

Production source outside approved sink adapter modules shall not use:

Path.write_text
Path.write_bytes
open(..., "w")
open(..., "a")
os.rename
os.remove
shutil.rmtree

An architecture test or lint rule shall enforce this boundary.

⸻

9. Report Lifecycle

Reports are projections of a Topology Packet.

They shall not be canonical stage inputs.

9.1 Report classes

Class	Examples	Authority	Storage	Downstream contract use
Canonical machine artifact	Topology Packet, validation receipt	machine-canonical	packet store	allowed
Human projection	Markdown topology report, Mermaid diagram	derived	cache or packet attachment	prohibited as stage contract
Execution report	validation report, write-plan report	execution evidence	packet store	allowed
Repository-managed document	architecture docs, generated README section	mixed	Git repository	allowed with freshness check
Debug artifact	verbose logs, temporary diffs	diagnostic	ephemeral store	prohibited
Candidate report	unresolved relationships, evidence gaps	unpromoted	candidate store	review-only

9.2 Default projections

The topology compiler may render:

topology_report.md
architecture_diagrams.mmd
maturity_scorecard.csv
risk_register.md
repo_inventory.yaml
dependency_graph.json
neo4j_candidate.jsonl

These shall be produced on demand or according to a report profile.

They shall not always be regenerated during every topology compile.

9.3 Projection cache key

topology packet semantic hash
+ renderer ID
+ renderer version
+ report profile hash

If unchanged, the prior projection may be reused.

9.4 Repository-managed updates

Generated updates to:

README.md
AGENTS.md
docs/architecture.md
docs/adr/**

shall use managed sections or create-only ownership.

They shall require:

* expected existing hash;
* diff preview;
* evidence references;
* OutputSink approval;
* PR-based update flow;
* normal branch validation.

The topology repository shall not directly push generated documentation to main.

⸻

10. Model B Orchestration

10.1 Operating model

Postgres controls workflow state and dependencies.

GitHub Actions provides ephemeral execution workers.

Postgres
    decides next runnable stage
Dispatcher
    invokes GitHub workflow
GitHub Actions
    executes exact stage at exact source revision
Worker
    publishes packet and reports result
Postgres
    commits stage result and activates dependents

GitHub Actions remains the repository authority and worker runtime.

Postgres becomes the durable scheduler, retry engine, packet registry, and global workflow state.

10.2 Pipeline stages

For the foundational chain:

pipeline_id: foundational-repository-intelligence
version: 1.0.0
stages:
  - id: compile-repository-model
    target_repo: Quantum-L9/l9-meta-injector
    output_packet_type: l9.repository-model
  - id: compile-topology
    target_repo: Quantum-L9/l9-constellation-topology
    depends_on:
      - compile-repository-model
    requires:
      packet_type: l9.repository-model
      validation_status: passed
    output_packet_type: l9.topology
  # SUPERSEDED by ADR-0021: publication planning is an internal stage of
  # Quantum-L9/l9-constellation-topology and emits l9.topology-publication-plan.
  - id: plan-ingestion
    target_repo: Quantum-L9/l9-topology-ingestion-bridge
    depends_on:
      - compile-topology
    requires:
      packet_type: l9.topology
      validation_status: passed
    output_packet_type: l9.effect-plan

The topology stage becomes runnable because a validated Repository Model Packet exists, not merely because an upstream GitHub workflow completed.

10.3 Topology worker dispatch payload

{
  "payload_schema": "l9.stage-dispatch/1.0.0",
  "data": {
    "run_id": "uuid",
    "stage_id": "uuid",
    "workflow_id": "foundational-repository-intelligence",
    "action": "compile-topology",
    "target_repository": "Quantum-L9/l9-constellation-topology",
    "target_revision": "git-sha",
    "input_packets": [
      {
        "packet_id": "packet:...",
        "packet_type": "l9.repository-model",
        "uri": "oci://...",
        "semantic_hash": "sha256:...",
        "validation_status": "passed"
      }
    ],
    "profile": {
      "id": "foundational-topology",
      "version": "1.0.0",
      "hash": "sha256:..."
    },
    "callback": {
      "url": "https://control.example/v1/stages/{stage_id}",
      "token_ref": "ephemeral"
    }
  }
}

10.4 Idempotency key

Topology compilation idempotency shall be:

packet type
+ sorted input repository-model semantic hashes
+ topology compiler version
+ topology profile hash
+ schema contract hash

If an already validated Topology Packet exists for the same idempotency key:

skip execution
emit reuse receipt
return existing packet reference

10.5 Retry policy

Default:

max_attempts: 3
retryable_errors:
  - github-dispatch-timeout
  - packet-download-timeout
  - temporary-registry-error
  - runner-capacity
  - callback-timeout
non_retryable_errors:
  - packet-schema-invalid
  - packet-signature-invalid
  - input-validation-failed
  - unsupported-contract-version
  - topology-invariant-failed
  - semantic-hash-mismatch

10.6 Dead letters

After retry exhaustion, the stage shall be moved to the dead-letter store with:

* run ID;
* stage ID;
* input packet refs;
* last TransportPacket;
* error classification;
* attempt count;
* GitHub run references;
* required operator action.

10.7 Reconciliation

Scheduled reconciliation shall detect:

validated repository-model packet with no derived topology packet
ready topology stage not dispatched
dispatched stage with expired lease
completed GitHub run without callback
packet registered but stage not completed
topology packet published without validation receipt
superseded input packet used as current input

⸻

11. Repository File Plan

11.1 Target structure

l9-constellation-topology/
├── .github/
│   └── workflows/
│       ├── l9-pr-validate.yml
│       ├── l9-ingress.yml
│       ├── l9-stage-worker.yml
│       └── l9-manual-replay.yml
│
├── .l9/
│   ├── pipeline.yaml
│   ├── packet-profile.yaml
│   ├── topology-profile.yaml
│   ├── report-profile.yaml
│   ├── risk-profile.yaml
│   └── maturity-profile.yaml
│
├── contracts/
│   ├── transport-packet.schema.json
│   ├── stage-dispatch.schema.json
│   ├── stage-result.schema.json
│   ├── repository-model-packet.schema.json
│   ├── topology-packet.schema.json
│   ├── validation-receipt.schema.json
│   ├── report-manifest.schema.json
│   └── commit-receipt.schema.json
│
├── schemas/
│   ├── repository-record.schema.json
│   ├── artifact-record.schema.json
│   ├── capability-record.schema.json
│   ├── edge-record.schema.json
│   ├── flow-record.schema.json
│   ├── graph-record.schema.json
│   ├── evidence-record.schema.json
│   ├── risk-record.schema.json
│   └── maturity-assessment.schema.json
│
├── src/
│   └── l9_constellation_topology/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── models.py
│       │
│       ├── run/
│       │   ├── context.py
│       │   ├── evidence.py
│       │   ├── diagnostics.py
│       │   ├── stages.py
│       │   └── receipts.py
│       │
│       ├── packets/
│       │   ├── refs.py
│       │   ├── loader.py
│       │   ├── validator.py
│       │   ├── repository_model.py
│       │   ├── topology_packet.py
│       │   ├── validation_receipt.py
│       │   └── adapters/
│       │       └── repository_model_v1.py
│       │
│       ├── sources/
│       │   ├── reader.py
│       │   ├── filesystem_reader.py
│       │   ├── repository_registry.py
│       │   └── source_snapshot.py
│       │
│       ├── scanners/
│       │   ├── repository_model_scanner.py
│       │   ├── repo_scanner.py
│       │   ├── manifest_scanner.py
│       │   ├── ci_scanner.py
│       │   ├── adr_scanner.py
│       │   ├── dependency_scanner.py
│       │   ├── governance_scanner.py
│       │   └── graphiti_scanner.py
│       │
│       ├── stages/
│       │   ├── resolve_config.py
│       │   ├── ingest_packets.py
│       │   ├── normalize_models.py
│       │   ├── observe_fallbacks.py
│       │   ├── reconcile_evidence.py
│       │   ├── aggregate_repositories.py
│       │   ├── aggregate_capabilities.py
│       │   ├── build_graph.py
│       │   ├── assess_impact.py
│       │   ├── assess_maturity.py
│       │   ├── assess_risk.py
│       │   ├── validate_topology.py
│       │   └── render_packet.py
│       │
│       ├── topology/
│       │   ├── classifier.py
│       │   ├── graph_builder.py
│       │   ├── capability_builder.py
│       │   ├── impact.py
│       │   ├── maturity.py
│       │   └── risk.py
│       │
│       ├── renderers/
│       │   ├── packet_renderer.py
│       │   ├── markdown_report.py
│       │   ├── json_export.py
│       │   ├── csv_export.py
│       │   ├── mermaid_export.py
│       │   └── neo4j_candidate.py
│       │
│       ├── validation/
│       │   ├── schema_validator.py
│       │   ├── invariant_validator.py
│       │   ├── packet_validator.py
│       │   ├── evidence_validator.py
│       │   └── validation_report.py
│       │
│       ├── io/
│       │   ├── rendered_artifact.py
│       │   ├── write_intent.py
│       │   ├── write_plan.py
│       │   ├── write_policy.py
│       │   ├── output_sink.py
│       │   ├── memory_output_sink.py
│       │   ├── filesystem_output_sink.py
│       │   └── packet_bundle_output_sink.py
│       │
│       └── worker/
│           ├── stage_runner.py
│           ├── callback.py
│           └── failure.py
│
├── tests/
│   ├── contracts/
│   ├── packets/
│   ├── scanners/
│   ├── stages/
│   ├── topology/
│   ├── validation/
│   ├── io/
│   ├── orchestration/
│   ├── integration/
│   └── fixtures/
│       ├── repository_model_packets/
│       ├── sample_constellation/
│       └── packet_pipeline/
│
├── scripts/
│   ├── validate_contracts.py
│   ├── compile_topology_packet.py
│   ├── render_topology_reports.py
│   ├── verify_determinism.py
│   └── architecture_boundary_check.py
│
└── docs/
    ├── architecture.md
    ├── packet-contracts.md
    ├── evidence-model.md
    ├── topology-model.md
    ├── worker-contract.md
    ├── output-sink.md
    ├── report-lifecycle.md
    ├── recovery.md
    └── migration-v4-to-v5.md

11.2 Existing file migrations

cli.py

Current behavior combines orchestration, compilation, rendering, validation, and direct writing.

It shall be reduced to command dispatch.

Commands:

compile-packet
validate-packet
render-report
impact
inspect-packet
verify-determinism

scan and scan-many may remain as compatibility commands but shall internally produce a Repository Model adaptation and then invoke the packet compiler.

evidence.py

Retain:

* canonical serialization;
* SHA-256 utilities;
* immutable conversion.

Replace timestamp-contaminated semantic hashing.

Add:

semantic_hash
artifact_hash
evidence_set_hash
record_hash
normalize_source_path

models.py

Split into domain-specific modules over time.

Maintain compatibility imports during migration.

renderers/*

Refactor from file-writing functions into pure rendering functions.

validation/*

Validation returns typed results and receipt data.

It shall not write reports directly.

scanners/*

Scanners remain read-only and emit evidence plus structured observations.

_write_all_outputs

Remove.

Its responsibilities are replaced by:

renderers
→ RenderedArtifact[]
→ OutputSink

⸻

12. GitHub Actions Workflows

12.1 l9-pr-validate.yml

Triggers:

on:
  pull_request:
    branches: [main]
  merge_group:
    types: [checks_requested]

Responsibilities:

* checkout exact revision;
* install dependencies;
* compile package;
* run unit and integration tests;
* validate schemas;
* run architecture boundary test;
* compile a preview Topology Packet from fixtures;
* verify deterministic semantic hash;
* upload temporary artifacts;
* publish check summary.

It shall not publish a canonical Topology Packet.

12.2 l9-ingress.yml

Triggers:

on:
  push:
    branches: [main]
  workflow_dispatch:

Responsibilities:

* build signed task-declaration TransportPacket;
* identify exact source SHA;
* submit task to the control API;
* expose orchestration run ID;
* perform no topology compilation.

12.3 l9-stage-worker.yml

Trigger:

on:
  workflow_dispatch:
    inputs:
      dispatch-packet:
        required: true
        type: string

Responsibilities:

1. validate dispatch packet;
2. verify requested action is allowed;
3. checkout exact target revision;
4. fetch input Repository Model Packets;
5. verify hashes and receipts;
6. run compile-packet;
7. validate output;
8. publish packet bundle;
9. callback success;
10. callback failure in an always() guarded step.

Permissions shall be minimal and explicit.

12.4 l9-manual-replay.yml

Inputs:

packet ID
stage ID
dry-run
reason

Produces a replay-request TransportPacket and submits it to the control plane.

⸻

13. Integration With l9-ci-core

l9-ci-core currently acts as a reusable GitHub Actions workflow repository and already provides a canonical cross-repository CI surface. (⁠GitHub)

The following shared capabilities shall live in l9-ci-core:

TransportPacket validation
task submission
packet fetch
packet publication
stage result callback
GitHub App token handling
Python environment setup
Node environment setup
check reporting
generated PR creation
shared packet contracts
Postgres orchestration migrations
dispatcher and reconciler

Topology-specific compilation logic shall remain in l9-constellation-topology.

The topology repository shall consume reusable workflow or composite-action primitives from l9-ci-core, pinned to immutable versions or commit SHAs.

⸻

14. Postgres Control-Plane Contract

The topology repository does not own the database schema, but its worker contract depends on it.

Required tables:

workflow_runs
workflow_stages
stage_dependencies
packet_registry
execution_attempts
outbox_events
dead_letter_tasks

Required queues:

l9_stage_dispatch
l9_github_callbacks
l9_outbox_delivery

Topology-specific stage state:

pending
ready
leased
dispatched
running
succeeded
failed
blocked
cancelled
dead-lettered

A topology stage shall not be considered successful until:

1. packet bundle publication succeeds;
2. packet digest verification succeeds;
3. validation receipt status is passed;
4. packet registry insertion succeeds;
5. stage callback transaction commits.

⸻

15. Packet Storage and Registry

15.1 Packet store

The initial deployment shall use GHCR-compatible immutable OCI artifacts.

The dispatch event or workflow input shall carry only:

packet ID
packet URI
packet type
packet version
semantic hash
source revision
validation status

It shall not embed the full topology payload.

15.2 Packet registry

The Postgres packet registry shall track:

packet identity
packet type
packet version
subject identity
source revision
semantic hash
artifact hash
storage URI
validation status
producer
producer version
run ID
stage ID
parent packet
root packet
generation
supersession state

15.3 Supersession

A new packet may supersede a prior packet.

Superseded packets shall not be deleted by default.

Default context retrieval shall resolve only the current validated packet unless history is explicitly requested.

⸻

16. Security and Governance

16.1 Trusted execution identities

Allowed:

GitHub App installation token
GitHub OIDC identity
job-scoped GITHUB_TOKEN for same-repository read operations

Disallowed:

human PAT as foundational pipeline credential
database owner credentials in compiler repositories
GitHub App private key in compiler repositories
static cloud access keys where OIDC is available

16.2 Packet security

Cross-repository stage dispatch and result packets shall be signed.

Allowed signature algorithms follow the TransportPacket contract.

Packet attachment hashes shall be verified before use.

16.3 Source permissions

Source repositories are read-only during topology compilation.

Generated repository updates shall occur through a separate PR workflow.

16.4 Classification and retention

TransportPacket governance classification and retention values shall apply to:

* packet bundle;
* reports;
* debug artifacts;
* validation receipts;
* dead-letter records.

16.5 Prompt and model use

No model-generated inference shall be promoted as a canonical topology fact without:

* explicit evidence classification;
* confidence assessment;
* validation;
* policy approval where required.

The initial topology compiler should remain deterministic and model-free unless a future profile explicitly enables bounded assistance.

⸻

17. Failure Semantics

17.1 Input packet failure

Examples:

missing packet
hash mismatch
invalid signature
unsupported version
failed parent validation receipt
duplicate current packet
conflicting repository identity

Result:

stage blocked
failure packet emitted
no topology output committed

17.2 Compilation failure

Examples:

repository boundary ambiguity
unresolved required edge endpoint
invalid capability relationship
semantic hash instability
risk-rule exception

Result:

failure packet
debug attachment
retry only when error classification permits

17.3 Publication failure

The packet remains unregistered until publication is complete.

A failed publication may be retried with the same idempotency key.

17.4 Callback failure

If publication succeeds but callback fails:

* dispatcher/reconciler shall detect the published packet;
* stage completion shall be repaired idempotently;
* duplicate packet publication shall be avoided.

17.5 Partial sink commit

The commit receipt must report partial state.

No false “complete” result is permitted.

⸻

18. Testing Requirements

18.1 Unit tests

Required coverage:

packet parsing
packet adapters
semantic hashing
artifact hashing
path normalization
evidence authority
confidence decomposition
repository aggregation
capability aggregation
edge identity
impact traversal
maturity profiles
risk profiles
schema validation
invariant validation
OutputSink policy
collision detection
unchanged output skipping
expected hash protection

18.2 Fixture correction

The sample constellation fixture shall produce:

repo:l9-gate-sdk
repo:l9-mcp-server

not:

repo:sample_constellation

unless an explicit fixture profile declares the containing directory to be one repository.

18.3 Integration tests

Repository Model Packet → Topology Packet
multiple repository packets → one topology packet
conflicting packets → blocked result
stale packet → warning or block by profile
invalid validation receipt → block
output sink dry-run → no writes
output sink commit → complete receipt
report rendering → deterministic cache key
repeated run → identical semantic hash

18.4 End-to-end Model B test

mock Postgres stage dispatch
→ GitHub-style worker input
→ fetch fixture Repository Model Packet
→ compile Topology Packet
→ validate
→ publish to test packet store
→ callback stage result
→ assert packet registry reference

18.5 Architecture tests

Enforce:

* no direct filesystem writes outside io/;
* no Neo4j SDK import;
* no Graphiti write client;
* no network calls in unit tests;
* no report used as a canonical compiler input;
* no absolute local path in semantic hashes;
* no unversioned packet payload contract.

18.6 Validation ladder

python -m compileall src tests -q
python -m pytest tests -q
schema contract validation
architecture boundary validation
determinism verification
package build
package installation smoke test
fixture packet compilation
fixture packet validation

No validation claim may be made without actual captured execution evidence.

⸻

19. Migration Plan

Phase T0 — baseline preservation

* capture current outputs;
* capture current test baseline;
* inventory all filesystem writes;
* inventory all public CLI commands;
* document current schema versions;
* mark v4 contract as superseded but retained historically.

Phase T1 — packet and signal contracts

* add packet refs;
* add RunContext;
* add EvidenceRecord;
* add decomposed confidence;
* add stage-result contracts;
* preserve runtime behavior.

Phase T2 — pure rendering and OutputSink

* refactor renderers;
* remove _write_all_outputs;
* add MemoryOutputSink;
* add FileSystemOutputSink;
* add write planning and receipts;
* preserve CLI compatibility.

Phase T3 — Repository Model Packet ingestion

* add packet loader;
* add packet validation;
* add RepositoryModelV1 adapter;
* add repository_model_scanner;
* retain direct scan fallback.

Phase T4 — canonical topology model

* add repository, artifact, capability, edge, flow, risk, and maturity records;
* migrate existing RepoCard and EdgeCard outputs;
* correct repository boundary semantics.

Phase T5 — Topology Packet compiler

* implement packet manifest;
* implement semantic hash;
* implement validation receipt;
* implement packet bundle output;
* add deterministic packet fixtures.

Phase T6 — GitHub worker

* add ingress workflow;
* add stage worker workflow;
* add callback client;
* integrate shared l9-ci-core actions;
* run one-repository vertical slice.

Phase T7 — Model B cross-repository chain

* consume real Repository Model Packet from l9-meta-injector;
* publish Topology Packet;
* trigger ingestion planning through Postgres stage dependency;
* verify end-to-end lineage.

Phase T8 — lazy report projections

* render Markdown, CSV, Mermaid, YAML, and Neo4j candidates from Topology Packet;
* add report-manifest packet;
* add projection cache.

Phase T9 — recovery and reconciliation

* validate retry behavior;
* validate missing callback repair;
* validate packet reuse;
* validate dead-letter operation;
* validate manual replay.

Phase T10 — generated documentation PRs

* generate managed architecture sections;
* open PR through GitHub App;
* validate source freshness and expected hashes;
* prohibit direct main-branch writes.

⸻

20. Acceptance Criteria

The specification is implemented when all of the following hold.

Functional

1. The compiler consumes validated Repository Model Packets.
2. A constellation of two repositories produces two repository nodes.
3. Artifact and capability relationships are preserved in the topology.
4. The compiler emits one validated Topology Packet.
5. The ingestion bridge can consume the Topology Packet without reading neighboring reports.
6. Reports can be regenerated from the Topology Packet.
7. Impact, risk, and maturity remain available.

Determinism

8. Two runs with identical semantic inputs produce the same semantic hash.
9. Machine-local paths do not affect semantic identity.
10. Timestamps do not affect semantic identity.
11. Graph entity and edge IDs are stable.

Evidence

12. Every canonical claim references evidence.
13. Inference is explicitly labeled.
14. Unknowns are explicit.
15. Conflicts are preserved, not silently overwritten.
16. Evidence references resolve.

Output safety

17. No production module outside io/ mutates files.
18. Invalid topology produces zero committed canonical outputs.
19. Dry-run performs no prohibited writes.
20. Unchanged outputs are skipped.
21. Every committed artifact appears in a commit receipt.

Orchestration

22. Postgres activates topology based on the existence of a validated Repository Model Packet.
23. GitHub Actions executes the exact requested stage at the exact revision.
24. Stage completion requires packet publication and validation.
25. Repeated identical input reuses the prior validated packet.
26. Failed transient work retries.
27. Non-retryable validation failures block.
28. Reconciliation repairs a dropped callback.
29. Dead-lettered work is queryable.
30. Manual replay preserves packet lineage.

Security

31. No human PAT is used.
32. No database credentials are stored in the topology repository.
33. No GitHub App private key is stored in the topology repository.
34. Cross-repository packets are signed.
35. Packet attachment hashes are verified.
36. Source repositories remain read-only during compilation.

Compatibility

37. Legacy scan commands either remain available or have documented replacements.
38. Existing validated topology behavior is preserved where not explicitly superseded.
39. Existing graph, risk, maturity, impact, and report capabilities remain supported.
40. Migration from v4 output to v5 packet output is documented.

⸻

21. Explicit Prohibitions

The implementation shall not:

* create a second transport shape alongside TransportPacket;
* call informal containers envelopes;
* use reports as downstream compiler contracts;
* insert full packet payloads into repository_dispatch;
* use GitHub workflow completion alone as the semantic dependency condition;
* write directly to Neo4j;
* write directly to Graphiti;
* mutate source repositories during topology compilation;
* put absolute local paths into semantic IDs;
* claim bit-for-bit determinism while including timestamps in semantic hashes;
* collapse multiple repositories into one node because they share a parent directory;
* use low/medium/high as the only evidence-quality model;
* validate by mutating the packet under validation;
* scatter direct file writes;
* commit after every rendered artifact;
* regenerate every report in every run;
* require the full Gate before foundational deployment;
* introduce Kafka, Redis, Temporal, or self-hosted runners without measured need;
* grant GitHub App organization-administration permissions;
* store database owner credentials in GitHub;
* auto-push generated documentation directly to main;
* silently promote model-generated output as source truth;
* report a successful stage before packet registration and validation complete.

⸻

22. Final Target Architecture

┌───────────────────────────────────────────────┐
│ Source repositories                           │
│ Human-declared authority                      │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│ l9-meta-injector                              │
│ Artifact-level repository compiler            │
└───────────────────────┬───────────────────────┘
                        │
              Repository Model Packet
                        │
                        ▼
┌───────────────────────────────────────────────┐
│ l9-constellation-topology                     │
│ Repository and constellation topology compiler│
│                                               │
│ packet validation                             │
│ repository aggregation                        │
│ capability topology                           │
│ dependency graph                              │
│ governance topology                           │
│ impact / maturity / risk                      │
│ topology validation                           │
└───────────────────────┬───────────────────────┘
                        │
                  Topology Packet
                        │
                        ▼
┌───────────────────────────────────────────────┐
│ l9-topology-ingestion-bridge   [SUPERSEDED]   │
│ Evidence-gated publication compiler           │
│ ADR-0021: now the internal publication/       │
│ module of l9-constellation-topology           │
└───────────────┬───────────────┬───────────────┘
                │               │
                ▼               ▼
         Candidate queue    Effect plans
                                │
                    Future controlled sinks
                         Graphiti / Neo4j

Execution control:

GitHub event
    ↓
l9-ci-core ingress
    ↓
TransportPacket task declaration
    ↓
Postgres state machine + pgmq
    ↓
GitHub Actions topology worker
    ↓
Topology Packet
    ↓
callback
    ↓
Postgres activates ingestion planning

Information control:

source repository
    authoritative declarations
Repository Model Packet
    immutable artifact semantics
Topology Packet
    immutable repository relationships
reports
    projections only
canonical graph
    accepted relationship index and packet references
temporal memory
    recent observations, rationale, and conflict history

⸻

23. Convergence Contract

convergence:
  specification_status: superseding-proposed
  target_contract_version: 5.0.0
  source_intent_preserved: true
  architecture:
    canonical_repository_model: required
    run_signal_plane: required
    transport_packet: required
    output_sink: required
    packet_spine: required
    model_b_orchestration: required
    reports_as_projections: required
  deployment_scope:
    foundational_repositories_only: true
    full_l9_gate_required: false
    live_graph_publication_required: false
  minimum_safe_first_slice:
    - add packet and evidence contracts
    - refactor direct writes behind OutputSink
    - add Repository Model Packet fixture ingestion
    - emit deterministic Topology Packet locally
  first_external_integration:
    source: l9-meta-injector
    destination: l9-constellation-topology
    execution: github-actions-worker
    orchestration: postgres-model-b
  remaining_explicit_unknowns:
    - final OCI packet publication implementation
    - exact l9-ci-core API hosting platform
    - initial packet-signing key custody platform
    - whether orchestration runtime remains in l9-ci-core or is later extracted
    - final live Graphiti and Neo4j sink promotion policy
  stop_conditions:
    - packet contract cannot be validated deterministically
    - source repository mutation is required for topology compilation
    - repository boundary ambiguity cannot be represented explicitly
    - output write path bypasses OutputSink
    - stage success can occur without a validated registered packet
