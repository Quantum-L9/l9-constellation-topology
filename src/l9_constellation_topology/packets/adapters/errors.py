"""The failure a Meta generation raises when it cannot be trusted.

Kept in its own module because both the generation adapter and the work-signal
payload reader raise it, and the payload reader is imported *by* the adapter.
"""

from __future__ import annotations

__all__ = ["MetaGenerationError"]


class MetaGenerationError(ValueError):
    """Raised when a Meta generation cannot be read or is not self-consistent."""
