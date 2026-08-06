# OutputSink

All filesystem effects in production source are confined to `src/l9_constellation_topology/io/`.

The sink normalizes destinations, enforces root containment and artifact-kind policy, detects collisions, compares existing content, optionally checks expected hashes, skips unchanged content, stages atomic replacements, commits, and emits an itemized receipt. Dry-run produces a plan and no writes.


Packet bundles use a stronger commit protocol than ordinary projections: all files are written into a sibling staging directory, the staged bundle is reloaded and validated, files and directories are fsynced, and the complete directory is exposed through one atomic rename. Immutable existing bundles cannot be replaced. Execution receipts remain outside the canonical immutable packet bundle.
