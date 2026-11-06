"""Managed header vocabulary (predicate policy 1.3.0) and the semantic claim view (ADR-0034).

The view is a pure read model over ``SemanticClaimRecord`` and ``EvidenceRecord``:
a declaration stays a declaration, an unknown field stays distinguishable from an
unknown predicate, and a conflict stays visible.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from l9_constellation_topology.cli import run
from l9_constellation_topology.domain.confidence import ConflictStatus
from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.packets.assertion_evidence import (
    assertion_evidence_record,
    assertion_semantic_inputs,
)
from l9_constellation_topology.packets.repository_model import (
    AssertionSourceRange,
    RepositoryModelAssertion,
    RepositoryModelPacket,
    RepositoryModelPayload,
)
from l9_constellation_topology.reconciliation import (
    DECLARATION_ONLY_PREDICATES,
    MANAGED_DECLARATION_PREDICATES,
    MANAGED_HEADER_VOCABULARY,
    UNSUPPORTED_PREDICATE_CODE,
    is_projectable,
    predicate_interpretation,
    predicate_policy_view,
    predicate_support,
)
from l9_constellation_topology.run.evidence import PdfLocator
from l9_constellation_topology.stages.reconcile_assertions import run as reconcile_assertions
from l9_constellation_topology.topology.claim_projection import project_claims
from l9_constellation_topology.topology.claim_view import (
    MAXIMUM_QUERY_LIMIT,
    ClaimQuery,
    SemanticClaimIndex,
    claim_view,
    interpretation_policy_ref,
    subject_kind,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests/fixtures/repository_model_packets/l9-assertion-sample"
SKILL = "artifact:sample:skills-demo-skill-md"
TOOL = "artifact:sample:tools-run-py"

#: Every field the producer's managed vocabulary defines (l9-meta-injector
#: ``MANAGED_VOCABULARY``), with the category it files the field under.
PRODUCER_MANAGED_VOCABULARY = {
    "id": "identity",
    "title": "identity",
    "namespace": "identity",
    "source_path": "identity",
    "artifact_type": "classification",
    "family": "classification",
    "mcp_primitive": "classification",
    "callable": "classification",
    "retrievable": "classification",
    "injectable": "classification",
    "authority": "governance",
    "owner": "governance",
    "sharing_scope": "governance",
}


def _assertion(
    predicate: str,
    obj: str,
    *,
    subject: str = SKILL,
    path: str = "skills/demo/SKILL.md",
    line: int = 1,
    revision_hash: str = "a",
) -> RepositoryModelAssertion:
    return RepositoryModelAssertion(
        assertion_id=f"assertion:{predicate}:{obj}:{path}:{line}",
        subject_id=subject,
        predicate=predicate,
        object=obj,
        source_path=path,
        source_range=AssertionSourceRange(start_line=line, end_line=line),
        evidence_excerpt=f"{predicate.rsplit('.', 1)[-1]}: {obj}",
        source_content_hash="sha256:" + revision_hash * 64,
        extractor_id="native-metadata/v1",
        evidence_class="declared",
        authority="source",
        confidence="medium",
    )


def _state(assertions: tuple[RepositoryModelAssertion, ...]) -> TopologyState:
    packet = RepositoryModelPacket(
        packet_version="1.1.0",
        packet_id="packet:fixture",
        subject={"repository_id": "repo:sample"},
        source_snapshot={"revision": "git:" + "0" * 40, "semantic_hash": "sha256:" + "b" * 64},
        validation={"status": "passed"},
        producer={"name": "fixture-producer", "version": "1.0.0"},
        profile={"id": "p", "version": "1.0.0", "hash": "sha256:" + "c" * 64},
        schema_hash="sha256:" + "d" * 64,
        semantic_hash="sha256:" + "e" * 64,
        payload=RepositoryModelPayload(assertions=assertions),
    )
    evidence = tuple(assertion_evidence_record(a, packet=packet) for a in assertions)
    claims, conflicts, unknowns, _ = reconcile_assertions(
        assertion_semantic_inputs(assertions), evidence
    )
    return TopologyState(
        semantic_claims=claims, evidence=evidence, conflicts=conflicts, unknowns=unknowns
    )


# ── D3: the managed vocabulary is recognized, conservatively ────────────────────


def test_every_producer_managed_field_is_registered_single_and_declaration_only() -> None:
    expected = {
        f"meta.managed.{category}.{field}"
        for field, category in PRODUCER_MANAGED_VOCABULARY.items()
    }
    assert set(MANAGED_DECLARATION_PREDICATES) == expected
    for predicate, declaration in MANAGED_DECLARATION_PREDICATES.items():
        field = predicate.rsplit(".", 1)[-1]
        assert declaration["definition"] == f"{MANAGED_HEADER_VOCABULARY}#fields.{field}"
        assert declaration["projection"] == "none"
        assert "not Foundation-governed" in declaration["authority"]
        assert predicate_support(predicate) == "single"
        assert predicate_interpretation(predicate) == "declaration"
        assert predicate in DECLARATION_ONLY_PREDICATES
        assert not is_projectable(predicate)


def test_case_f_a_future_managed_field_stays_unsupported() -> None:
    predicate = "meta.managed.classification.some_new_field"
    assert predicate_support(predicate) == "unsupported"
    assert predicate_interpretation(predicate) == "unsupported-predicate"
    assert not is_projectable(predicate)


@pytest.mark.parametrize(
    ("predicate", "interpretation"),
    [
        ("meta.managed.unresolved_field", "unresolved-value"),
        ("meta.l9v1.unresolved_field", "unresolved-value"),
        ("meta.l9v2.unresolved_field", "unresolved-value"),
        ("meta.managed.unsupported_field", "unsupported-field"),
        ("meta.l9v1.unsupported_field", "unsupported-field"),
        ("meta.unversioned.field", "unsupported-field"),
        ("meta.declaration.carrier", "auxiliary-observation"),
        ("contract.declares_invariants", "auxiliary-observation"),
        ("package.dependency", "declaration"),
        ("nobody.declared.this", "unsupported-predicate"),
    ],
)
def test_interpretation_keeps_the_five_readings_apart(predicate: str, interpretation: str) -> None:
    assert predicate_interpretation(predicate) == interpretation


def test_the_policy_view_names_the_managed_vocabulary_as_its_own_authority() -> None:
    view = predicate_policy_view()
    assert view["version"] == "1.4.0"
    managed = view["managed_header_semantics"]
    assert isinstance(managed, dict)
    assert managed["vocabulary"] == MANAGED_HEADER_VOCABULARY
    assert managed["declared_schema"] == "managed:l9-meta-injector"


def test_competing_single_valued_managed_declarations_stay_a_conflict() -> None:
    state = _state(
        (
            _assertion("meta.managed.classification.injectable", "true", line=2),
            _assertion("meta.managed.classification.injectable", "false", line=9),
        )
    )
    assert len(state.conflicts) == 1
    assert {claim.object for claim in state.semantic_claims} == {"true", "false"}
    assert all(claim.conflict_status is ConflictStatus.confirmed for claim in state.semantic_claims)


def test_managed_declarations_raise_no_unsupported_predicate_unknown() -> None:
    state = _state(
        (
            _assertion("meta.managed.classification.injectable", "true"),
            _assertion("meta.managed.governance.owner", "platform"),
            _assertion("meta.managed.unsupported_field", "legacy_key"),
        )
    )
    assert state.unknowns == ()
    assert project_claims(state.semantic_claims).edges == ()
    assert project_claims(state.semantic_claims).capabilities == ()


# ── D2: the read model ─────────────────────────────────────────────────────────


def test_case_d_a_declared_owner_is_retrievable_and_projects_nothing() -> None:
    state = _state((_assertion("meta.managed.governance.owner", "platform", line=4),))
    index = SemanticClaimIndex.from_state(state)
    result = index.query(ClaimQuery(predicate="meta.managed.governance.owner"))
    assert result.total_matched == 1
    view = result.claims[0]
    assert view.raw_value == "platform"
    assert view.interpretation == "declaration"
    assert view.value_kind == "label"
    assert view.authority.value == "source"
    assert view.projection_status == "not-projectable"
    assert view.projected_entity_ids == ()
    assert [(loc.source_path, loc.line_number) for loc in view.source_locations] == [
        ("skills/demo/SKILL.md", 4)
    ]
    assert view.missing_evidence_refs == ()
    assert view.definition_ref == f"{MANAGED_HEADER_VOCABULARY}#fields.owner"
    assert view.interpretation_policy_ref == interpretation_policy_ref()


def test_injectable_artifacts_are_discoverable_with_their_evidence() -> None:
    """Section 12: which artifacts declare themselves injectable, on what evidence."""
    state = _state(
        (
            _assertion("meta.managed.classification.injectable", "true", line=6),
            _assertion(
                "meta.managed.classification.injectable",
                "false",
                subject=TOOL,
                path="tools/run.py",
                line=3,
            ),
            _assertion(
                "meta.managed.classification.mcp_primitive",
                "tool",
                subject=TOOL,
                path="tools/run.py",
                line=4,
            ),
        )
    )
    index = SemanticClaimIndex.from_state(state)
    result = index.query(
        ClaimQuery(predicate="meta.managed.classification.injectable", value="true")
    )
    assert [view.subject_id for view in result.claims] == [SKILL]
    assert result.claims[0].value_kind == "boolean"
    assert result.claims[0].conflict_status is ConflictStatus.none
    everything_about_tool = index.query(ClaimQuery(subject_id=TOOL))
    assert {view.predicate for view in everything_about_tool.claims} == {
        "meta.managed.classification.injectable",
        "meta.managed.classification.mcp_primitive",
    }
    # Declared classification, never proof: nothing about the tool projected.
    assert all(view.projection_status == "not-projectable" for view in everything_about_tool.claims)


def test_filters_narrow_deterministically_and_the_bound_is_reported() -> None:
    state = _state(
        (
            *tuple(
                _assertion("meta.l9v1.classification.tags", f"tag-{index:02d}", line=index + 1)
                for index in range(5)
            ),
            _assertion("meta.managed.classification.injectable", "true", line=10),
            _assertion("meta.managed.classification.injectable", "false", line=11),
            _assertion("meta.managed.unresolved_field", "owner", line=12),
        )
    )
    index = SemanticClaimIndex.from_state(state)
    bounded = index.query(ClaimQuery(predicate_prefix="meta.l9v1", limit=2))
    assert (bounded.total_matched, bounded.returned, bounded.truncated) == (5, 2, True)
    assert [view.claim_id for view in bounded.claims] == sorted(
        view.claim_id for view in bounded.claims
    )
    assert index.query(ClaimQuery(predicate_prefix="meta.l9")).total_matched == 0
    conflicted = index.query(ClaimQuery(conflict="conflicted"))
    assert {view.raw_value for view in conflicted.claims} == {"true", "false"}
    assert index.query(ClaimQuery(conflict="none", predicate_prefix="meta.managed")).claims[
        0
    ].interpretation == ("unresolved-value")
    assert index.query(ClaimQuery(interpretation="unresolved-value")).total_matched == 1
    assert index.query(ClaimQuery(source_path="skills/demo/SKILL.md")).total_matched == 8
    assert index.query(ClaimQuery(subject_kind="artifact")).total_matched == 8


def test_corroboration_counts_distinct_source_locations() -> None:
    state = _state(
        (
            _assertion("meta.managed.governance.owner", "platform", line=2),
            _assertion(
                "meta.managed.governance.owner", "platform", path="skills/demo/README.md", line=2
            ),
        )
    )
    index = SemanticClaimIndex.from_state(state)
    assert index.query(ClaimQuery(minimum_locations=2)).total_matched == 1
    assert index.query(ClaimQuery(minimum_locations=3)).total_matched == 0


def test_corroboration_distinguishes_structured_locators_without_lines() -> None:
    """Two pages of one PDF are two places, though neither has a line number."""
    state = _state(
        (
            _assertion("meta.managed.governance.owner", "platform", path="docs/plan.pdf", line=1),
            _assertion("meta.managed.governance.owner", "platform", path="docs/plan.pdf", line=2),
        )
    )
    claim = state.semantic_claims[0]
    evidence = {
        record.evidence_id: record.model_copy(
            update={
                "source_ref": record.source_ref.model_copy(
                    update={
                        "line_number": None,
                        "locator": PdfLocator(page_number=page, block_index=0),
                    }
                )
            }
        )
        for page, record in enumerate(state.evidence, start=1)
    }
    index = SemanticClaimIndex([claim_view(claim, evidence)])
    assert index.query(ClaimQuery(minimum_locations=2)).total_matched == 1
    assert index.query(ClaimQuery(minimum_locations=3)).total_matched == 0


def test_differential_reports_a_confidence_only_re_reading() -> None:
    owner = _assertion("meta.managed.governance.owner", "platform", line=2)
    before = SemanticClaimIndex.from_state(_state((owner,)))
    after = SemanticClaimIndex.from_state(
        _state((owner.model_copy(update={"confidence": "high"}),))
    )
    changes = before.differential(after).changed
    assert [change.changed_fields for change in changes] == [("confidence",)]


def test_the_view_is_pure_and_reports_missing_evidence() -> None:
    state = _state((_assertion("meta.managed.governance.owner", "platform"),))
    claim = state.semantic_claims[0]
    view = claim_view(claim, {})
    assert view.source_locations == ()
    assert view.missing_evidence_refs == claim.evidence_refs
    assert state.semantic_claims[0] == claim


def test_unsupported_predicates_are_queryable_as_such() -> None:
    state = _state((_assertion("nobody.declared.this", "x"),))
    assert any(diagnostic for diagnostic in state.unknowns)
    view = SemanticClaimIndex.from_state(state).views[0]
    assert view.interpretation == "unsupported-predicate"
    assert view.support == "unsupported"
    assert view.cardinality == "unknown"
    assert UNSUPPORTED_PREDICATE_CODE  # the stage still emits its diagnostic


def test_differential_reports_added_removed_and_re_read_claims() -> None:
    before = SemanticClaimIndex.from_state(
        _state(
            (
                _assertion("meta.managed.governance.owner", "platform", line=2),
                _assertion("meta.managed.classification.injectable", "true", line=3),
            )
        )
    )
    after = SemanticClaimIndex.from_state(
        _state(
            (
                _assertion("meta.managed.governance.owner", "platform", line=5),
                _assertion("meta.managed.classification.retrievable", "true", line=6),
            )
        )
    )
    differential = before.differential(after)
    assert [view.predicate for view in differential.added] == [
        "meta.managed.classification.retrievable"
    ]
    assert [view.predicate for view in differential.removed] == [
        "meta.managed.classification.injectable"
    ]
    assert [change.changed_fields for change in differential.changed] == [("source_locations",)]
    assert before.differential(before).changed == ()
    scoped = before.differential(after, ClaimQuery(predicate="meta.managed.governance.owner"))
    assert (scoped.added, scoped.removed) == ((), ())


def test_keyset_pagination_walks_every_match_exactly_once() -> None:
    state = _state(
        tuple(
            _assertion("meta.l9v1.classification.tags", f"tag-{index:02d}", line=index + 1)
            for index in range(7)
        )
    )
    index = SemanticClaimIndex.from_state(state)
    seen: list[str] = []
    after: str | None = None
    pages = 0
    while True:
        page = index.query(ClaimQuery(predicate_prefix="meta.l9v1", limit=3, after=after))
        assert page.total_matched == 7
        seen.extend(view.claim_id for view in page.claims)
        pages += 1
        if not page.truncated:
            assert page.next_after is None
            break
        assert page.next_after == page.claims[-1].claim_id
        after = page.next_after
    assert pages == 3
    assert seen == sorted(view.claim_id for view in index.views)
    assert len(set(seen)) == 7
    # A cursor names its page exactly, on a freshly built index too.
    rebuilt = SemanticClaimIndex.from_state(state)
    resumed = rebuilt.query(ClaimQuery(limit=3, after=seen[2]))
    assert [view.claim_id for view in resumed.claims] == seen[3:6]
    assert resumed.next_after == seen[5]


def test_differential_separates_evidence_and_interpretation() -> None:
    owner = _assertion("meta.managed.governance.owner", "platform", line=2)
    before = SemanticClaimIndex.from_state(
        _state((owner,)), packet_predicate_policy_hash="sha256:a"
    )
    moved_owner = owner.model_copy(
        update={"source_range": AssertionSourceRange(start_line=9, end_line=9)}
    )
    moved = SemanticClaimIndex.from_state(
        _state((moved_owner,)), packet_predicate_policy_hash="sha256:a"
    )
    evidence_only = before.differential(moved)
    assert [change.categories for change in evidence_only.changed] == [("evidence",)]
    assert evidence_only.predicate_policy_changed is False
    assert evidence_only.changed[0].interpretation_under_changed_policy is False

    rival = _assertion("meta.managed.governance.owner", "infra", line=3)
    conflicted = SemanticClaimIndex.from_state(
        _state((owner, rival)), packet_predicate_policy_hash="sha256:a"
    )
    reconciled = before.differential(conflicted)
    original_id = before.views[0].claim_id
    changes = [change for change in reconciled.changed if change.claim_id == original_id]
    assert [change.categories for change in changes] == [("interpretation",)]
    assert changes[0].interpretation_under_changed_policy is False
    assert [view.raw_value for view in reconciled.added] == ["infra"]


def test_differential_attributes_interpretation_changes_to_a_policy_change() -> None:
    state = _state((_assertion("meta.managed.governance.owner", "platform", line=2),))
    before = SemanticClaimIndex.from_state(state, packet_predicate_policy_hash="sha256:old")
    recompiled = state.model_copy(
        update={
            "semantic_claims": tuple(
                claim.model_copy(update={"support": "unsupported", "cardinality": "unknown"})
                for claim in state.semantic_claims
            )
        }
    )
    after = SemanticClaimIndex.from_state(recompiled, packet_predicate_policy_hash="sha256:new")
    differential = before.differential(after)
    assert differential.predicate_policy_changed is True
    assert differential.before_predicate_policy_hash == "sha256:old"
    assert differential.after_predicate_policy_hash == "sha256:new"
    change = differential.changed[0]
    assert change.categories == ("interpretation",)
    assert change.changed_fields == ("support", "cardinality")
    assert change.interpretation_under_changed_policy is True
    # An unknown policy on either side never claims a policy change.
    assert (
        not SemanticClaimIndex.from_state(recompiled).differential(before).predicate_policy_changed
    )


def test_differential_reports_a_projection_change() -> None:
    dependency = _assertion(
        "package.dependency", "fastapi", subject="repo:sample", path="pyproject.toml"
    )
    state = _state((dependency,))
    before = SemanticClaimIndex.from_state(state)
    projected = state.model_copy(
        update={
            "semantic_claims": tuple(
                claim.model_copy(update={"projected": True, "projected_entity_ids": ("edge:x",)})
                for claim in state.semantic_claims
            )
        }
    )
    change = before.differential(SemanticClaimIndex.from_state(projected)).changed[0]
    assert change.categories == ("projection",)
    assert change.changed_fields == ("projection_status", "projected_entity_ids")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 0},
        {"limit": MAXIMUM_QUERY_LIMIT + 1},
        {"minimum_locations": -1},
        {"predicate_prefix": "."},
    ],
)
def test_queries_are_bounded(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ClaimQuery(**kwargs)  # type: ignore[arg-type]


def test_subject_kind_reads_the_identity_prefix() -> None:
    assert subject_kind("repo:sample") == "repository"
    assert subject_kind("artifact:sample:x") == "artifact"
    assert subject_kind("unprefixed") == "unknown"


# ── the read-only CLI entrypoint ───────────────────────────────────────────────


def test_query_claims_cli_answers_from_a_compiled_bundle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    args = ["compile-packet", "--repo-root", str(ROOT), "--input-bundle", str(SAMPLE)]
    assert run([*args, "--out", str(bundle)]) == 0
    capsys.readouterr()

    assert run(["query-claims", "--input-bundle", str(bundle), "--predicate", "http.route"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["interpretation_policy"]["matches_packet"] is True
    assert output["result"]["total_matched"] == 3
    for view in output["result"]["claims"]:
        assert view["interpretation"] == "declaration"
        assert view["projection_status"] == "projected"
        assert view["source_locations"]

    assert (
        run(["query-claims", "--input-bundle", str(bundle), "--compare-bundle", str(bundle)]) == 0
    )
    same = json.loads(capsys.readouterr().out)["differential"]
    assert (same["added"], same["removed"], same["changed"]) == ([], [], [])
    assert same["predicate_policy_changed"] is False
    assert same["before_predicate_policy_hash"] == same["after_predicate_policy_hash"]
    assert same["before_predicate_policy_hash"].startswith("sha256:")

    page = ["query-claims", "--input-bundle", str(bundle), "--predicate", "http.route"]
    assert run([*page, "--limit", "2"]) == 0
    first = json.loads(capsys.readouterr().out)["result"]
    assert (first["returned"], first["truncated"]) == (2, True)
    assert run([*page, "--limit", "2", "--after", first["next_after"]]) == 0
    second = json.loads(capsys.readouterr().out)["result"]
    assert (second["returned"], second["truncated"], second["next_after"]) == (1, False, None)
