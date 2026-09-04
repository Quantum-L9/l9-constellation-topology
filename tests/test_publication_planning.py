"""Publication boundary: lowering, eligibility, determinism, and containment."""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.domain.assessment import ConflictRecord, UnknownRecord
from l9_constellation_topology.domain.topology import TopologyState
from l9_constellation_topology.packets.common import PacketValidationRef
from l9_constellation_topology.packets.topology_packet import MaterializedTopology
from l9_constellation_topology.publication import (
    EligibilityContext,
    PublicationEligibilityError,
    PublicationPolicy,
    PublicationPolicyError,
    TopologyIndex,
    build_publication_plan,
    build_publication_plan_artifacts,
    eligible_intent_document,
    load_publication_policy,
    validate_publication_plan,
)
from l9_constellation_topology.publication.eligibility import (
    REASON_MATERIAL_CONFLICT,
    REASON_MATERIAL_UNKNOWN,
    REASON_MISSING_LINEAGE,
    REASON_UNRESOLVED_ENTITY,
)

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk",
    ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server",
)
PUBLICATION_SOURCE = ROOT / "src/l9_constellation_topology/publication"
FIXED_TIME = datetime(2026, 3, 1, tzinfo=UTC)
OTHER_TIME = datetime(2026, 9, 17, tzinfo=UTC)


@pytest.fixture(scope="module")
def materialized() -> MaterializedTopology:
    return compile_topology(ROOT, INPUTS, created_at=FIXED_TIME).materialized


@pytest.fixture(scope="module")
def policy() -> PublicationPolicy:
    return load_publication_policy(ROOT)


def _plan(materialized: MaterializedTopology, policy: PublicationPolicy, when: datetime):
    return build_publication_plan(materialized, policy, published_at=when)


def test_policy_resolves_with_stable_identity_and_hash(policy: PublicationPolicy) -> None:
    assert policy.identity == "foundational-topology-publication/1.0.0"
    assert policy.policy_hash().startswith("sha256:")
    assert policy.policy_hash() == load_publication_policy(ROOT).policy_hash()
    assert "CONTAINS" not in policy.eligible_edge_types
    assert "artifact" not in policy.eligible_entity_kinds


def test_missing_policy_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(PublicationPolicyError):
        load_publication_policy(tmp_path)


def test_plan_is_derived_and_leaves_topology_packet_unchanged(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    before = materialized.packet.model_copy(deep=True)
    before_state = materialized.state.model_copy(deep=True)
    plan = _plan(materialized, policy, FIXED_TIME)

    assert materialized.packet == before
    assert materialized.state == before_state
    assert plan.source_topology_semantic_hash == materialized.packet.semantic_hash
    assert plan.source_topology_packet.packet_id == materialized.packet.packet_id
    assert plan.plan_type == "l9.topology-publication-plan"


def test_plan_semantic_identity_ignores_publication_time(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    first = _plan(materialized, policy, FIXED_TIME)
    second = _plan(materialized, policy, OTHER_TIME)

    assert first.semantic_hash == second.semantic_hash
    assert first.plan_id == second.plan_id
    assert first.published_at != second.published_at


def test_candidate_and_idempotency_identity_are_deterministic(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    first = _plan(materialized, policy, FIXED_TIME)
    second = _plan(materialized, policy, OTHER_TIME)

    assert [item.candidate_id for item in first.candidates] == [
        item.candidate_id for item in second.candidates
    ]
    assert [item.idempotency_key for item in first.candidates] == [
        item.idempotency_key for item in second.candidates
    ]
    assert all(
        item.idempotency_key.startswith("l9-topology-publication/v3:") for item in first.candidates
    )
    assert len({item.candidate_id for item in first.candidates}) == len(first.candidates)


def test_candidate_and_skip_order_is_stable(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    plan = _plan(materialized, policy, FIXED_TIME)
    assert [item.candidate_id for item in plan.candidates] == sorted(
        item.candidate_id for item in plan.candidates
    )
    assert [(item.source_kind, item.source_id) for item in plan.skipped_candidates] == sorted(
        (item.source_kind, item.source_id) for item in plan.skipped_candidates
    )


def test_inert_policy_change_does_not_rekey_unchanged_facts(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    """A policy change that changes no requested write changes no key.

    Under v1 the whole policy hash was mixed into every key, so any policy edit
    re-keyed every effect in the plan and downstream saw a plan of brand-new
    facts. The facts had not moved; only the rules had. Raising the evidence
    ceiling above what any candidate actually uses is the clean case: no lowered
    request differs by a single field afterwards. The plan hash still records it.
    """
    baseline = _plan(materialized, policy, FIXED_TIME)
    inert_policy = policy.model_copy(
        update={
            "maximum_evidence_refs_per_candidate": policy.maximum_evidence_refs_per_candidate + 1
        }
    )
    shifted = build_publication_plan(materialized, inert_policy, published_at=FIXED_TIME)

    assert baseline.policy_hash != shifted.policy_hash
    assert [item.idempotency_key for item in baseline.candidates] == [
        item.idempotency_key for item in shifted.candidates
    ]


def test_confidence_policy_revision_rekeys_every_effect(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    """A policy version bump is not inert: every request carries the version.

    ``MemoryConfidence.policy_version`` is a field of the durable write, derived
    from the publication policy version. Bumping the version therefore changes
    what every request asks downstream to store. Reusing the previous key would
    have downstream answer ``DUPLICATE`` and keep the superseded version stamped
    on the record — the same class of silent loss v3 exists to prevent.

    The logical facts have not moved, so candidate identity must hold throughout.
    """
    baseline = _plan(materialized, policy, FIXED_TIME)
    shifted_policy = policy.model_copy(update={"version": "1.0.1"})
    shifted = build_publication_plan(materialized, shifted_policy, published_at=FIXED_TIME)

    assert [item.candidate_id for item in baseline.candidates] == [
        item.candidate_id for item in shifted.candidates
    ]
    assert {item.idempotency_key for item in baseline.candidates}.isdisjoint(
        {item.idempotency_key for item in shifted.candidates}
    )
    assert {
        item.memory_intent.request.confidence.policy_version for item in shifted.candidates
    } == {"l9-topology-publication/1.0.1"}


def test_policy_change_that_moves_an_effect_does_rekey_it(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    """A policy change with real effect semantics must change the keys.

    Namespace is part of what an effect *is*, not merely of how it was
    produced, so relocating published facts is a new set of effects.
    """
    baseline = _plan(materialized, policy, FIXED_TIME)
    moved_policy = policy.model_copy(update={"namespace_root": "l9-topology-relocated"})
    moved = build_publication_plan(materialized, moved_policy, published_at=FIXED_TIME)

    assert {item.idempotency_key for item in baseline.candidates}.isdisjoint(
        {item.idempotency_key for item in moved.candidates}
    )
    assert {item.candidate_id for item in baseline.candidates}.isdisjoint(
        {item.candidate_id for item in moved.candidates}
    )


def test_every_candidate_preserves_evidence_and_lineage(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    plan = _plan(materialized, policy, FIXED_TIME)
    known_evidence = {record.evidence_id for record in materialized.state.evidence}
    input_ids = {ref.packet_id for ref in materialized.packet.inputs.repository_model_packets}
    assert plan.candidates

    for candidate in plan.candidates:
        metadata = candidate.memory_intent.request.metadata
        assert metadata["topology_packet_id"] == materialized.packet.packet_id
        assert metadata["topology_semantic_hash"] == materialized.packet.semantic_hash
        assert metadata["topology_entity_ids"] == list(candidate.source_topology_entity_ids)
        assert set(metadata["repository_model_packet_ids"]) == input_ids
        assert set(candidate.source_repository_model_packet_ids) == input_ids
        assert set(candidate.source_evidence_ids) <= known_evidence
        provenance = candidate.memory_intent.request.provenance
        assert provenance.source_digest == materialized.packet.semantic_hash.removeprefix("sha256:")
        assert provenance.tool == "l9-constellation-topology/publication"


def test_published_records_state_the_revision_they_were_observed_at(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    """A memory record must not need its parent packet to say which commit it holds for."""
    plan = _plan(materialized, policy, FIXED_TIME)
    known_revisions = {
        record.source_ref.source_revision
        for record in materialized.state.evidence
        if record.source_ref.source_revision
    }
    assert known_revisions, "fixture must carry at least one revision-bound evidence record"

    carrying = 0
    for candidate in plan.candidates:
        metadata = candidate.memory_intent.request.metadata
        revisions = metadata["source_revisions"]
        paths = metadata["source_paths"]
        assert revisions == sorted(revisions)
        assert paths == sorted(paths)
        assert set(revisions) <= known_revisions
        assert len(paths) <= policy.maximum_evidence_refs_per_candidate
        if revisions:
            carrying += 1
    assert carrying == len(plan.candidates)


def test_source_locators_do_not_change_idempotency_identity(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    """Locators are descriptive metadata, so replay of an existing plan stays idempotent."""
    plan = _plan(materialized, policy, FIXED_TIME)
    for candidate in plan.candidates:
        key = candidate.memory_intent.request.idempotency_key
        assert key is not None
        assert candidate.idempotency_key == key
        assert not any(
            locator in key
            for locator in candidate.memory_intent.request.metadata["source_revisions"]
        )


def test_inferred_and_aggregated_intents_carry_admissible_evidence(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    plan = _plan(materialized, policy, FIXED_TIME)
    checked = 0
    for candidate in plan.eligible_candidates:
        confidence = candidate.memory_intent.request.confidence
        if confidence.method not in {"inferred", "aggregated"}:
            continue
        checked += 1
        evidence = candidate.memory_intent.request.evidence
        assert evidence
        assert any(item.kind in {"inference", "aggregation", "source_excerpt"} for item in evidence)
        assert confidence.evidence_count == len(evidence)
    assert checked, "fixture topology produced no derived-confidence candidates"


def test_confidence_is_never_upgraded(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    plan = _plan(materialized, policy, FIXED_TIME)
    for candidate in plan.candidates:
        level = candidate.lowering.confidence_level
        ceiling = min(
            policy.confidence_score_by_level[level],
            policy.confidence_conflict_ceiling[candidate.lowering.conflict_status],
        )
        assert candidate.memory_intent.request.confidence.score <= ceiling


def test_namespace_is_stable_and_never_a_checkout_path(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    plan = _plan(materialized, policy, FIXED_TIME)
    for candidate in plan.candidates:
        namespace = candidate.memory_intent.request.namespace
        assert namespace.startswith("l9.constellation/")
        assert not namespace.startswith("/")
        assert str(ROOT) not in namespace


def test_excluded_topology_facts_are_recorded_not_dropped(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    plan = _plan(materialized, policy, FIXED_TIME)
    skipped_ids = {item.source_id for item in plan.skipped_candidates}
    contains_edges = {
        edge.edge_id
        for edge in materialized.state.edge_records
        if str(edge.edge_type) not in set(policy.eligible_edge_types)
    }
    artifact_ids = {record.artifact_id for record in materialized.state.artifact_records}

    assert contains_edges <= skipped_ids
    assert artifact_ids <= skipped_ids
    planned = len(plan.candidates) + len(plan.skipped_candidates)
    assert planned == (
        len(materialized.state.edge_records)
        + len(materialized.state.artifact_records)
        + len(materialized.state.repository_records)
        + len(materialized.state.capability_records)
    )


def test_diagnostics_report_status_and_skip_counts(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    plan = _plan(materialized, policy, FIXED_TIME)
    codes = {item.code: item.count for item in plan.diagnostics}
    assert codes["candidates.eligible"] == len(plan.eligible_candidates)
    assert codes["candidates.held"] == len(plan.held_candidates)
    assert codes["candidates.rejected"] == len(plan.rejected_candidates)
    assert codes["skipped.policy.edge_type_not_selected"] >= 0
    assert "evidence.truncated" in codes


def _context(
    materialized: MaterializedTopology, policy: PublicationPolicy, state: TopologyState
) -> EligibilityContext:
    return EligibilityContext.build(
        policy=policy,
        packet=materialized.packet,
        state=state,
        index=TopologyIndex.build(state),
    )


def test_material_conflict_holds_the_affected_candidate(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    repository = materialized.state.repository_records[0]
    conflicted = materialized.state.model_copy(
        update={
            "conflicts": (
                ConflictRecord(
                    conflict_id="conflict:material",
                    subject_id=repository.repository_id,
                    field="primary_role",
                    values=("topology", "library"),
                ),
            )
        }
    )
    plan = build_publication_plan(
        MaterializedTopology(packet=materialized.packet, state=conflicted),
        policy,
        published_at=FIXED_TIME,
    )
    held = [
        item
        for item in plan.held_candidates
        if repository.repository_id in item.source_topology_entity_ids
    ]
    assert held
    assert REASON_MATERIAL_CONFLICT in held[0].eligibility.reasons
    assert "conflict:material" in held[0].lowering.observed_conflict_ids


def test_non_material_conflict_is_preserved_without_holding(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    repository = materialized.state.repository_records[0]
    conflicted = materialized.state.model_copy(
        update={
            "conflicts": (
                ConflictRecord(
                    conflict_id="conflict:immaterial",
                    subject_id=repository.repository_id,
                    field="owner_ids",
                    values=("a", "b"),
                ),
            )
        }
    )
    plan = build_publication_plan(
        MaterializedTopology(packet=materialized.packet, state=conflicted),
        policy,
        published_at=FIXED_TIME,
    )
    candidate = next(
        item
        for item in plan.candidates
        if item.source_topology_entity_ids == (repository.repository_id,)
    )
    assert candidate.eligibility.status == "eligible"
    assert "conflict:immaterial" in candidate.lowering.observed_conflict_ids
    assert (
        "conflict:immaterial" in candidate.memory_intent.request.metadata["observed_conflict_ids"]
    )


def test_material_unknown_holds_the_affected_candidate(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    repository = materialized.state.repository_records[0]
    with_unknown = materialized.state.model_copy(
        update={
            "unknowns": (
                UnknownRecord(
                    unknown_id="unknown:material",
                    subject_id=repository.repository_id,
                    field="source_revision",
                    reason="source revision could not be resolved",
                ),
            )
        }
    )
    plan = build_publication_plan(
        MaterializedTopology(packet=materialized.packet, state=with_unknown),
        policy,
        published_at=FIXED_TIME,
    )
    held = [
        item
        for item in plan.held_candidates
        if repository.repository_id in item.source_topology_entity_ids
    ]
    assert held
    assert REASON_MATERIAL_UNKNOWN in held[0].eligibility.reasons


def test_subject_wide_unknown_is_always_material(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    repository = materialized.state.repository_records[0]
    state = materialized.state.model_copy(
        update={
            "unknowns": (
                UnknownRecord(
                    unknown_id="unknown:subject",
                    subject_id=repository.repository_id,
                    field=None,
                    reason="subject is unresolved",
                ),
            )
        }
    )
    context = _context(materialized, policy, state)
    plan = build_publication_plan(
        MaterializedTopology(packet=materialized.packet, state=state),
        policy,
        published_at=FIXED_TIME,
    )
    assert context.known_entity_ids
    assert any(REASON_MATERIAL_UNKNOWN in item.eligibility.reasons for item in plan.held_candidates)


def test_unvalidated_topology_is_rejected(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    unvalidated = materialized.packet.model_copy(
        update={"validation": PacketValidationRef(status="failed")}
    )
    # Build args outside raises block so only build_publication_plan can raise (S5778)
    topology = MaterializedTopology(packet=unvalidated, state=materialized.state)
    with pytest.raises(PublicationEligibilityError):
        build_publication_plan(topology, policy, published_at=FIXED_TIME)


def test_missing_lineage_rejects_every_candidate(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    stripped = materialized.packet.model_copy(
        update={
            "inputs": materialized.packet.inputs.model_copy(update={"repository_model_packets": ()})
        }
    )
    plan = build_publication_plan(
        MaterializedTopology(packet=stripped, state=materialized.state),
        policy,
        published_at=FIXED_TIME,
    )
    assert plan.candidates
    assert not plan.eligible_candidates
    assert all(
        REASON_MISSING_LINEAGE in item.eligibility.reasons for item in plan.rejected_candidates
    )


def test_relationship_to_unknown_entity_is_rejected(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    edges = materialized.state.edge_records
    eligible = next(
        edge for edge in edges if str(edge.edge_type) in set(policy.eligible_edge_types)
    )
    detached = eligible.model_copy(update={"target_id": "artifact:not-in-this-topology"})
    state = materialized.state.model_copy(update={"edge_records": (detached,)})
    plan = build_publication_plan(
        MaterializedTopology(packet=materialized.packet, state=state),
        policy,
        published_at=FIXED_TIME,
    )
    assert plan.rejected_candidates
    assert REASON_UNRESOLVED_ENTITY in plan.rejected_candidates[0].eligibility.reasons


def test_artifact_entity_kind_is_unsupported_memory_semantics(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    widened = policy.model_copy(
        update={"eligible_entity_kinds": (*policy.eligible_entity_kinds, "artifact")}
    )
    with pytest.raises(ValueError, match="artifact entities"):
        build_publication_plan(materialized, widened, published_at=FIXED_TIME)


def test_relationship_candidates_are_structured_assertions(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    plan = _plan(materialized, policy, FIXED_TIME)
    relationships = [item for item in plan.candidates if item.candidate_kind == "relationship"]
    assert relationships
    for candidate in relationships:
        assertion = candidate.memory_intent.request.assertion
        assert assertion is not None
        assert assertion.is_structured
        assert candidate.memory_intent.request.memory_class == policy.relationship_memory_class


def test_entity_candidates_are_observations(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    plan = _plan(materialized, policy, FIXED_TIME)
    entities = [item for item in plan.candidates if item.candidate_kind == "entity"]
    assert entities
    for candidate in entities:
        assert candidate.memory_intent.request.memory_class == policy.entity_memory_class
        assert candidate.memory_intent.operation == "memory.ingest"


def test_plan_validates_against_the_checked_in_schema(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    plan = _plan(materialized, policy, FIXED_TIME)
    assert validate_publication_plan(plan, repository_root=ROOT) == ()


def test_plan_bundle_is_byte_deterministic(
    materialized: MaterializedTopology, policy: PublicationPolicy, tmp_path: Path
) -> None:
    first = build_publication_plan_artifacts(
        _plan(materialized, policy, FIXED_TIME), created_at=FIXED_TIME
    )
    second = build_publication_plan_artifacts(
        _plan(materialized, policy, FIXED_TIME), created_at=FIXED_TIME
    )
    assert [item.content_hash for item in first] == [item.content_hash for item in second]
    assert {item.destination_path for item in first} == {
        "publication-plan.json",
        "intents/memory-ingest.json",
        "manifest.json",
    }
    assert all(item.artifact_kind == "publication-plan" for item in first)


def test_intent_document_exposes_only_eligible_intents(
    materialized: MaterializedTopology, policy: PublicationPolicy
) -> None:
    plan = _plan(materialized, policy, FIXED_TIME)
    document = eligible_intent_document(plan)
    assert document["operation"] == "memory.ingest"
    assert len(document["intents"]) == len(plan.eligible_candidates)
    assert all(item["operation"] == "memory.ingest" for item in document["intents"])


def test_publication_module_imports_no_graph_or_memory_client() -> None:
    forbidden = {"neo4j", "graphiti", "l9_graphite_memory", "requests", "httpx", "urllib"}
    for path in sorted(PUBLICATION_SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".", 1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots = {node.module.split(".", 1)[0]}
            else:
                continue
            assert not (roots & forbidden), f"{path.name} imports {roots & forbidden}"


def test_publication_module_performs_no_dispatch_or_write() -> None:
    forbidden_calls = {
        "dispatch",
        "dispatch_root",
        "dispatch_follow_up",
        "write_text",
        "write_bytes",
        "unlink",
        "rename",
    }
    for path in sorted(PUBLICATION_SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls, f"{path.name}: {node.func.attr}"


def test_publication_policy_is_excluded_from_topology_configuration() -> None:
    """Publication policy must not participate in Topology Packet identity."""
    from l9_constellation_topology.config import ResolvedConfiguration, resolve_configuration

    configuration = resolve_configuration(ROOT)
    assert "publication" not in ResolvedConfiguration.model_fields
    policy_text = json.dumps(load_publication_policy(ROOT).raw(), sort_keys=True)
    assert configuration.profile_hash not in policy_text
    assert "publication" not in json.dumps(configuration.topology_profile, sort_keys=True)
