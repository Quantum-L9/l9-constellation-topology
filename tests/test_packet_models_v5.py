from l9_constellation_topology.domain import ConfidenceAssessment, RepositoryRecord
from l9_constellation_topology.packets import (
    PacketValidationRef,
    Producer,
    ProfileRef,
    RepositoryModelPacket,
    RepositoryModelPayload,
    RepositorySubject,
    SourceSnapshot,
)
from l9_constellation_topology.packets.validator import (
    repository_model_semantic_view,
    validate_repository_model_packet,
)
from l9_constellation_topology.run.evidence import semantic_hash


def make_packet() -> RepositoryModelPacket:
    repository = RepositoryRecord(
        repository_id="repo:alpha",
        name="alpha",
        source_revision="git:abc",
        packet_ref="packet:alpha",
        confidence=ConfidenceAssessment.direct(),
    )
    packet_data = dict(
        packet_version="1.0.0",
        packet_id="packet:pending",
        subject=RepositorySubject(repository_id="repo:alpha"),
        source_snapshot=SourceSnapshot(revision="git:abc", semantic_hash="sha256:source"),
        validation=PacketValidationRef(status="passed", receipt_ref="packet://receipt"),
        producer=Producer(name="fixture", version="1.0.0"),
        profile=ProfileRef(id="repository-model", version="1.0.0", hash="sha256:profile"),
        schema_hash="sha256:schema",
        semantic_hash="sha256:pending",
        payload=RepositoryModelPayload(repositories=(repository,)),
    )
    candidate = RepositoryModelPacket(**packet_data)
    digest = semantic_hash(repository_model_semantic_view(candidate))
    return candidate.model_copy(update={"semantic_hash": digest, "packet_id": f"packet:{digest}"})


def test_repository_packet_validates() -> None:
    validate_repository_model_packet(make_packet())


def test_repository_packet_rejects_failed_parent() -> None:
    packet = make_packet().model_copy(
        update={"validation": PacketValidationRef(status="failed", receipt_ref="packet://receipt")}
    )
    try:
        validate_repository_model_packet(packet)
    except ValueError as exc:
        assert "input-validation-failed" in str(exc)
    else:
        raise AssertionError("failed parent validation was accepted")
