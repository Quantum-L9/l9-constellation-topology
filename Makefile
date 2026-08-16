UV ?= uv
PYTHON ?= python

.PHONY: sync compile test coverage lint type contracts workflows architecture readiness schemas-check schemas-update fixtures-check fixtures-update generated-check generated-update git-manifest git-integrity determinism hash-locality hash-locality-update build validate clean

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

# Fixture generation pins `created_at` and derives `source_revision` from the
# sample tree's own content, so regeneration is byte-for-byte reproducible at any
# commit and this check is part of `validate`.
fixtures-check:
	$(UV) run $(PYTHON) scripts/generate_fixture_packets.py --check

fixtures-update:
	$(UV) run $(PYTHON) scripts/generate_fixture_packets.py

hash-locality-update:
	$(UV) run $(PYTHON) scripts/evaluate_hash_locality.py

generated-check: schemas-check fixtures-check hash-locality

generated-update: schemas-update fixtures-update hash-locality-update

git-manifest:
	$(UV) run $(PYTHON) scripts/git_tree_manifest.py

git-integrity:
	$(UV) run $(PYTHON) scripts/validate_git_integrity.py

determinism:
	$(UV) run $(PYTHON) scripts/verify_determinism.py

hash-locality:
	$(UV) run $(PYTHON) scripts/evaluate_hash_locality.py --check

build:
	$(UV) build

validate: compile coverage lint type contracts workflows architecture readiness generated-check git-integrity determinism hash-locality build

clean:
	rm -rf .coverage coverage.xml htmlcov build dist .pytest_cache .ruff_cache .mypy_cache .wheel-smoke
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
