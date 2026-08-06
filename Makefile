UV ?= uv
PYTHON ?= python

.PHONY: sync compile test coverage lint type contracts workflows architecture readiness schemas-check schemas-update fixtures-check fixtures-update generated-check generated-update git-manifest git-integrity determinism build validate clean

sync:
	$(UV) sync --frozen --extra dev

compile:
	$(UV) run $(PYTHON) -m compileall src tests scripts -q

test:
	$(UV) run pytest -q

coverage:
	$(UV) run pytest --cov=l9_constellation_topology --cov-report=term-missing -q

lint:
	$(UV) run ruff check .

type:
	$(UV) run mypy src/l9_constellation_topology

contracts:
	$(UV) run $(PYTHON) scripts/validate_contracts.py

workflows:
	$(UV) run $(PYTHON) scripts/validate_workflows.py

architecture:
	$(UV) run $(PYTHON) scripts/architecture_boundary_check.py

readiness:
	$(UV) run $(PYTHON) scripts/validate_release_readiness.py

schemas-check:
	$(UV) run $(PYTHON) scripts/generate_schemas.py --check

schemas-update:
	$(UV) run $(PYTHON) scripts/generate_schemas.py

# NOTE: fixture packets embed a wall-clock `created_at` and the live repository
# HEAD as `source_revision`, so a byte-for-byte regeneration check is only
# meaningful at the exact commit the fixtures were generated at. It is retained
# as an on-demand diagnostic and is intentionally NOT part of `validate` until
# fixture generation is made deterministic (see ROADMAP / follow-up).
fixtures-check:
	$(UV) run $(PYTHON) scripts/generate_fixture_packets.py --check

fixtures-update:
	$(UV) run $(PYTHON) scripts/generate_fixture_packets.py

generated-check: schemas-check fixtures-check

generated-update: schemas-update fixtures-update

git-manifest:
	$(UV) run $(PYTHON) scripts/git_tree_manifest.py

git-integrity:
	$(UV) run $(PYTHON) scripts/validate_git_integrity.py

determinism:
	$(UV) run $(PYTHON) scripts/verify_determinism.py

build:
	$(UV) build

validate: compile coverage lint type contracts workflows architecture readiness schemas-check git-integrity determinism build

clean:
	rm -rf .coverage coverage.xml htmlcov build dist .pytest_cache .ruff_cache .mypy_cache .wheel-smoke
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
