"""The recorded hash-locality matrix must state the contract, not merely exist.

``HASH_LOCALITY_EVALUATION.json`` is a generated artifact, so a drift check alone
would happily accept a regenerated file that recorded the wrong answers. These
tests assert the expected verdict of every case, so a change in identity locality
fails here rather than being blessed by regeneration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_hash_locality import build_matrix  # noqa: E402

from l9_constellation_topology.publication import (  # noqa: E402
    EFFECT_IDENTITY_ALGORITHM_VERSION,
)

EVALUATION = ROOT / "HASH_LOCALITY_EVALUATION.json"

SAME = "same"
CHANGED = "changed"

#: case -> (topology hash, plan hash, sampled candidate id, sampled effect key)
#:
#: ``None`` means the case does not constrain that identity: an unrelated change
#: is *permitted* to move a snapshot hash, and pinning it would assert more than
#: the contract requires.
EXPECTED: dict[str, tuple[str | None, str | None, str, str]] = {
    "exact_replay": (SAME, SAME, SAME, SAME),
    "checkout_path_only": (SAME, SAME, SAME, SAME),
    "wall_clock_only": (SAME, SAME, SAME, SAME),
    # The snapshot moved and the unaffected fact did not. This is the case the v1
    # algorithm failed: it re-keyed every effect in the plan.
    "unrelated_repository_fact": (CHANGED, None, SAME, SAME),
    "unrelated_topology_fact": (CHANGED, None, SAME, SAME),
    "published_fact_content": (None, None, CHANGED, CHANGED),
    "published_assertion": (None, None, CHANGED, CHANGED),
    # The logical fact is the same fact; the requested write is not the same write.
    "local_evidence_strength": (None, None, SAME, CHANGED),
    "namespace": (None, CHANGED, CHANGED, CHANGED),
    "memory_class": (None, CHANGED, CHANGED, CHANGED),
    "unrelated_publication_policy": (None, CHANGED, SAME, SAME),
}


@pytest.fixture(scope="module")
def recorded() -> dict[str, object]:
    return json.loads(EVALUATION.read_text(encoding="utf-8"))


def _by_case(matrix: dict[str, object]) -> dict[str, dict[str, object]]:
    cases = matrix["cases"]
    assert isinstance(cases, list)
    return {str(case["case"]): case for case in cases}


def test_recorded_matrix_matches_a_fresh_evaluation(recorded: dict[str, object]) -> None:
    assert _by_case(recorded) == _by_case(build_matrix())


def test_every_contract_case_is_present(recorded: dict[str, object]) -> None:
    assert set(_by_case(recorded)) == set(EXPECTED)


@pytest.mark.parametrize("case_name", sorted(EXPECTED))
def test_case_verdicts_match_the_identity_contract(
    recorded: dict[str, object], case_name: str
) -> None:
    case = _by_case(recorded)[case_name]
    topology, plan, candidate, effect = EXPECTED[case_name]
    if topology is not None:
        assert case["topology_semantic_hash"] == topology, case_name
    if plan is not None:
        assert case["publication_plan_semantic_hash"] == plan, case_name
    assert case["sampled_candidate_id"] == candidate, case_name
    assert case["sampled_effect_idempotency_key"] == effect, case_name


def test_unrelated_changes_move_no_shared_effect_key(recorded: dict[str, object]) -> None:
    """Locality is a property of the whole plan, not only of the sampled fact."""
    for case_name in (
        "exact_replay",
        "checkout_path_only",
        "wall_clock_only",
        "unrelated_repository_fact",
        "unrelated_topology_fact",
        "unrelated_publication_policy",
    ):
        case = _by_case(recorded)[case_name]
        assert case["shared_candidates"] > 0, case_name
        assert case["shared_candidates_with_changed_effect_key"] == 0, case_name


def test_evaluation_records_the_active_algorithm_and_no_dispatch(
    recorded: dict[str, object],
) -> None:
    assert recorded["effect_identity_algorithm"] == EFFECT_IDENTITY_ALGORITHM_VERSION
    assert recorded["dispatches_performed"] == 0
