from pathlib import Path

from l9_constellation_topology.config import ResolvedConfiguration, resolve_configuration


def run(root: Path) -> ResolvedConfiguration:
    return resolve_configuration(root)
