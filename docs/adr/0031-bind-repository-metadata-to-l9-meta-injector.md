# ADR-0031: Bind repository metadata to `l9-meta-injector` through a central manifest

**Status:** Accepted (operator decision, 2026-11-03)

## Context

`l9-meta-injector` owns repository metadata projection; this repository owns
topology semantics and does not own source metadata injection (README). Until
now topology carried no metadata authority, so the producer it consumes could
not describe it.

The producer's `apply` and `check` modes refuse a repository without
`.l9/meta-authority.yaml`. Its `central_manifest` carrier records metadata in
`.l9/metadata-index.jsonl` and leaves every source file byte-identical, which
matters here: packet fixtures are hash-bound and must not be edited.

The first run at `v4.3.0` refused with `DUPLICATE_METADATA_ID`:
`schemas/graph-record.schema.json` and `schemas/graph_record.schema.json`
normalize to the same metadata id. The first is the canonical generated schema
(`scripts/generate_schemas.py`, `topology_validator.py`). The second was a
553-byte hand-written legacy card schema from the initial import that no code,
test, or script read.

## Decision

1. Declare `.l9/meta-authority.yaml` as `l9.meta-authority/v1`: writer
   `Quantum-L9/l9-meta-injector` ref `v4`, carrier `central_manifest`, legacy
   writers forbidden, no inline carriers.
2. Delete `schemas/graph_record.schema.json` (operator decision) so every
   tracked file has one metadata id.
3. Generate `.l9/metadata-index.jsonl` by hand with the released producer
   (`v4.3.0`, `c53ef3aa0ccea04af2adfe67800ad09843b6e0fe`) installed as a git
   dependency outside this tree, exactly as `DEVELOPMENT.md` records:
   authority `Quantum-L9`, namespace `l9-constellation-topology`, and
   `GIT_TREE_MANIFEST.json` omitted.
4. Add no CI job (operator decision). Metadata is refreshed manually; nothing
   in this repository's gates reads it.

`GIT_TREE_MANIFEST.json` is omitted because the two files cannot both be
current: the manifest records the index's blob id, and the index would record
the manifest's content hash.

## Consequences

- The metadata index is a derived artifact owned by the producer; it is never
  hand-edited and is never a compiler input.
- It goes stale whenever a tracked file changes. With no CI gate, `check`
  drift is expected between manual refreshes and is not a topology defect.
- No `package.json` or Node toolchain enters this repository.
- Compatibility and archive references to the deleted legacy schema under
  `docs/archive/` remain as history.

## Alternatives considered

**Omit the legacy schema instead of deleting it.** Rejected by the operator:
an unread duplicate-named schema has no reason to stay.

**Inline carriers.** Rejected: they rewrite source files, including
hash-bound fixtures.

**A `check` gate in `l9-pr-validate`.** Rejected by the operator for now: it
would force every pull request to regenerate the index.

## Compliance and validation

- The producer's own `check` mode, run with the flags in `DEVELOPMENT.md` on a
  clean export of the committed tree, reports `drift=0` and
  `authorityConflicts=0` at the commit that adds the index.
- `apply` writes only `.l9/metadata-index.jsonl`; a second run changes nothing.
- `scripts/validate_contracts.py` checks every remaining schema under
  `schemas/`; none references the deleted legacy schema.

## Related artifacts

- `.l9/meta-authority.yaml`
- `.l9/metadata-index.jsonl`
- `DEVELOPMENT.md` (Repository metadata)
- `schemas/graph-record.schema.json`
