"""Legacy v4 model compatibility surface.

Canonical v5 code imports from :mod:`l9_constellation_topology.domain`,
:mod:`l9_constellation_topology.packets`, and :mod:`l9_constellation_topology.run`.
The historical names remain stable here so existing scanner clients keep working.
"""

from l9_constellation_topology.compatibility.v4_models import *  # noqa: F403

# Non-colliding discoverability aliases for callers migrating to v5.
