"""Run and stage receipt value objects."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.run.evidence import utc_now


class StageReceipt(FrozenModel):
    stage: str
    status: Literal["passed", "failed", "not_run", "blocked"]
    input_hashes: tuple[str, ...] = ()
    output_hashes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)
