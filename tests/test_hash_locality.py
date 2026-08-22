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
    # The four cases below are the ones v2 got wrong in the opposite direction to
    # v1. The logical fact is unchanged, so candidate identity must hold — but the
    # requested durable write is not the same write, and downstream answers a
    # repeated key with DUPLICATE rather than admitting the new epistemic state.
    "unchanged_fact_confidence_change": (None, None, SAME, CHANGED),
    "unchanged_fact_stronger_evidence": (None, None, SAME, CHANGED),
    "unchanged_fact_weaker_evidence": (None, None, SAME, CHANGED),
    "local_source_content_changes_but_claim_text_remains_same": (None, None, SAME, CHANGED),
    # ...and the three that must stay put, so v3 does not simply re-key on
    # everything and call the problem solved.
    "unchanged_fact_same_evidence_same_confidence": (SAME, SAME, SAME, SAME),
    "evidence_timestamp_only": (None, None, SAME, SAME),
    "source_repository_revision_only_with_same_local_content": (None, None, SAME, SAME),
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
        "unchanged_fact_same_evidence_same_confidence",
        "evidence_timestamp_only",
        "source_repository_revision_only_with_same_local_content",
    ):
        case = _by_case(recorded)[case_name]
        assert case["shared_candidates"] > 0, case_name
        assert case["shared_candidates_with_changed_effect_key"] == 0, case_name


def test_evaluation_records_the_active_algorithm_and_no_dispatch(
    recorded: dict[str, object],
) -> None:
    assert recorded["effect_identity_algorithm"] == EFFECT_IDENTITY_ALGORITHM_VERSION
    assert recorded["dispatches_performed"] == 0


def test_only_the_perturbed_write_moves_in_the_localized_cases(
    recorded: dict[str, object],
) -> None:
    """A case that must re-key one write must not re-key the whole plan.

    Without this, v3 could satisfy every "effect key moves" row by keying on
    something global again — the exact failure v1 was, wearing v3's number.
    """
    for case_name in (
        "unchanged_fact_confidence_change",
        "unchanged_fact_stronger_evidence",
        "unchanged_fact_weaker_evidence",
    ):
        case = _by_case(recorded)[case_name]
        assert case["shared_candidates"] > 1, case_name
        assert case["shared_candidates_with_changed_effect_key"] == 1, case_name
