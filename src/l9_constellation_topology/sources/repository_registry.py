"""Explicit repository source registry for bounded fallback observation."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class RepositoryRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_id: str
    name: str
    local_path: str
    remote_url: str | None = None
    expected_role: str | None = None


class RepositoryRegistry:
    def __init__(self, entries: tuple[RepositoryRegistryEntry, ...]) -> None:
        self.entries = entries
        self._by_id = {entry.repository_id: entry for entry in entries}

    @classmethod
    def from_yaml(cls, path: Path) -> RepositoryRegistry:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        raw_entries = data.get("repo_sources", []) if isinstance(data, dict) else []
        entries = tuple(
            RepositoryRegistryEntry(
                repository_id=(
                    str(item.get("repository_id") or item.get("repo_id"))
                    if str(item.get("repository_id") or item.get("repo_id")).startswith("repo:")
                    else f"repo:{item.get('repository_id') or item.get('repo_id')}"
                ),
                name=str(item["name"]),
                local_path=str(item["local_path"]),
                remote_url=(
                    None if item.get("remote_url") in {None, "UNKNOWN"} else str(item["remote_url"])
                ),
                expected_role=(
                    None
                    if item.get("expected_role") in {None, "UNKNOWN"}
                    else str(item["expected_role"])
                ),
            )
            for item in raw_entries
        )
        return cls(entries)

    def get(self, repository_id: str) -> RepositoryRegistryEntry | None:
        canonical = repository_id if repository_id.startswith("repo:") else f"repo:{repository_id}"
        return self._by_id.get(canonical)
