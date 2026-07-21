# OutputSink

All filesystem effects in production source are confined to `src/l9_constellation_topology/io/`.

The sink normalizes destinations, enforces root containment and artifact-kind policy, detects collisions, compares existing content, optionally checks expected hashes, skips unchanged content, stages atomic replacements, commits, and emits an itemized receipt. Dry-run produces a plan and no writes.
