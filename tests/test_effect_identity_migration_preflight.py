"""Adopting v3 directly is only safe if no v2 key ever reached durable memory.

Changing the effect-identity algorithm rewrites every key this repository will
emit. If v2 keys were already admitted downstream, the v3 keys would look like
brand-new operations and every previously published fact would be re-admitted as
a duplicate record — which is a migration, not a version bump.

So the adoption rests on a claim that must be checked rather than assumed: this
repository has never dispatched anything. These tests check it from the
repository's own structure, so the claim stays true rather than being true once
on the day it was written.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from l9_constellation_topology.publication import EFFECT_IDENTITY_ALGORITHM_VERSION
from l9_constellation_topology.publication.identity import IDEMPOTENCY_NAMESPACE

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "l9_constellation_topology"
PREFLIGHT = ROOT / "EFFECT_IDENTITY_MIGRATION_PREFLIGHT.json"

#: Any of these reaching this repository would mean an intent could be executed
#: here rather than merely planned.
FORBIDDEN_CLIENT_ROOTS = frozenset({"neo4j", "graphiti", "l9_graphite_memory", "l9_gate_sdk"})


@pytest.fixture(scope="module")
def preflight() -> dict[str, object]:
    return json.loads(PREFLIGHT.read_text(encoding="utf-8"))


def test_the_recorded_preflight_names_the_algorithms_it_decided_between(
    preflight: dict[str, object],
) -> None:
    assert preflight["superseded_algorithm"] == "v2"
    assert preflight["adopted_algorithm"] == EFFECT_IDENTITY_ALGORITHM_VERSION
    assert preflight["durable_v2_dispatch_found"] is False
    assert preflight["decision"] == "adopt_v3_directly"


def test_no_module_imports_a_client_that_could_execute_an_intent() -> None:
    """A plan cannot have been dispatched by code that cannot dispatch."""
    offenders: list[str] = []
    for path in sorted(SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if name.split(".", 1)[0] in FORBIDDEN_CLIENT_ROOTS:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} {name}")
    assert offenders == []


def test_no_committed_artifact_carries_a_dispatched_effect_key() -> None:
    """A dispatch receipt, had one ever existed, would be checked in here.

    The pattern matches a *key* — the namespace, the version, and a full digest —
    rather than the bare prefix, so prose that discusses v2 (this file, the
    preflight record, the boundary document) is not mistaken for a key that was
    emitted.
    """
    marker = re.compile(re.escape(f"{IDEMPOTENCY_NAMESPACE}/v2:") + r"[0-9a-f]{64}")
    hits: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git/" in path.as_posix():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if marker.search(text):
            hits.append(path.relative_to(ROOT).as_posix())
    assert hits == []


def test_the_publication_boundary_still_forbids_dispatch(
    preflight: dict[str, object],
) -> None:
    """The preflight's conclusion depends on the boundary that produced it."""
    assert preflight["dispatch_surface_present"] is False
    evidence = preflight["evidence"]
    assert isinstance(evidence, list)
    assert evidence
