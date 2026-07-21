UV ?= uv
PYTHON ?= python

.PHONY: sync compile test coverage lint type contracts workflows architecture readiness determinism build validate clean

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

determinism:
	$(UV) run $(PYTHON) scripts/verify_determinism.py

build:
	$(UV) build

validate: compile coverage lint type contracts workflows architecture readiness determinism build

clean:
	rm -rf .coverage coverage.xml htmlcov build dist .pytest_cache .ruff_cache .mypy_cache .wheel-smoke
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
