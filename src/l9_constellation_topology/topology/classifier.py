"""Profile-driven repository role classification with a legacy compatibility entrypoint."""

from __future__ import annotations

from l9_constellation_topology.compatibility.v4_models import Confidence, RepoCard
from l9_constellation_topology.domain import RepositoryRecord

_DEFAULT_ROLE_SIGNALS: dict[str, tuple[str, ...]] = {
    "api_gateway": ("gateway", "api-gateway", "ingress"),
    "agent": ("agent", "bot", "worker"),
    "library": ("lib", "sdk", "shared", "common"),
    "service": ("service", "svc", "microservice", "server"),
    "infrastructure": ("infra", "terraform", "helm", "k8s", "docker"),
    "data_pipeline": ("pipeline", "etl", "ingestion"),
    "frontend": ("frontend", "ui", "web", "app"),
    "topology": ("topology", "constellation", "map"),
    "memory": ("memory", "graphiti", "knowledge"),
    "documentation": ("docs", "documentation", "wiki"),
}


def classify_repository(
    record: RepositoryRecord,
    role_taxonomy: dict[str, list[str] | tuple[str, ...]] | None = None,
) -> RepositoryRecord:
    taxonomy = role_taxonomy or _DEFAULT_ROLE_SIGNALS
    searchable = " ".join(
        [record.name, *record.languages, *record.package_managers, *record.entrypoints]
    ).lower()
    matches = [
        role
        for role, signals in taxonomy.items()
        if any(signal.lower() in searchable for signal in signals)
    ]
    primary = record.primary_role
    secondary = list(record.secondary_roles)
    if primary in {"", "unknown", "UNKNOWN"} and matches:
        primary = matches[0]
        secondary.extend(matches[1:])
    else:
        secondary.extend(role for role in matches if role != primary)
    if primary in {"", "UNKNOWN"}:
        primary = "unknown"
    return record.model_copy(
        update={
            "primary_role": primary,
            "secondary_roles": tuple(dict.fromkeys(secondary)),
        }
    )


def classify_repo(card: RepoCard) -> RepoCard:
    """Legacy v4 compatibility classifier."""
    combined = f"{card.name} {card.path}".lower()
    matched = [
        role
        for role, signals in _DEFAULT_ROLE_SIGNALS.items()
        if any(signal in combined for signal in signals)
    ]
    if card.primary_role == "UNKNOWN" and matched:
        card.primary_role = matched[0]
        card.secondary_roles = list(dict.fromkeys(matched[1:]))
    elif matched:
        card.secondary_roles = list(
            dict.fromkeys(
                card.secondary_roles + [role for role in matched if role != card.primary_role]
            )
        )
    if card.primary_role == "UNKNOWN" and card.confidence == Confidence.low:
        card.primary_role = "service"
    return card
