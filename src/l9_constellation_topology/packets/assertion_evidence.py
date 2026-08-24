"""Bind every repository-model assertion to a first-class topology evidence record.

An assertion arrives already carrying its own proof: an exact line span in a named
file, the sha256 of that file's content, the extractor that read it, and the
excerpt it read. None of that survives if the assertion is carried as a bare
triple, and a claim whose evidence has been reduced to "the packet said so" is not
materially different from a guess.

So each assertion becomes an ``EvidenceRecord`` whose ``source_ref.content_hash``
is the *source file's* digest rather than the repository snapshot's. That is the
difference between "this file said this, and here is the file" and "some file in
this commit said this". The former survives an unrelated commit; the latter does
not, and downstream cannot tell the two apart after the fact.
"""

from __future__ import annotations

from datetime import UTC, datetime

from l9_constellation_topology.domain.confidence import (
    Authority,
    Completeness,
    ConfidenceAssessment,
    ConfidenceLevel,
    DerivationMethod,
    EvidenceStrength,
)
from l9_constellation_topology.reconciliation.inputs import SemanticInput
from l9_constellation_topology.run.evidence import (
    EvidenceRecord,
    EvidenceSourceRef,
    make_evidence_record,
)

from .repository_model import RepositoryModelAssertion, RepositoryModelPacket

#: Stage recorded on assertion-derived evidence.
ASSERTION_EVIDENCE_STAGE = "ingest_assertions"

#: ``created_at`` stamped onto assertion-derived evidence.
#:
#: The field is volatile rather than semantic — every semantic hash strips it —
#: but ``topology_payload_hashes`` serializes the evidence payload verbatim, so
#: reading the wall clock here would make an otherwise identical compile emit
#: different bytes. The producer's own observation instant is not carried on a
#: repository-model packet, so there is nothing truthful to record; a fixed,
#: obviously synthetic instant is recorded instead of a fabricated one.
ASSERTION_EVIDENCE_CREATED_AT = datetime(1970, 1, 1, tzinfo=UTC)

#: Producer authority vocabulary, mapped conservatively. An unrecognized value
#: resolves to ``unknown`` rather than to the nearest plausible upgrade.
_AUTHORITY_BY_NAME: dict[str, Authority] = {
    "source": Authority.source,
    "validated-machine": Authority.validated_machine,
    "validated_machine": Authority.validated_machine,
    "derived": Authority.derived,
    "candidate": Authority.candidate,
    "unknown": Authority.unknown,
}

#: Producer confidence vocabulary. An unrecognized value resolves to ``low``.
_LEVEL_BY_NAME: dict[str, ConfidenceLevel] = {
    "high": ConfidenceLevel.high,
    "medium": ConfidenceLevel.medium,
    "low": ConfidenceLevel.low,
}


def named_authority(value: str) -> Authority:
    """Map a producer authority name, never upgrading an unrecognized one."""
    return _AUTHORITY_BY_NAME.get(value, Authority.unknown)


def named_level(value: str) -> ConfidenceLevel:
    """Map a producer confidence name, never upgrading an unrecognized one."""
    return _LEVEL_BY_NAME.get(value, ConfidenceLevel.low)


def named_derivation(evidence_class: str) -> DerivationMethod:
    """Return how a producer arrived at a statement.

    ``declared`` means the source said it in prose or in a manifest; ``observed``
    means an extractor read it out of structure. Both are deterministic reads of
    a hashed span, and neither is a heuristic guess. The same mapping serves
    document work signals, which carry the same two-valued vocabulary.
    """
    return (
        DerivationMethod.declared
        if evidence_class == "declared"
        else DerivationMethod.deterministic
    )


def assertion_authority(assertion: RepositoryModelAssertion) -> Authority:
    """Return the topology authority of an assertion, never upgrading it."""
    return named_authority(assertion.authority)


def assertion_level(assertion: RepositoryModelAssertion) -> ConfidenceLevel:
    """Return the topology confidence level of an assertion, never upgrading it."""
    return named_level(assertion.confidence)


def assertion_derivation(assertion: RepositoryModelAssertion) -> DerivationMethod:
    """Return how the producer arrived at an assertion."""
    return named_derivation(assertion.evidence_class)


def assertion_confidence(assertion: RepositoryModelAssertion) -> ConfidenceAssessment:
    """Return the confidence of a single assertion's evidence."""
    return ConfidenceAssessment(
        level=assertion_level(assertion),
        # An assertion cites an exact span in a hashed file. That is direct
        # evidence for the claim, regardless of how strong the claim itself is.
        evidence_strength=EvidenceStrength.direct,
        derivation_method=assertion_derivation(assertion),
        authority=assertion_authority(assertion),
        # One span supports the claim; whether the claim as a whole is complete
        # is decided by reconciliation across every assertion that supports it.
        completeness=Completeness.sufficient,
    )


def assertion_evidence_value(assertion: RepositoryModelAssertion) -> dict[str, object]:
    """Return everything about an assertion that the evidence record must carry.

    The producer's ``assertion_id``, extractor identity, exact span, and read
    excerpt all live here, so a topology consumer can reconstruct precisely what
    was read and from where without resolving the parent packet out of band.
    """
    return {
        "assertion_id": assertion.assertion_id,
        "predicate": assertion.predicate,
        "object": assertion.object,
        "evidence_excerpt": assertion.evidence_excerpt,
        "extractor_id": assertion.extractor_id,
        "source_range": {
            "start_line": assertion.source_range.start_line,
            "end_line": assertion.source_range.end_line,
        },
        "declared_authority": assertion.authority,
        "declared_confidence": assertion.confidence,
    }


def assertion_evidence_record(
    assertion: RepositoryModelAssertion,
    *,
    packet: RepositoryModelPacket,
) -> EvidenceRecord:
    """Return the topology evidence record for one repository-model assertion."""
    return make_evidence_record(
        subject_id=assertion.subject_id,
        # The predicate is the field this evidence speaks to, which is what makes
        # a per-predicate conflict or unknown material to exactly the claims that
        # depend on it, and to nothing else.
        field=assertion.predicate,
        stage=ASSERTION_EVIDENCE_STAGE,
        evidence_class=assertion.evidence_class,
        source_type="file",
        source_ref=EvidenceSourceRef(
            source_path=assertion.source_path,
            line_number=assertion.source_range.start_line,
            # The source file's digest, not the repository snapshot's. A claim
            # must stay bound to the bytes that support it.
            content_hash=assertion.source_content_hash,
            packet_id=packet.packet_id,
            source_revision=packet.source_snapshot.revision,
        ),
        value=assertion_evidence_value(assertion),
        confidence=assertion_confidence(assertion),
        producer=packet.producer.name,
        producer_version=packet.producer.version,
        created_at=ASSERTION_EVIDENCE_CREATED_AT,
    )


def assertion_evidence_records(
    packet: RepositoryModelPacket,
) -> tuple[EvidenceRecord, ...]:
    """Return evidence for every assertion the packet carries, in packet order."""
    if packet.payload is None or not packet.payload.assertions:
        return ()
    return tuple(
        assertion_evidence_record(assertion, packet=packet)
        for assertion in packet.payload.assertions
    )


def assertion_semantic_input(assertion: RepositoryModelAssertion) -> SemanticInput:
    """Reduce an assertion to the shape reconciliation reads."""
    return SemanticInput(
        input_id=assertion.assertion_id,
        subject_id=assertion.subject_id,
        predicate=assertion.predicate,
        object=assertion.object,
        authority=assertion.authority,
        confidence=assertion.confidence,
        evidence_class=assertion.evidence_class,
        origin="repository-model",
    )


def assertion_semantic_inputs(
    assertions: tuple[RepositoryModelAssertion, ...],
) -> tuple[SemanticInput, ...]:
    return tuple(assertion_semantic_input(assertion) for assertion in assertions)
