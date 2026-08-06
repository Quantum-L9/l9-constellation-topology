# Regression Guard

## Preserved capabilities

- Validated Repository Model Packet ingestion
- Canonical repository, artifact, capability, edge, flow, evidence, risk, maturity, conflict, and Unknown records
- Deterministic Topology Packet compilation
- Separate immutable Validation Receipt
- OutputSink-only controlled effects
- Dry-run, collision, overwrite, expected-hash, and commit-receipt behavior
- Report projections from Topology Packets
- Legacy read-only scanner compatibility ingress
- Signed TransportPacket preflight and exact-revision worker execution
- Local and OCI packet-store adapters
- Typed upstream diagnostic conservation
- Complete semantic compilation fingerprints
- Digest-bound packet publication and reuse
- Locally governed callback destinations, credentials, hosts, ports, and segment-bound paths
- Transactional local recovery registry
- Idempotent packet reuse and signed callbacks

## Guard commands

```bash
python -m compileall src tests scripts -q
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python scripts/validate_contracts.py
PYTHONPATH=src python scripts/validate_workflows.py
PYTHONPATH=src python scripts/architecture_boundary_check.py
PYTHONPATH=src python scripts/validate_release_readiness.py
git add -A
PYTHONPATH=src python scripts/git_tree_manifest.py
git add GIT_TREE_MANIFEST.json
PYTHONPATH=src python scripts/validate_git_integrity.py
PYTHONPATH=src python scripts/verify_determinism.py
```

## Prohibited regressions

- Reports becoming stage-to-stage transport
- Direct Neo4j or Graphiti clients
- Source-repository mutation during compilation
- Filesystem writes outside `io/`
- Absolute paths or timestamps entering semantic identity
- Validation mutating the packet under review
- Silent malformed-manifest handling
- Removal of required release evidence without a manifest update
- A human inventory that differs from tracked paths
- A Git tree manifest whose path, mode, object type, or blob ID differs from `git ls-tree`
- Packet-selected callback URLs or environment-variable names
- Callback path prefix checks without segment boundaries or encoded-separator rejection
- Tag-only OCI references in production paths or shared mutable publication tags
- Reuse keys that omit any output-affecting profile, schema, adapter, or compiler build identity
- Dropped input diagnostics

## Governance and decision-memory guards

- The repository must retain the full build specification.
- Exactly 20 initial accepted ADRs must remain indexed unless a later ADR is added.
- Every ADR must include context, decision, consequences, alternatives, compliance,
  and related artifacts.
- Root architecture, governance, security, development, support, release, license,
  threat, dependency, and initial-commit files must remain present.
- Collaboration templates cannot weaken packet, evidence, OutputSink, or validation laws.

## Generated artifact synchronization invariant

- Validation must not rewrite generated files; check targets are read-only and fail closed.
- `make generated-check` must fail for missing or stale schemas or packet fixtures.
- `make schemas-update`, `make fixtures-update`, and `make generated-update` are the only canonical regeneration targets.
- Duplicate generated destinations fail closed.
- `make validate` must retain the deterministic schema drift gate (`schemas-check`).
- A generated source change is incomplete until generated diffs are reviewed and the read-only check passes.
