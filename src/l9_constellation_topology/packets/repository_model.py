"""Repository Model Packet v1 contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from l9_constellation_topology.domain.artifact import ArtifactRecord
from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.domain.capability import CapabilityRecord
from l9_constellation_topology.domain.edge import EdgeRecord
from l9_constellation_topology.domain.repository import RepositoryRecord
from l9_constellation_topology.run.evidence import EvidenceRecord

from .common import PacketValidationRef, Producer, ProfileRef, SourceSnapshot


class RepositorySubject(FrozenModel):
    repository_id: str


class AssertionSourceRange(FrozenModel):
    """1-based inclusive line span inside ``source_path``."""

    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class RepositoryModelAssertion(FrozenModel):
    """A semantic claim the producing repository makes about itself.

    Added by repository-model packet 1.1.0. Every field is required: an
    assertion that cannot cite an exact span in a hashed source file is not a
    claim this pipeline is willing to carry.
    """

    assertion_id: str
    subject_id: str
    predicate: str
    object: str
    source_path: str
    source_range: AssertionSourceRange
    evidence_excerpt: str
    source_content_hash: str
    extractor_id: str
    evidence_class: Literal["declared", "observed"]
    authority: str
    confidence: str


class InterpretationProfileRef(FrozenModel):
    """Identity of the producer's interpretation profile, when it ran."""

    profile_id: str
    profile_version: str
    profile_hash: str
    extractor_versions: dict[str, str] = Field(default_factory=dict)


class RepositoryModelPayload(FrozenModel):
    repositories: tuple[RepositoryRecord, ...] = ()
    artifacts: tuple[ArtifactRecord, ...] = ()
    capabilities: tuple[CapabilityRecord, ...] = ()
    relationships: tuple[EdgeRecord, ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()
    diagnostics: tuple[dict[str, Any], ...] = ()
    #: ``None`` for 1.0.0 packets, which have no assertion domain at all, versus
    #: an empty tuple for a 1.1.0 packet whose interpretation found nothing. The
    #: distinction is load-bearing: a 1.0.0 packet must hash exactly as it was
    #: emitted, and serializing an absent domain as ``[]`` would change it.
    assertions: tuple[RepositoryModelAssertion, ...] | None = None


class RepositoryModelPacket(FrozenModel):
    packet_type: Literal["l9.repository-model"] = "l9.repository-model"
    packet_version: str
    packet_id: str
    subject: RepositorySubject
    source_snapshot: SourceSnapshot
    validation: PacketValidationRef
    producer: Producer
    profile: ProfileRef
    schema_hash: str
    semantic_hash: str
    artifact_hash: str | None = None
    payload_refs: dict[str, str] = Field(default_factory=dict)
    payload: RepositoryModelPayload | None = None
    #: Present only when the producer ran interpretation, mirroring the producer's
    #: rule that the profile binds identity exactly when it exists.
    interpretation_profile: InterpretationProfileRef | None = None
