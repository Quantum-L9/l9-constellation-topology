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
- Idempotent packet reuse and signed callbacks

## Guard commands

```bash
python -m compileall src tests scripts -q
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python scripts/validate_contracts.py
PYTHONPATH=src python scripts/validate_workflows.py
PYTHONPATH=src python scripts/architecture_boundary_check.py
PYTHONPATH=src python scripts/validate_release_readiness.py
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

## Governance and decision-memory guards

- The repository must retain the full build specification.
- Exactly 20 initial accepted ADRs must remain indexed unless a later ADR is added.
- Every ADR must include context, decision, consequences, alternatives, compliance,
  and related artifacts.
- Root architecture, governance, security, development, support, release, license,
  threat, dependency, and initial-commit files must remain present.
- Collaboration templates cannot weaken packet, evidence, OutputSink, or validation laws.
