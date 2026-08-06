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

## Design rules

- Keep domain and topology stages pure.
- Adapt external packet versions at the boundary.
- Never use reports as compiler inputs.
- Add evidence and explicit unknowns rather than silent defaults.
- Route writes through `OutputSink`.
- Add tests for every behavioral change.
- Record architecture changes as ADRs before implementation.
- Keep generated artifacts synchronized through explicit update commands and read-only drift checks.
