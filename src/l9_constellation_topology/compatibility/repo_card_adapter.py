"""Adapt proven v4 scanner output into canonical v5 records."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from l9_constellation_topology.compatibility.v4_models import Confidence, RepoCard, SourceType
from l9_constellation_topology.domain import (
    ArtifactRecord,
    CapabilityRecord,
    ConfidenceAssessment,
    RepositoryRecord,
    UnknownRecord,
)
from l9_constellation_topology.packets.adapters import NormalizedRepositoryModel
from l9_constellation_topology.run import (
    EvidenceSourceRef,
    artifact_hash,
    make_evidence_record,
    normalize_source_path,
    semantic_hash,
    stable_id,
)


def _confidence(value: Confidence) -> ConfidenceAssessment:
    if value == Confidence.high:
        return ConfidenceAssessment.deterministic(corroborated=True)
    if value == Confidence.medium:
        return ConfidenceAssessment.deterministic()
    return ConfidenceAssessment.candidate()


def _artifact_type(path: str) -> str:
    name = Path(path).name.lower()
    if name in {"pyproject.toml", "package.json", "requirements.txt", "cargo.toml", "go.mod"}:
        return "package-manifest"
    if ".github/workflows/" in path:
        return "ci-workflow"
    if "adr" in path.lower() and path.lower().endswith(".md"):
        return "architecture-decision"
    if name in {"codeowners", "owners", "maintainers", "governance.md", "security.md"}:
        return "governance"
    if name.startswith("readme"):
        return "documentation"
    return "source-artifact"


def adapt_repo_card(
    card: RepoCard,
    *,
    source_revision: str,
    packet_ref: str,
    repository_root: Path | None = None,
) -> tuple[NormalizedRepositoryModel, tuple[UnknownRecord, ...]]:
    repository_id = card.repo_id if card.repo_id.startswith("repo:") else f"repo:{card.repo_id}"
    confidence = _confidence(card.confidence)
    evidence_records = []
    path_to_evidence: dict[str, list[str]] = {}

    for item in card.evidence:
        source_path: str | None = None
        uri: str | None = None
        try:
            source_path = normalize_source_path(
                item.source_file,
                repository_root=repository_root if Path(item.source_file).is_absolute() else None,
            )
        except ValueError:
            uri = f"urn:l9:legacy-path:{semantic_hash(item.source_file).removeprefix('sha256:')}"
        source_type: Literal["file", "packet", "inference", "validation", "unknown"]
        if item.source_type == SourceType.file:
            source_type = "file"
        elif item.source_type == SourceType.inference:
            source_type = "inference"
        else:
            source_type = "unknown"
        evidence_class: Literal[
            "observed", "declared", "derived", "assisted", "projected", "validated", "committed"
        ] = "observed" if source_type == "file" else "derived"
        record = make_evidence_record(
            subject_id=repository_id,
            field=None,
            stage="legacy-direct-observation",
            evidence_class=evidence_class,
            source_type=source_type,
            source_ref=EvidenceSourceRef(
                uri=uri,
                source_path=source_path,
                line_number=item.line_number,
                source_revision=source_revision,
            ),
            value=item.excerpt,
            confidence=confidence,
            producer="l9-constellation-topology.legacy-scanner-adapter",
            producer_version="2.0.0",
        )
        evidence_records.append(record)
        if source_path is not None:
            path_to_evidence.setdefault(source_path, []).append(record.evidence_id)

    artifacts: list[ArtifactRecord] = []
    for source_path, evidence_refs in sorted(path_to_evidence.items()):
        content_hash = semantic_hash({"source_path": source_path, "evidence_refs": evidence_refs})
        if repository_root is not None:
            candidate = repository_root / source_path
            if candidate.is_file():
                content_hash = artifact_hash(candidate.read_bytes())
        artifact_id = stable_id(
            "artifact", {"repository_id": repository_id, "source_path": source_path}
        )
        artifacts.append(
            ArtifactRecord(
                artifact_id=artifact_id,
                repository_id=repository_id,
                source_path=source_path,
                artifact_type=_artifact_type(source_path),
                content_hash=content_hash,
                evidence_refs=tuple(sorted(evidence_refs)),
                packet_ref=packet_ref,
                confidence=confidence,
            )
        )

    roles = tuple(dict.fromkeys([card.primary_role, *card.secondary_roles]))
    capabilities = tuple(
        CapabilityRecord(
            capability_id=f"capability:{card.repo_id}:{role}",
            name=role,
            description=f"Repository role capability observed for {card.name}.",
            implemented_by=(repository_id,),
            evidence_refs=tuple(record.evidence_id for record in evidence_records[:5]),
            confidence=confidence,
        )
        for role in roles
        if role and role != "UNKNOWN"
    )

    owners = () if card.owner == "UNKNOWN" else (f"owner:{card.owner}",)
    repository = RepositoryRecord(
        repository_id=repository_id,
        name=card.name,
        source_revision=source_revision,
        packet_ref=packet_ref,
        primary_role=card.primary_role.lower() if card.primary_role != "UNKNOWN" else "unknown",
        secondary_roles=tuple(role.lower() for role in card.secondary_roles),
        languages=tuple(sorted(set(card.languages))),
        package_managers=tuple(sorted(set(card.package_managers))),
        entrypoints=tuple(sorted(set(card.entrypoints))),
        workflows=tuple(sorted(set(card.ci_workflows))),
        adr_refs=tuple(sorted(set(card.adr_files))),
        governance_refs=tuple(sorted(set(card.governance_files))),
        capability_ids=tuple(capability.capability_id for capability in capabilities),
        artifact_ids=tuple(artifact.artifact_id for artifact in artifacts),
        unresolved_dependencies=tuple(sorted(set(card.upstream_dependencies))),
        owner_ids=owners,
        evidence_refs=tuple(record.evidence_id for record in evidence_records),
        confidence=confidence,
    )
    unknowns: list[UnknownRecord] = []
    if not card.path or card.confidence == Confidence.low:
        unknowns.append(
            UnknownRecord(
                unknown_id=stable_id(
                    "unknown", {"repository_id": repository_id, "field": "source"}
                ),
                subject_id=repository_id,
                field="source",
                reason="legacy scanner produced low-confidence or unavailable source evidence",
                evidence_refs=repository.evidence_refs,
            )
        )
    model = NormalizedRepositoryModel(
        repositories=(repository,),
        artifacts=tuple(artifacts),
        capabilities=capabilities,
        relationships=(),
        evidence=tuple(evidence_records),
        diagnostics=(),
    )
    return model, tuple(unknowns)
