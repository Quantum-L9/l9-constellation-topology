"""Capability aggregation and deterministic derivation."""

from __future__ import annotations

from collections import defaultdict

from l9_constellation_topology.domain import (
    ArtifactRecord,
    CapabilityRecord,
    ConfidenceAssessment,
    RepositoryRecord,
)


def build_capabilities(
    repositories: tuple[RepositoryRecord, ...],
    artifacts: tuple[ArtifactRecord, ...],
    declared: tuple[CapabilityRecord, ...],
) -> tuple[CapabilityRecord, ...]:
    by_id: dict[str, CapabilityRecord] = {item.capability_id: item for item in declared}
    {item.artifact_id: item for item in artifacts}

    for repository in repositories:
        for capability_id in repository.capability_ids:
            if capability_id in by_id:
                continue
            by_id[capability_id] = CapabilityRecord(
                capability_id=capability_id,
                name=capability_id.rsplit(":", 1)[-1],
                description=f"Capability declared by repository {repository.name}.",
                implemented_by=(repository.repository_id,),
                evidence_refs=repository.evidence_refs,
                confidence=repository.confidence,
            )

    artifact_implementers: dict[str, set[str]] = defaultdict(set)
    for artifact in artifacts:
        for capability_id in artifact.capabilities:
            artifact_implementers[capability_id].add(artifact.artifact_id)

    for capability_id, implementers in artifact_implementers.items():
        existing = by_id.get(capability_id)
        if existing is None:
            by_id[capability_id] = CapabilityRecord(
                capability_id=capability_id,
                name=capability_id.rsplit(":", 1)[-1],
                description="Capability derived from artifact declarations.",
                implemented_by=tuple(sorted(implementers)),
                confidence=ConfidenceAssessment.deterministic(),
            )
        else:
            by_id[capability_id] = existing.model_copy(
                update={
                    "implemented_by": tuple(sorted(set(existing.implemented_by) | implementers))
                }
            )
    return tuple(sorted(by_id.values(), key=lambda item: item.capability_id))
