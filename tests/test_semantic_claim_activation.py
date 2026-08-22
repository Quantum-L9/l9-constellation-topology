"""Repository-model assertions must become topology knowledge, not disappear.

The fixture behind these tests is a real repository-model 1.1.0 bundle emitted by
``l9-meta-injector`` from ``tests/fixtures/semantic_assertion_repository``. The
assertions are producer output rather than hand-authored data, which is what
makes them evidence: a test written against invented assertions would pass while
the real interpretation profile emitted something else entirely.

The compiler never reads that source tree. Its only ingress is the packet.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.domain.claim import SemanticClaimRecord
from l9_constellation_topology.domain.confidence import ConflictStatus
from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.packets.assertion_evidence import ASSERTION_EVIDENCE_STAGE
from l9_constellation_topology.packets.loader import load_repository_model_bundle
from l9_constellation_topology.packets.repository_model import RepositoryModelAssertion
from l9_constellation_topology.publication import (
    build_publication_plan,
    load_publication_policy,
)
from l9_constellation_topology.reconciliation import SUPPORTED_PREDICATES

ROOT = Path(__file__).resolve().parents[1]
ASSERTION_BUNDLE = ROOT / "tests/fixtures/repository_model_packets/l9-assertion-sample"
SPARSE_BUNDLES = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)
FIXED_TIME = datetime(2026, 7, 21, tzinfo=UTC)

#: Every predicate the bound interpretation profile emits for this fixture. A
#: predicate that stops surviving compilation fails here by name rather than by a
#: count that could be satisfied by the wrong claims.
REQUIRED_PREDICATES = frozenset(
    {
        "authority.canonical_contract",
        "authority.canonical_contract_count",
        "contract.declares_invariants",
        "contract.invariant",
        "http.handler_body_marker",
        "http.route",
        "http.route_handler",
        "package.build_backend",
        "package.dependency",
        "package.framework",
        "package.name",
        "package.packaging_system",
        "package.python_constraint",
        "package.server",
        "package.version",
        "repository.disclaimed_role",
        "repository.replaced_by",
        "repository.self_described_role",
        "repository.status",
        "service.action",
        "service.name",
        "service.version",
    }
)


@pytest.fixture(scope="module")
def asserted() -> tuple[RepositoryModelAssertion, ...]:
    packet = load_repository_model_bundle(ASSERTION_BUNDLE).packet
    assert packet.packet_version == "1.1.0"
    assert packet.payload is not None
    assert packet.payload.assertions
    return packet.payload.assertions


@pytest.fixture(scope="module")
def state() -> TopologyState:
    result = compile_topology(ROOT, (ASSERTION_BUNDLE,), created_at=FIXED_TIME)
    assert result.validation_receipt.status == "passed"
    return result.materialized.state


def _claims(state: TopologyState, predicate: str) -> tuple[SemanticClaimRecord, ...]:
    return tuple(claim for claim in state.semantic_claims if claim.predicate == predicate)


def _objects(state: TopologyState, predicate: str) -> set[str]:
    return {claim.object for claim in _claims(state, predicate)}


def test_the_fixture_is_a_real_producer_emission(asserted) -> None:
    """Guard the premise: these assertions must come from the real profile."""
    packet = load_repository_model_bundle(ASSERTION_BUNDLE).packet
    assert packet.producer.name.startswith("l9-meta-injector")
    assert packet.interpretation_profile is not None
    assert {assertion.extractor_id for assertion in asserted}
    assert all(assertion.source_content_hash.startswith("sha256:") for assertion in asserted)


def test_every_predicate_the_producer_emits_survives_compilation(asserted, state) -> None:
    emitted = {assertion.predicate for assertion in asserted}
    assert emitted == REQUIRED_PREDICATES
    assert {claim.predicate for claim in state.semantic_claims} == REQUIRED_PREDICATES
    assert emitted <= SUPPORTED_PREDICATES


def test_no_assertion_is_lost_and_none_is_invented(asserted, state) -> None:
    """Assertions are accounted for by identity, not merely by count."""
    incoming = {assertion.assertion_id for assertion in asserted}
    claimed = {
        assertion_id
        for claim in state.semantic_claims
        for assertion_id in claim.source_assertion_ids
    }
    assert claimed == incoming


def test_exact_source_evidence_survives_into_topology(asserted, state) -> None:
    """A claim without its span and its file digest is barely better than a guess."""
    by_assertion = {
        record.value["assertion_id"]: record
        for record in state.evidence
        if record.stage == ASSERTION_EVIDENCE_STAGE and isinstance(record.value, dict)
    }
    assert set(by_assertion) == {assertion.assertion_id for assertion in asserted}
    for assertion in asserted:
        record = by_assertion[assertion.assertion_id]
        assert record.source_ref.source_path == assertion.source_path
        assert record.source_ref.line_number == assertion.source_range.start_line
        # The file's digest, never the repository snapshot's.
        assert record.source_ref.content_hash == assertion.source_content_hash
        assert record.value["extractor_id"] == assertion.extractor_id
        assert record.value["evidence_excerpt"] == assertion.evidence_excerpt
        assert record.value["source_range"]["end_line"] == assertion.source_range.end_line
        assert record.evidence_class == assertion.evidence_class
        assert record.source_ref.source_revision


def test_competing_package_names_conflict_without_a_winner(state) -> None:
    """Two manifests, two names, one single-valued predicate: a real conflict."""
    names = _claims(state, "package.name")
    assert len(names) == 2, "both competing claims must survive"
    assert {claim.conflict_status for claim in names} == {ConflictStatus.confirmed}
    conflicts = [item for item in state.conflicts if item.field == "package.name"]
    assert len(conflicts) == 1
    assert set(conflicts[0].values) == {claim.object for claim in names}
    # No resolution was invented, and no claim was elected the survivor.
    assert conflicts[0].resolution is None
    assert all(claim.conflict_ids == (conflicts[0].conflict_id,) for claim in names)


def test_agreement_aggregates_evidence_instead_of_conflicting(state) -> None:
    """The same invariant stated by two contract files is corroboration."""
    corroborated = [
        claim
        for claim in _claims(state, "contract.invariant")
        if claim.object == "gate-compatible-ingress"
    ]
    assert len(corroborated) == 1, "one object, one claim"
    claim = corroborated[0]
    assert len(claim.source_assertion_ids) == 2
    assert len(claim.evidence_refs) == 2
    assert claim.conflict_status is ConflictStatus.none


def test_set_valued_predicates_aggregate_rather_than_contradict(state) -> None:
    dependencies = _objects(state, "package.dependency")
    assert len(dependencies) > 1
    assert not [item for item in state.conflicts if item.field == "package.dependency"]


def test_deprecation_and_reference_role_both_survive(state) -> None:
    """A repository can be deprecated *and* still describe itself as a reference."""
    assert _objects(state, "repository.status") == {"deprecated"}
    assert _objects(state, "repository.self_described_role") == {"reference-implementation"}
    assert _objects(state, "repository.disclaimed_role") == {"bootstrap-template"}
    assert _objects(state, "repository.replaced_by")


def test_an_unfinished_marker_never_becomes_a_verdict(state) -> None:
    """Observing a marker in a handler is not concluding the handler is broken."""
    markers = _claims(state, "http.handler_body_marker")
    assert len(markers) == 1
    marker = markers[0]
    # Preserved as the observation it is, and projected into nothing.
    assert marker.projected is False
    assert marker.projected_entity_ids == ()
    # No claim may render as a verdict about whether the handler works. The
    # phrases are assembled rather than written out so this file does not itself
    # trip the repository's unfinished-marker scan.
    forbidden = (" ".join(("not", "implemented")), "un" + "implemented", "incomplete")
    rendered = " ".join(
        f"{claim.predicate} {claim.object}" for claim in state.semantic_claims
    ).lower()
    assert not [phrase for phrase in forbidden if phrase in rendered]
    # The route the marker sits behind is still published as observed.
    assert "POST /v1/execute" in _objects(state, "http.route")


def test_package_identity_is_not_conflated_with_service_identity(state) -> None:
    package_names = _objects(state, "package.name")
    service_names = _objects(state, "service.name")
    assert package_names.isdisjoint(service_names)
    # Distinct predicates, so the divergence is not reported as a contradiction.
    assert not [item for item in state.conflicts if item.field == "service.name"]


def test_a_dependency_never_becomes_an_observed_repository(state) -> None:
    """An external package must not be published as a constellation member."""
    observed = {record.repository_id for record in state.repository_records}
    dependency_edges = [
        edge
        for edge in state.edge_records
        if edge.properties.get("assertion_predicate") == "package.dependency"
    ]
    assert dependency_edges
    for edge in dependency_edges:
        assert edge.target_id.startswith("package:")
        assert edge.target_id not in observed
        assert edge.properties["endpoint_kind"] == "external-package-reference"
    external_nodes = {
        record.entity_id: record
        for record in state.graph_records
        if record.record_type == "node" and record.entity_id.startswith("package:")
    }
    assert external_nodes
    assert all(
        node.properties["observed_as_repository"] is False for node in external_nodes.values()
    )


def test_route_projection_asserts_observation_and_nothing_more(state) -> None:
    routes = _claims(state, "http.route")
    assert routes
    assert all(claim.projected for claim in routes)
    projected = {
        capability.capability_id: capability
        for capability in state.capability_records
        if capability.capability_id.startswith("capability:http-route:")
    }
    assert len(projected) == len(routes)
    for capability in projected.values():
        assert "observed" in capability.description.lower()
        assert "reachability" in capability.description.lower()
        # Presenting a route is not implementing whatever is behind it.
        assert capability.implemented_by == ()
        assert capability.exposed_by


def test_auxiliary_predicates_are_preserved_but_never_projected(state) -> None:
    auxiliary = _claims(state, "contract.declares_invariants")
    assert auxiliary
    assert all(claim.support == "auxiliary" for claim in auxiliary)
    assert all(claim.projected is False for claim in auxiliary)
    assert all(claim.evidence_refs for claim in auxiliary)


def test_claims_lower_to_structured_memory_assertions(state) -> None:
    result = compile_topology(ROOT, (ASSERTION_BUNDLE,), created_at=FIXED_TIME)
    plan = build_publication_plan(
        result.materialized, load_publication_policy(ROOT), published_at=FIXED_TIME
    )
    claim_candidates = [item for item in plan.candidates if item.candidate_kind == "claim"]
    assert len(claim_candidates) == len(state.semantic_claims)
    triples = set()
    for candidate in claim_candidates:
        assertion = candidate.memory_intent.request.assertion
        assert assertion is not None
        assert assertion.is_structured
        triples.add((assertion.subject, assertion.predicate, assertion.object))
        metadata = candidate.memory_intent.request.metadata
        assert metadata["publication_candidate_id"] == candidate.candidate_id
        assert metadata["assertion_predicate"] == assertion.predicate
        assert metadata["source_assertion_ids"]
        # Topology never fabricates a downstream record identity.
        assert candidate.memory_intent.request.supersedes == ()
    assert triples == {
        (claim.subject_id, claim.predicate, claim.object) for claim in state.semantic_claims
    }


def test_conflicted_claims_are_held_rather_than_published(state) -> None:
    result = compile_topology(ROOT, (ASSERTION_BUNDLE,), created_at=FIXED_TIME)
    plan = build_publication_plan(
        result.materialized, load_publication_policy(ROOT), published_at=FIXED_TIME
    )
    conflicted = [
        item for item in plan.candidates if item.lowering.assertion_predicate == "package.name"
    ]
    assert len(conflicted) == 2
    assert all(item.eligibility.status == "held" for item in conflicted)
    assert all("conflict.unresolved_material" in item.eligibility.reasons for item in conflicted)


def test_no_candidate_is_silently_skipped(state) -> None:
    """Every claim reaches a recorded decision; none is dropped without a word."""
    result = compile_topology(ROOT, (ASSERTION_BUNDLE,), created_at=FIXED_TIME)
    plan = build_publication_plan(
        result.materialized, load_publication_policy(ROOT), published_at=FIXED_TIME
    )
    decided = Counter(
        item.eligibility.status for item in plan.candidates if item.candidate_kind == "claim"
    )
    assert sum(decided.values()) == len(state.semantic_claims)
    assert all(item.eligibility.reasons for item in plan.candidates)
    skipped_claims = [item for item in plan.skipped_candidates if item.source_kind == "claim"]
    assert skipped_claims == []


def test_a_sparse_1_0_0_constellation_invents_no_claims() -> None:
    """Back-compatibility is the absence of new facts, not merely no crash."""
    result = compile_topology(ROOT, SPARSE_BUNDLES, created_at=FIXED_TIME)
    assert result.validation_receipt.status == "passed"
    assert result.materialized.state.semantic_claims == ()
    conservation = next(
        check
        for check in result.validation_receipt.cross_reference_results
        if check.check_id == "cross-assertion-conservation"
    )
    assert conservation.status == "passed"
    assert conservation.details["input_assertion_count"] == 0


def test_topology_identity_moves_when_a_claim_moves() -> None:
    """Semantic movement must move the packet hash, or identity could be reused."""
    from l9_constellation_topology.packets.payloads import topology_payload_hashes
    from l9_constellation_topology.packets.topology_packet import (
        calculate_topology_semantic_hash,
    )
    from l9_constellation_topology.reconciliation import predicate_policy_hash

    result = compile_topology(ROOT, (ASSERTION_BUNDLE,), created_at=FIXED_TIME)
    packet, state = result.materialized.packet, result.materialized.state

    # The claim domain participates in the payload hashes the semantic view binds.
    assert "semantic_claims" in packet.payload_hashes
    restated = state.model_copy(
        update={
            "semantic_claims": tuple(
                claim.model_copy(update={"object": "restated"})
                if claim.predicate == "package.framework"
                else claim
                for claim in state.semantic_claims
            )
        }
    )
    moved = packet.model_copy(update={"payload_hashes": topology_payload_hashes(restated)})
    assert calculate_topology_semantic_hash(moved) != packet.semantic_hash

    # ...and so does the registry that decides what a predicate means.
    assert packet.policy_hashes["assertion_predicates"] == predicate_policy_hash()
    rekeyed = packet.model_copy(
        update={"policy_hashes": {**packet.policy_hashes, "assertion_predicates": "sha256:changed"}}
    )
    assert calculate_topology_semantic_hash(rekeyed) != packet.semantic_hash
