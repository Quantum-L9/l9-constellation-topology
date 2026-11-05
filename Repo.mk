# Repository-owned execution implementation for l9-constellation-topology (ADR-0032).
#
# The root Makefile is the generated, byte-identical make-v1 facade from
# Quantum-L9/l9-ci-core; it includes this file and routes the four portable
# phases to the repo-* leaves below. Everything else here is this repository's
# own command surface. Core forbids this file from defining help, setup,
# validate, check or test, so the former `test` target is `unit` and the former
# all-in-one `validate` target is the four phases together:
#
#   make setup validate check test
#
# Together the four phases run exactly the gate `make validate` ran before:
# compile, coverage, lint, type, contracts, workflows, architecture, readiness,
# generated-check (schemas, fixtures, hash-locality), git-integrity,
# determinism and build.

UV ?= uv
PYTHON ?= python
# Pinned to the version .github/workflows/l9-pr-validate.yml installs.
UV_VERSION ?= 0.10.0

.PHONY: sync compile unit coverage lint type contracts workflows architecture readiness schemas-check schemas-update fixtures-check fixtures-update generated-check generated-update git-manifest git-integrity determinism hash-locality hash-locality-update build clean
.PHONY: repo-setup repo-validate repo-check repo-test

sync:
	$(UV) sync --frozen --extra dev

compile:
	$(UV) run $(PYTHON) -m compileall src tests scripts -q

unit:
	$(UV) run pytest -q

coverage:
	$(UV) run pytest --cov=l9_constellation_topology --cov-report=term-missing -q

# CI runs both `ruff check` and `ruff format --check`. Keep them together here so a
# formatting-only failure cannot pass locally and then fail the PR validation job.
lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

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
# commit and this check is part of the `validate` phase.
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


clean:
	rm -rf .coverage coverage.xml htmlcov build dist .pytest_cache .ruff_cache .mypy_cache .wheel-smoke
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

# ── make-v1 phase leaves (Core repository execution V2) ────────────────────
#
# repo-setup reproduces .github/workflows/l9-pr-validate.yml exactly: Core's
# runner provides Python but not uv, and --no-build keeps third-party source
# distributions out of the environment, so the project itself is installed
# editable from its own tree with --no-deps.
repo-setup:
	command -v $(UV) >/dev/null 2>&1 || $(PYTHON) -m pip install --disable-pip-version-check --only-binary ":all:" uv==$(UV_VERSION)
	$(UV) sync --frozen --no-build --extra dev --no-install-project
	$(UV) pip install --no-deps --editable .

repo-validate: contracts workflows architecture readiness generated-check

repo-check: compile lint type

# git-integrity precedes build: it requires a clean working tree, and the
# coverage and build outputs it runs beside are gitignored.
repo-test: coverage git-integrity determinism build
