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
make architecture
make readiness
```

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
