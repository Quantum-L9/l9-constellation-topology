# L9 Constellation Topology Canonical Build Specification

## Metadata

```yaml
specification_id: l9.constellation-topology.spec
specification_version: 5.0.0
implementation_version: 2.0.0
status: accepted_initial_repository_baseline
source_repository: Quantum-L9/l9-constellation-topology
source_commit: bbca641a0380f66c10dc83ff5be86669d3c94172
source_blob: 58e8d062ecbb74fe8a007f4601f82bd27631596d
primary_runtime: Python 3.12+
transport_standard: TransportPacket
primary_input: validated Repository Model Packets
primary_output: validated immutable Topology Packet
source_mutation_policy: read_only
canonical_principle: evidence over inference; packets over reports; planned effects over direct writes
```

## 1. Executive objective

`l9-constellation-topology` is the deterministic middle-end compiler in the
foundational L9 repository-intelligence pipeline. It consumes validated artifact-
level repository semantics and emits repository- and constellation-level topology.

The compiler aggregates repositories, artifacts, capabilities, dependencies,
governance, documentation, CI, runtime, memory relationships, flows, impact,
maturity, risk, conflicts, unknowns, and evidence lineage.

It is not a source scanner that hands a directory of reports to the next stage.
Reports remain human projections of the canonical packet.

## 2. System position

```text
source repositories
        ↓
l9-meta-injector
        ↓ validated Repository Model Packet(s)
l9-constellation-topology
        ↓ validated Topology Packet + Validation Receipt
        ↓ publication plan: eligibility decisions and memory.ingest intents
l9-graphiti-memory
        ↓ durable admission, promotion decisions, publication receipts
```

Execution control:

```text
GitHub event
    ↓
l9-ci-core ingress
    ↓ signed TransportPacket task declaration
Postgres Model B state machine
    ↓ signed stage-dispatch packet
GitHub Actions exact-revision worker
    ↓ validated Topology Packet publication
signed stage-result callback
    ↓
Postgres packet registration and dependency activation
```

## 3. Repository authority boundary

### Owns

- validation and normalization of supported Repository Model Packet versions;
- bounded read-only topology observations when enabled by profile;
- evidence reconciliation and conflict preservation;
- repository and capability aggregation;
- stable topology identities, graph records, edges, and flows;
- impact traversal;
- profile-driven maturity and risk projections;
- Topology Packet construction;
- schema, invariant, evidence, and lineage validation;
- pure report rendering;
- local packet-bundle output planning and commit receipts;
- worker-side packet fetch, publication verification, and callbacks.

### Does not own

- artifact-level source understanding;
- source-repository mutation;
- canonical graph promotion;
- direct Neo4j or Graphiti writes;
- Postgres control-plane schema and scheduling state;
- global promotion policy;
- organization key custody;
- the full L9 Gate during the foundational deployment phase.

## 4. Authority order

1. Human-declared source authority.
2. Validated Repository Model Packet evidence.
3. Deterministic direct observation.
4. Cross-record deterministic derivation.
5. Heuristic derivation.
6. Model-assisted inference under an explicitly approved future profile.
7. Prior generated topology.

Contradictions produce conflict records. Missing evidence produces unknown records.
Neither is silently replaced by last-write-wins behavior.

## 5. Transport and packet contracts

`TransportPacket` is the only control-plane envelope. The compiler cannot introduce
another envelope or use report files as inter-stage transport.

Accepted payloads:

- `l9.stage-dispatch/1.0.0`
- `l9.repository-model-ref/1.0.0`
- `l9.replay-request/1.0.0`
- `l9.render-request/1.0.0`
- `l9.validation-request/1.0.0`

Emitted payloads:

- `l9.topology-ref/1.0.0`
- `l9.stage-result/1.0.0`
- `l9.execution-failure/1.0.0`
- `l9.validation-receipt/1.0.0`
- `l9.render-result/1.0.0`
- `l9.reuse-receipt/1.0.0`

Large packet bodies use immutable attachments with content hashes, media types,
sizes, and storage URIs.

## 6. Repository Model Packet input

Each parent packet must supply or reference:

- packet manifest and packet identity;
- repository identity and source revision;
- semantic hash;
- artifact, module, capability, and relationship records;
- evidence and diagnostics;
- passed Validation Receipt;
- producer and contract versions;
- profile and schema hashes.

The loader verifies bundle membership, byte hashes, packet schema, source revision,
parent receipt, and repository identity. Unsupported versions fail closed unless a
versioned adapter is present.

## 7. Canonical internal model

The run-scoped compiler model includes:

- `RunContext`
- `RepositoryRecord`
- `ArtifactRecord`
- `CapabilityRecord`
- `EdgeRecord`
- `FlowRecord`
- `EvidenceRecord`
- `ConfidenceAssessment`
- `ConflictRecord`
- `UnknownRecord`
- `ImpactIndex`
- `RiskRecord`
- `MaturityAssessment`
- `Diagnostic`
- `StageReceipt`

External packet versions are translated at ingress. Topology algorithms operate on
canonical records and do not know whether data originated from a packet, fixture,
or compatibility scan.

## 8. Run-scoped signal plane

Every compilation carries explicit typed state for:

- input references and source snapshots;
- configuration and policy hashes;
- evidence, derivations, conflicts, unknowns, and diagnostics;
- stage inputs and outputs;
- rendered artifacts and write intents;
- validation and commit receipts;
- packet lineage.

Global mutable compiler state is prohibited.

## 9. Confidence assessment

Confidence is decomposed into:

- level: low, medium, high;
- evidence strength: none, weak, corroborated, direct;
- derivation method: declared, deterministic, cross-record, heuristic,
  model-assisted, unknown;
- authority: source, validated-machine, derived, candidate, unknown;
- completeness: partial, sufficient, complete;
- conflict status: none, possible, confirmed.

The simple level remains available for compatibility and routing, but canonical
validation considers the full assessment.

## 10. Compilation stages

```text
resolve configuration
→ ingest packet references
→ validate input packets
→ normalize repository models
→ perform bounded direct observation
→ reconcile evidence
→ aggregate repositories
→ classify repository roles
→ aggregate capabilities
→ build graph and flows
→ calculate impact
→ assess maturity
→ assess risk
→ validate topology
→ render packet bundle
→ plan outputs
→ commit outputs
→ emit stage result
```

Each stage accepts typed input and returns typed output. Compilation stages cannot
perform hidden filesystem or network effects.

## 11. Bounded direct observation

Direct repository observation is allowed only when:

- the active profile enables it;
- the exact source revision is available;
- a required topology signal is absent from the parent packet;
- the observation is deterministic and read-only;
- the resulting evidence is classified as a new observation;
- the observation does not silently override stronger packet or source authority.

Legacy scanner logic remains behind this boundary.

## 12. Repository identity and aggregation

A directory containing multiple repositories cannot be collapsed into one
repository node merely because the repositories share a parent directory.
Repository boundaries resolve in this order:

1. Repository Model Packet subject identity.
2. Explicit repository registry.
3. Git boundary.
4. Explicit manifest declaration.
5. Configured fallback rule.

Ambiguous boundaries produce diagnostics, conflicts, or a blocked result according
to profile requirements.

## 13. Capability topology

The compiler derives versioned relationships including:

- Repository `IMPLEMENTS` Capability
- Artifact `IMPLEMENTS` Capability
- Capability `VALIDATED_BY` Test
- Capability `GOVERNED_BY` ADR
- Capability `DOCUMENTED_BY` documentation
- Capability `DEPENDS_ON` Capability
- Workflow `PRODUCES` Packet
- Stage `CONSUMES` Packet

Every accepted relationship references evidence.

## 14. Graph construction

Graph construction is pure. Stable entity and edge identities derive from canonical
semantic IDs and normalized properties, never machine-local absolute paths.

Supported edge classes include `CONTAINS`, `DEPENDS_ON`, `IMPLEMENTS`, `EXPOSES`,
`VALIDATED_BY`, `GOVERNED_BY`, `OWNED_BY`, `DOCUMENTED_BY`, `PRODUCES`, `CONSUMES`,
`DERIVED_FROM`, `SUPERSEDES`, `ROUTES_TO`, `PUBLISHES_TO`, and `MEMBER_OF`.

Edge-type additions require schema versioning and an ADR.

## 15. Impact analysis

Impact supports:

- upstream, downstream, and bidirectional traversal;
- bounded depth and node limits;
- edge-type and confidence filters;
- packet-version scoping;
- current and historical topology views;
- affected repository and capability summaries;
- unresolved-edge diagnostics;
- deterministic cycle handling.

## 16. Maturity and risk

Maturity is a projection, not canonical truth. Profiles define dimensions, weights,
evidence requirements, maximum scores, bands, and treatment of unknowns and
conflicts.

Risk rules are configuration-driven and versioned. Example categories include
missing CI, missing governance, low evidence quality, stale packets, conflicting
identity, unvalidated dependencies, missing ownership, lineage breaks, and
non-deterministic output.

## 17. Topology Packet output

The Topology Packet is the sole canonical machine output. It contains or references:

- producer and profile identity;
- parent packet references and lineage;
- repository, artifact, capability, edge, flow, and graph records;
- impact indexes;
- risk and maturity projections;
- evidence, conflicts, unknowns, and diagnostics;
- semantic and artifact hashes;
- a reference to the separate Validation Receipt.

## 18. Validation

Validation produces immutable receipt data and does not mutate the packet under
validation.

Schema checks cover packet and record contracts.

Invariant checks include:

- every edge endpoint exists;
- every evidence reference resolves;
- every repository has one canonical identity;
- accepted facts carry evidence;
- inference is not labeled as declared;
- source revisions and lineage are present;
- semantic hashes reproduce;
- local absolute paths do not enter semantic identity;
- disallowed graph cycles are reported;
- the receipt references the exact packet semantic hash.

Cross-packet checks include parent status, hash agreement, identity consistency,
version support, and required repository presence.

A failed validation commits no canonical Topology Packet.

## 19. Determinism

The semantic hash covers semantic inputs, compiler version, profile hash, schema
contract hash, canonical records, and deterministic ordering. It excludes timestamps,
execution IDs, machine-local paths, and presentation order.

Artifact hashes cover exact emitted bytes. A timestamp may change report bytes while
the semantic hash remains stable.

## 20. OutputSink architecture

All production filesystem effects pass through `OutputSink`.

The sink:

- normalizes and contains paths;
- enforces artifact-kind and output-root policy;
- detects collisions;
- compares existing content;
- skips unchanged outputs;
- requires expected hashes for protected replacement;
- stages atomic per-file writes;
- reports partial failures honestly;
- supports dry-run and in-memory execution;
- emits an itemized Commit Receipt.

Required implementations are memory, filesystem, packet-bundle, and composite
sinks. Registry and object-store adapters remain outside compiler semantics.

## 21. Report lifecycle

Reports are lazy projections of a validated Topology Packet. Supported projections
include Markdown, Mermaid, CSV, YAML, combined JSON, graph JSONL, Neo4j candidate
JSONL, and risk reports.

Projection identity is:

```text
topology semantic hash
+ renderer identity and version
+ report profile hash
```

Reports cannot serve as compiler-stage inputs. Generated repository documentation
requires expected-hash checks, diff review, and pull-request delivery.

## 22. Model B orchestration

Postgres owns durable workflow state, dependencies, leases, retries, packet registry,
outbox delivery, reconciliation, and dead letters. GitHub Actions provides ephemeral
exact-revision workers.

The topology stage becomes runnable because a validated Repository Model Packet
exists, not merely because an upstream workflow finished.

Stage success requires:

1. packet bundle commit;
2. packet publication;
3. clean re-fetch and digest verification;
4. passed Validation Receipt;
5. packet registry insertion;
6. committed stage callback transaction.

## 23. Idempotency, replay, and recovery

The idempotency key is the semantic hash of a complete compilation fingerprint: sorted parent semantic hashes, compiler name/version/build identity, aggregate topology/risk/maturity/report/packet/output configuration hash, schema-contract hash, active contract versions, adapter mode, and output packet type/version.

An existing validated result is reused and emits a reuse receipt. Retryable failures
include temporary packet-store, runner-capacity, and callback errors. Contract,
signature, hash, parent-validation, and topology-invariant failures are non-retryable.

A published packet whose callback is lost is reconciled by idempotency key without
blind republication. Exhausted work is preserved in the external dead-letter store.
Manual replay is authorized by the control plane and preserves lineage.

## 24. Worker trust sequence

1. Check out trusted `main` worker authority.
2. Build a frozen non-editable environment.
3. Decode but do not trust dispatch fields.
4. Verify signature, key ID, transport version, payload schema, action, repository,
   profile, parent status, idempotency key, approved callback ID, digest-qualified output URI, and exact object ID.
5. Check out the signed target revision only after preflight passes.

### 24.1 Callback trust boundary

The dispatch packet carries only an approved callback ID. Worker-local policy resolves the destination and dedicated credential, requires an enabled entry with exact host and optional port constraints, uses segment-bound path matching, rejects encoded slash and backslash ambiguity and redirects, and blocks unsafe DNS results. Packet content cannot select an environment-variable name or arbitrary destination.

### 24.2 Immutable publication verification

Production OCI authority is digest-qualified. Publication uses a semantic-hash-derived staging tag, records only the returned digest-qualified reference, independently resolves the registry descriptor, and re-fetches the bundle. Publication and reuse compare the result against the expected PacketRef, validation subject, bundle-manifest digest, and registry manifest digest. A different but internally valid packet is rejected.
6. Build the exact-revision environment from its lockfile.
7. Revalidate and execute.

Unsigned or tampered packets cannot select executable code.

## 25. Packet storage and registry

The initial immutable packet store is GHCR-compatible OCI storage accessed through
ORAS. Dispatch packets carry references and hashes, not large payloads.

The external registry tracks identity, type, version, subject, source revision,
semantic and artifact hashes, URI, validation status, producer, run, stage, lineage,
and supersession state.

Superseded packets remain available for history and audit unless retention policy
explicitly removes them.

## 26. Security

Allowed execution identities include GitHub App installation tokens, GitHub OIDC,
and job-scoped `GITHUB_TOKEN` for bounded operations.

Human personal access tokens, database owner credentials, GitHub App private keys,
and static cloud keys are prohibited in this repository.

Cross-repository control packets are signed. Attachment and bundle hashes are
verified before use. Source repositories remain read-only. Model-generated claims
cannot become canonical facts without evidence classification, confidence,
validation, and policy approval.

## 27. Failure semantics

Input failures block before compilation. Compilation failures emit an execution-
failure packet and commit no canonical output. Publication failures preserve the
idempotency key for safe retry. Callback failures are reconciled against the
published packet. Partial sink commits are reported item by item and cannot be
reported as complete.

## 28. Required repository structure

The repository contains:

- root governance, architecture, security, support, release, and operator documents;
- `.github/workflows/` for PR validation, ingress, exact-revision worker, and replay;
- `.l9/` versioned topology, packet, risk, maturity, report, output, and pipeline profiles;
- `contracts/` and `schemas/`;
- `src/l9_constellation_topology/` with domain, packet, topology, validation, I/O,
  renderer, compatibility, source, stage, and worker modules;
- `tests/` with unit, contract, integration, worker, and regression fixtures;
- `docs/adr/` with accepted architectural decisions;
- deterministic validation and build scripts.

## 29. Validation ladder

```text
compileall
pytest with branch coverage
ruff
strict mypy
contract and schema validation
workflow validation
architecture boundary validation
release-readiness validation
determinism verification
package build
isolated installation and CLI smoke
fixture packet compilation and validation
```

No validation status is reported as passed without captured execution evidence.

## 30. Migration from v4

The donor implementation contributes read-only scanners, canonical serialization,
dependency analysis, graph traversal, maturity and risk logic, renderers, fixtures,
and regression tests.

Retired behaviors include report-directory stage transport, coarse trust decisions,
timestamp-contaminated identity, scattered writes, mutable validation, direct graph
handoffs, and repository identity derived from containing directories.

Compatibility commands adapt legacy scanner output into the v5 packet compiler.

## 31. Acceptance criteria

The repository is accepted when:

- validated Repository Model Packets compile into one validated Topology Packet;
- two repositories remain two canonical repository nodes;
- artifact and capability relationships retain evidence;
- reports regenerate solely from the packet;
- impact, maturity, and risk remain available;
- identical semantic inputs reproduce the semantic hash;
- invalid topology commits no canonical bundle;
- all writes are contained by OutputSink;
- exact-revision workers validate signed dispatches;
- repeated inputs reuse the prior validated result;
- legacy analytical behavior remains available through compatibility surfaces;
- migration and operational recovery are documented.

External production acceptance additionally requires real Postgres orchestration,
GHCR publication, callback-loss reconciliation, dead-letter inspection, and the
three-repository chain.

## 32. Explicit prohibitions

The implementation cannot:

- create a second transport envelope;
- use reports as stage contracts;
- embed large packet payloads in GitHub dispatch events;
- treat workflow completion as semantic dependency satisfaction;
- write directly to Neo4j or Graphiti;
- mutate source repositories;
- include local absolute paths or volatile timestamps in semantic identity;
- collapse multiple repositories into one parent-directory node;
- use a single confidence label as the full trust model;
- mutate packets during validation;
- scatter filesystem writes;
- regenerate every report on every compile;
- require the full Gate before foundational deployment;
- add major infrastructure without measured need;
- report stage success before packet validation and registration complete.

## 33. External unknowns

The repository intentionally records these external decisions rather than inventing
them:

- final production control-API hosting platform;
- production packet-signing key custody and rotation;
- final organization team slugs for CODEOWNERS;
- final live Graphiti and Neo4j promotion policy;
- whether Model B orchestration remains in `l9-ci-core` or later moves to a dedicated
  control-plane repository.

## 34. Convergence and stop conditions

The repository is converged locally when packet contracts, compiler behavior,
validation, deterministic outputs, OutputSink containment, worker preflight, root
governance, accepted ADRs, manifest, and operator documentation agree.

Work stops and reports a blocked state when:

- packet contracts cannot be deterministically validated;
- source mutation is required for compilation;
- repository identity ambiguity cannot be represented explicitly;
- a write bypasses OutputSink;
- stage success can occur without a validated registered packet;
- external proof is required but unavailable.
