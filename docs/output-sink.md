# OutputSink

All filesystem effects in production source are confined to `src/l9_constellation_topology/io/`.

The sink normalizes destinations, enforces root containment and artifact-kind policy, detects collisions, compares existing content, optionally checks expected hashes, skips unchanged content, stages atomic replacements, commits, and emits an itemized receipt. Dry-run produces a plan and no writes.


Packet bundles use a stronger commit protocol than ordinary projections: all files are written into a sibling staging directory, the staged bundle is reloaded and validated, files and directories are fsynced, and the complete directory is exposed through one atomic rename. Immutable existing bundles cannot be replaced. Execution receipts remain outside the canonical immutable packet bundle.

## Packet-type-aware post-write verification

The staged bundle is reloaded with the loader that owns the packet type its
manifest declares, resolved through `packets/bundle_verification.py`:

| Declared packet type | Verifier |
|---|---|
| `l9.topology` | `load_topology_bundle` |
| `l9.repository-model` | `load_repository_model_bundle` |

Both canonical Topology Packet bundles and the synthetic Repository Model bundles
produced by the compatibility scan are therefore verified under their own
contract. Verifying one with the other's loader reports contract violations that
do not exist — the Repository Model bundle has no `inputs` or `payload_hashes`
because it is not a Topology Packet — and hides any violation that does.

An unrecognized packet type fails closed rather than defaulting to a loader, and
verification is never disabled to let a write through.

## Failure reporting

A commit receipt records why each artifact failed. `io/failure_report.py` renders
it deterministically: failures first, then by destination path, naming the stage,
the packet type, the affected member, and the underlying reason. Because an atomic
bundle records one shared cause against every member, the cause is printed once
and the remaining members are named against it.

Reporting only the receipt status — `commit failed: failed` — is not an acceptable
operator surface: it names neither what failed nor why.
