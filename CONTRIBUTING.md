# Contributing

Changes must preserve packet boundaries, deterministic semantic identity, fail-closed validation, and the OutputSink effect boundary.

Before opening a pull request:

```bash
python -m compileall src tests -q
python -m pytest tests -q
python scripts/validate_contracts.py
python scripts/architecture_boundary_check.py
python scripts/verify_determinism.py
uv build
```

A pull request must state the contract or defect addressed, evidence for the change, validation commands executed, and any remaining unknowns. Generated documents are updated through a pull request, never pushed directly to `main` by the compiler.

## Architecture changes

Changes to packet contracts, semantic identity, evidence authority, OutputSink,
worker trust, orchestration, storage, or downstream publication require an ADR.
Follow `GOVERNANCE.md` and update `ADR_INDEX.md`, the full build specification,
contracts, migration notes, tests, and validation evidence together.

## Complete gate

```bash
make validate
```

See `DEVELOPMENT.md`, `DEPENDENCY_POLICY.md`, and `RELEASING.md`.
