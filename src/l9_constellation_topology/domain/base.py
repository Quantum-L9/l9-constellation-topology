"""Strict base models shared by the canonical topology domain."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Reject unknown fields so contract drift fails closed."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class FrozenModel(BaseModel):
    """Immutable canonical value object."""

    model_config = ConfigDict(extra="forbid", frozen=True)
