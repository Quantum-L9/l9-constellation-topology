"""Governed native-header predicates (predicate policy 1.2.0, ADR-0033).

The header predicates take their meaning from the Semantic Foundation's
``l9.artifact-header-model/global@1``: every one is a declaration the carrying
file makes about itself, and none may project a canonical entity or edge.
"""

from __future__ import annotations

import pytest

from l9_constellation_topology.domain.confidence import ConflictStatus
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
    HEADER_DECLARATION_PREDICATES,
    HEADER_SEMANTICS_LEDGER,
    UNSUPPORTED_PREDICATE_CODE,
    is_projectable,
    predicate_policy_hash,
    predicate_policy_view,
    predicate_support,
)
from l9_constellation_topology.stages.reconcile_assertions import run as reconcile_assertions
from l9_constellation_topology.topology.claim_projection import project_claims

ARTIFACT = "artifact:sample:docs-repo-map-md"

REQUIRED_DECLARATION_KEYS = {
    "definition",
    "subject_scope",
    "object_type",
    "cardinality",
    "support",
    "authority",
    "projection",
    "conflict",
    "unknown",
}


def _assertion(
    predicate: str,
    obj: str,
    *,
    subject: str = ARTIFACT,
    path: str = "docs/REPO_MAP.md",
    line: int = 1,
) -> RepositoryModelAssertion:
    return RepositoryModelAssertion(
        assertion_id=f"assertion:{predicate}:{obj}:{path}:{line}",
        subject_id=subject,
        predicate=predicate,
        object=obj,
        source_path=path,
        source_range=AssertionSourceRange(start_line=line, end_line=line),
        evidence_excerpt=f"{predicate.rsplit('.', 1)[-1]}: {obj}",
        source_content_hash="sha256:" + "a" * 64,
        extractor_id="native-metadata/v1",
        evidence_class="declared",
        authority="source",
        confidence="medium",
    )


def _reconcile(assertions: tuple[RepositoryModelAssertion, ...]):
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
    return reconcile_assertions(assertion_semantic_inputs(assertions), evidence)


# ── declarations ─────────────────────────────────────────────────────────────


def test_every_governed_header_predicate_declares_all_nine_properties() -> None:
    assert len(HEADER_DECLARATION_PREDICATES) == 60  # 30 fields x l9_schema 1 and 2
    for predicate, declaration in HEADER_DECLARATION_PREDICATES.items():
        assert set(declaration) == REQUIRED_DECLARATION_KEYS, predicate
        field = predicate.rsplit(".", 1)[-1]
        assert declaration["definition"] == f"{HEADER_SEMANTICS_LEDGER}#fields.{field}"
        assert declaration["subject_scope"] == "artifact"
        assert declaration["projection"] == "none"
        assert declaration["support"] == declaration["cardinality"]
        assert declaration["cardinality"] == (
            "set" if declaration["object_type"].endswith("_list") else "single"
        )
        assert predicate_support(predicate) == declaration["support"]
        assert predicate.split(".")[1] in {"l9v1", "l9v2"}


def test_the_policy_view_carries_the_header_semantics_it_applies() -> None:
    view = predicate_policy_view()
    assert view["version"] == "1.2.0"
    assert view["declaration_only_predicates"] == sorted(DECLARATION_ONLY_PREDICATES)
    header = view["header_semantics"]
    assert isinstance(header, dict)
    assert header["ledger"] == HEADER_SEMANTICS_LEDGER


def test_changing_a_header_declaration_changes_the_policy_hash() -> None:
    import l9_constellation_topology.reconciliation.predicates as predicates

    before = predicate_policy_hash()
    original = predicates.HEADER_DECLARATION_PREDICATES
    try:
        altered = dict(original)
        altered["meta.l9v1.governance.owner"] = {
            **original["meta.l9v1.governance.owner"],
            "projection": "owned_by",
        }
        predicates.HEADER_DECLARATION_PREDICATES = altered
        assert predicate_policy_hash() != before
    finally:
        predicates.HEADER_DECLARATION_PREDICATES = original
    assert predicate_policy_hash() == before


# ── reconciliation ───────────────────────────────────────────────────────────


def test_two_different_owner_declarations_conflict_and_elect_no_winner() -> None:
    claims, conflicts, unknowns, _ = _reconcile(
        (
            _assertion("meta.l9v1.governance.owner", "platform", line=4),
            _assertion("meta.l9v1.governance.owner", "engine-team", line=9),
        )
    )
    assert {claim.object for claim in claims} == {"platform", "engine-team"}
    assert len(conflicts) == 1
    assert conflicts[0].values == ("engine-team", "platform")
    assert conflicts[0].resolution is None
    assert conflicts[0].blocking is False
    assert all(claim.conflict_status is ConflictStatus.confirmed for claim in claims)
    assert unknowns == ()


def test_several_tags_aggregate_without_a_conflict() -> None:
    claims, conflicts, unknowns, _ = _reconcile(
        tuple(
            _assertion("meta.l9v1.classification.tags", tag, line=1)
            for tag in ("graph", "ci", "docs")
        )
    )
    assert {claim.object for claim in claims} == {"graph", "ci", "docs"}
    assert conflicts == ()
    assert unknowns == ()


def test_declarations_in_different_files_do_not_conflict() -> None:
    _, conflicts, _, _ = _reconcile(
        (
            _assertion(
                "meta.l9v1.classification.status", "active", subject="artifact:a", path="a.md"
            ),
            _assertion(
                "meta.l9v1.classification.status", "deprecated", subject="artifact:b", path="b.md"
            ),
        )
    )
    assert conflicts == ()


@pytest.mark.parametrize(
    "predicate",
    [
        "meta.l9v1.unresolved_field",
        "meta.l9v1.unsupported_field",
        "meta.unversioned.field",
        "meta.managed.governance.owner",
        "meta.l9v1.identity.owner",
    ],
)
def test_fields_without_a_governed_meaning_stay_unsupported(predicate: str) -> None:
    claims, conflicts, unknowns, diagnostics = _reconcile((_assertion(predicate, "role"),))
    assert predicate_support(predicate) == "unsupported"
    assert all(claim.support == "unsupported" for claim in claims)
    assert conflicts == ()
    assert [unknown.field for unknown in unknowns] == [predicate]
    assert [diagnostic.code for diagnostic in diagnostics] == [UNSUPPORTED_PREDICATE_CODE]


def test_governed_header_predicates_raise_no_unsupported_unknowns() -> None:
    _, _, unknowns, diagnostics = _reconcile(
        (
            _assertion("meta.declaration.carrier", "legacy-html"),
            _assertion("meta.declaration.schema", "l9_schema:1"),
            _assertion("meta.l9v1.governance.owner", "platform"),
            _assertion("meta.l9v1.governance.ssot_for", "module-boundaries"),
            _assertion("meta.l9v2.retrieval.load_when", "code_review"),
        )
    )
    assert unknowns == ()
    assert diagnostics == ()


# ── projection gate ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("predicate", sorted(DECLARATION_ONLY_PREDICATES))
def test_no_header_predicate_projects_anything(predicate: str) -> None:
    assert not is_projectable(predicate)
    claims, _, _, _ = _reconcile((_assertion(predicate, "Quantum-L9/l9-ci-core"),))
    projection = project_claims(claims)
    assert projection.capabilities == ()
    assert projection.edges == ()
    assert projection.nodes == ()
    assert projection.entities_by_claim == {}
    assert all(claim.projected is False for claim in claims)


def test_owner_ssot_and_references_create_no_ownership_governance_or_dependency_edge() -> None:
    """Negative dependency test with a positive control.

    Header declarations naming owners, governed scopes and references produce no
    edge, while a declared package dependency in the same compilation still does,
    so the absence is the gate working rather than projection being off.
    """
    header = (
        _assertion("meta.l9v1.governance.owner", "platform-team"),
        _assertion("meta.l9v1.governance.ssot_for", "module-boundaries"),
        _assertion("meta.l9v1.retrieval.references", "AGENTS.md"),
        _assertion("meta.l9v1.retrieval.requires", "l9_coding_kernel.v1"),
        _assertion("meta.l9v1.retrieval.load_when", "code_review"),
        _assertion("meta.l9v1.retrieval.amplifies", "agent_review_kernel.v1"),
    )
    control = _assertion(
        "package.dependency", "fastapi", subject="repo:sample", path="requirements.txt"
    )
    claims, _, _, _ = _reconcile((*header, control))
    projection = project_claims(claims)
    edge_types = {edge.edge_type for edge in projection.edges}
    assert "DEPENDS_ON" in edge_types  # the control projected
    assert not {"OWNED_BY", "GOVERNED_BY"} & edge_types
    header_claims = [claim for claim in claims if claim.predicate.startswith("meta.")]
    assert header_claims
    assert all(claim.projected is False for claim in header_claims)
    assert all(claim.claim_id not in projection.entities_by_claim for claim in header_claims)
    # Only the control's own claim reaches the graph.
    assert len(projection.edges) == 1
