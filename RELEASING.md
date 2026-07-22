# Releasing

## Version policy

The Python distribution uses semantic versioning.

- **Major:** incompatible packet, schema, semantic identity, or CLI contract change.
- **Minor:** backward-compatible capability or supported contract version addition.
- **Patch:** backward-compatible defect, validation, documentation, or operational fix.

The build specification and packet schemas have independent explicit versions.
Changing the package version does not implicitly change a packet contract.

## Release prerequisites

```bash
uv sync --frozen --extra dev
uv run python -m compileall src tests scripts -q
uv run pytest --cov=l9_constellation_topology --cov-report=term-missing -q
uv run ruff check .
uv run mypy src/l9_constellation_topology
uv run python scripts/validate_contracts.py
uv run python scripts/validate_workflows.py
uv run python scripts/architecture_boundary_check.py
uv run python scripts/validate_release_readiness.py
git add -A
uv run python scripts/git_tree_manifest.py
git add GIT_TREE_MANIFEST.json
uv run python scripts/validate_git_integrity.py
uv run python scripts/verify_determinism.py
uv build
```

All executed checks must be recorded in `VALIDATION.md`. Checks unavailable in the
release environment remain explicitly blocked and cannot be reported as passed.

## Release procedure

1. Confirm the working tree contains only intended release changes.
2. Update `CHANGELOG.md` and package version.
3. Confirm affected ADR, specification, schema, and migration documents are current.
4. Stage every intended path, regenerate `GIT_TREE_MANIFEST.json`, stage it, and commit.
5. Run the complete validation ladder against the clean exact commit.
6. Build wheel and source distribution from a clean checkout.
7. Install the wheel into an isolated environment and run CLI smoke checks.
8. Create a signed Git tag through the organization release process.
9. Publish artifacts only after the tag and validation evidence agree.
10. Verify published hashes and record the immutable release references.

## Prohibited release behavior

- Publishing from an uncommitted working tree.
- Reusing a version number for different bytes.
- Claiming external deployment proof from local tests.
- Changing schemas without compatibility and migration evidence.
- Marking a stage successful before packet publication and validation complete.
