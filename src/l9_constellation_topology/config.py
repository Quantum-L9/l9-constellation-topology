"""Versioned configuration resolution for compiler profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.run.evidence import artifact_hash, semantic_hash


class ResolvedConfiguration(FrozenModel):
    topology_profile: dict[str, Any]
    risk_profile: dict[str, Any]
    maturity_profile: dict[str, Any]
    report_profile: dict[str, Any]
    packet_profile: dict[str, Any]
    output_policy: dict[str, Any]
    profile_hash: str
    schema_contract_hash: str
    active_contract_versions: dict[str, str] = Field(default_factory=dict)

    @property
    def profile_id(self) -> str:
        return str(self.topology_profile["id"])

    @property
    def profile_version(self) -> str:
        return str(self.topology_profile["version"])


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"required configuration file is missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"configuration must be a mapping: {path}")
    return data


def _contract_hash(root: Path) -> str:
    contract_dir = root / "contracts"
    members: dict[str, str] = {}
    for path in sorted(contract_dir.glob("*.json")):
        members[path.name] = artifact_hash(path.read_bytes())
    if not members:
        raise ValueError(f"no JSON contracts found in {contract_dir}")
    return semantic_hash(members)


def resolve_configuration(root: Path) -> ResolvedConfiguration:
    root = root.resolve()
    profiles = {
        "topology_profile": _load_yaml(root / ".l9" / "topology-profile.yaml"),
        "risk_profile": _load_yaml(root / ".l9" / "risk-profile.yaml"),
        "maturity_profile": _load_yaml(root / ".l9" / "maturity-profile.yaml"),
        "report_profile": _load_yaml(root / ".l9" / "report-profile.yaml"),
        "packet_profile": _load_yaml(root / ".l9" / "packet-profile.yaml"),
        "output_policy": _load_yaml(root / ".l9" / "output-policy.yaml"),
    }
    for name, profile in profiles.items():
        if "id" not in profile and name != "output_policy":
            raise ValueError(f"{name} is missing id")
        if "version" not in profile and name != "output_policy":
            raise ValueError(f"{name} is missing version")
    profile_hash = semantic_hash(profiles)
    return ResolvedConfiguration(
        **profiles,
        profile_hash=profile_hash,
        schema_contract_hash=_contract_hash(root),
        active_contract_versions={
            "repository_model_packet": "1.0.0",
            "topology_packet": "1.0.0",
            "validation_receipt": "1.0.0",
            "stage_dispatch": "1.0.0",
        },
    )
