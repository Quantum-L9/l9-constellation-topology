"""Policy-bounded direct observation fallback."""

from __future__ import annotations

from pathlib import Path

from l9_constellation_topology.compatibility.v4_models import RepoSource
from l9_constellation_topology.packets.adapters import NormalizedRepositoryModel
from l9_constellation_topology.scanners.repository_model_scanner import scan_repository_model


def run(
    *,
    repository_id: str,
    name: str,
    source_root: Path,
    expected_role: str | None,
    allowed: bool,
) -> NormalizedRepositoryModel:
    if not allowed:
        raise ValueError("direct observation fallback is disabled by the active profile")
    source = RepoSource(
        repo_id=repository_id.removeprefix("repo:"),
        name=name,
        local_path=str(source_root.resolve()),
        expected_role=expected_role or "UNKNOWN",
    )
    bundle = scan_repository_model(source)
    if bundle.packet.payload is None:
        raise ValueError("direct observation did not materialize a Repository Model payload")
    from l9_constellation_topology.packets.adapters import RepositoryModelV1Adapter

    return RepositoryModelV1Adapter().adapt(bundle.packet)
