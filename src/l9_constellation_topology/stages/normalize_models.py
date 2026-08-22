"""Combine adapted packet models without losing packet boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from l9_constellation_topology.domain import (
    ArtifactRecord,
    CapabilityRecord,
    EdgeRecord,
    RepositoryRecord,
)
from l9_constellation_topology.packets.adapters import NormalizedRepositoryModel
from l9_constellation_topology.packets.repository_model import RepositoryModelAssertion
from l9_constellation_topology.run import Diagnostic, EvidenceRecord


@dataclass(frozen=True)
class NormalizedInputs:
    repositories: tuple[RepositoryRecord, ...]
    artifacts: tuple[ArtifactRecord, ...]
    capabilities: tuple[CapabilityRecord, ...]
    relationships: tuple[EdgeRecord, ...]
    evidence: tuple[EvidenceRecord, ...]
    diagnostics: tuple[Diagnostic, ...]
    #: Empty for a constellation of 1.0.0 packets, which carry no assertion
    #: domain at all. Packet boundaries are not lost by flattening: every
    #: assertion keeps the producer's content-addressed identity, and the
    #: evidence built for it at the packet boundary names the parent packet.
    assertions: tuple[RepositoryModelAssertion, ...] = ()


def run(models: tuple[NormalizedRepositoryModel, ...]) -> NormalizedInputs:
    return NormalizedInputs(
        repositories=tuple(record for model in models for record in model.repositories),
        artifacts=tuple(record for model in models for record in model.artifacts),
        capabilities=tuple(record for model in models for record in model.capabilities),
        relationships=tuple(record for model in models for record in model.relationships),
        evidence=tuple(record for model in models for record in model.evidence),
        diagnostics=tuple(record for model in models for record in model.diagnostics),
        assertions=tuple(record for model in models for record in model.assertions),
    )
