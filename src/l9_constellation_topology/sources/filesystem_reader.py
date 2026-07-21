"""Read-only filesystem source adapter with path containment."""

from __future__ import annotations

from pathlib import Path

from l9_constellation_topology.run.evidence import normalize_source_path


class FileSystemSourceReader:
    def __init__(self, repository_id: str, root: Path, source_revision: str) -> None:
        self.repository_id = repository_id
        self.root = root.resolve()
        self.source_revision = source_revision
        if not self.root.is_dir():
            raise ValueError(f"source repository does not exist: {self.root}")

    def _resolve(self, path: str) -> Path:
        relative = normalize_source_path(path)
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"source path escapes repository root: {path}") from exc
        return candidate

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def read_bytes(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()

    def read_text(self, path: str) -> str:
        return self._resolve(path).read_text(encoding="utf-8")

    def iter_files(self) -> tuple[str, ...]:
        ignored = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
        files: list[str] = []
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(self.root)
            if any(part in ignored for part in relative.parts):
                continue
            files.append(relative.as_posix())
        return tuple(sorted(files))
