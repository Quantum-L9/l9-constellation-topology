# Development

## Environment

Python 3.12 and `uv` 0.10.0 are canonical.

```bash
python -m pip install uv==0.10.0
uv sync --frozen --extra dev
```

## Repository layout

- `src/l9_constellation_topology/`: compiler, packets, topology, validation, I/O, worker.
- `contracts/`: control-plane and packet JSON Schemas.
- `schemas/`: canonical and compatibility record schemas.
- `.l9/`: versioned compiler and policy profiles.
- `tests/fixtures/`: validated packet, constellation, and legacy regression fixtures.
- `docs/adr/`: accepted architectural decisions.
- `scripts/`: deterministic validation and operator commands.

## Fast loop

```bash
make test
make contracts
make generated-check
make architecture
make readiness
```

## Generated artifacts

Run `make generated-check` after changes to canonical Pydantic models, schema generation, packet construction, fixture generation, or sample repositories. The check is read-only and fails when a generated file is missing or stale.

Regenerate only when the source change is intentional:

```bash
make schemas-update
make fixtures-update
# or both
make generated-update
```

After regeneration:

1. Review every changed schema, packet, receipt, and manifest.
2. Run `make generated-check` again.
3. Run targeted tests for the changed generator or model.
4. Run `make validate`.
5. Synchronize `MANIFEST.md`, `FINAL_TREE.md`, traceability records, validation evidence, and the commit-bound `GIT_TREE_MANIFEST.json` from the final staged tree.

Do not use an update target inside validation or CI. Validation must detect drift without mutating tracked files.

## Full loop

```bash
make validate
```

## Workflow changes

`scripts/validate_workflows.py` is the workflow contract gate. It checks the exact loaded
`uses` scalar against the full-SHA pin contract — a quoted value carrying a comment-like
suffix is a different action reference and is rejected — and it enforces the direct compile
seam's controls, including its least-privilege job split.

Run it directly after editing anything under `.github/workflows/`:

```bash
make workflows
uv run pytest tests/test_workflow_contracts_v5.py -q
```

The CI environment is built with `uv sync --frozen --no-build --extra dev --no-install-project`
followed by `uv pip install --no-deps --editable .`. `--no-build` keeps third-party source
distributions out of the environment; because that also refuses this project's own editable
install, the project is installed separately from its own tree with no dependency resolution.
Reproduce that pair locally when debugging a CI-only failure.

When changing `.github/workflows/compile.yml`, keep compilation and publication in separate
jobs. Package-write authority belongs only to the publishing job, and the ADR-0018 acceptance
drill's negative controls are part of the contract, not optional extras.

## Design rules

- Keep domain and topology stages pure.
- Adapt external packet versions at the boundary.
- Never use reports as compiler inputs.
- Add evidence and explicit unknowns rather than silent defaults.
- Route writes through `OutputSink`.
- Add tests for every behavioral change.
- Record architecture changes as ADRs before implementation.
- Keep generated artifacts synchronized through explicit update commands and read-only drift checks.
