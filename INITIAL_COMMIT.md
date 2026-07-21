# Initial Commit Handoff

This archive is structured for a clean initial commit to
`Quantum-L9/l9-constellation-topology`.

## Pre-commit verification

```bash
make sync
make validate
```

Python 3.12 is canonical. A different interpreter may be used only for additional
informational checks and must not replace the canonical validation result.

## Initialize and push

```bash
git init -b main
git add -A
git status --short
git commit -m "Initialize packet-native topology compiler"
git remote add origin https://github.com/Quantum-L9/l9-constellation-topology.git
git push -u origin main
```

If the remote already has history, do not force-push blindly. Create a branch from
the remote default branch, compare the source tree, and merge through a pull request.

## Expected repository posture

- one top-level repository directory;
- no nested archives, build outputs, caches, secrets, or Git metadata;
- all root governance and operator files present;
- 20 accepted ADRs indexed by `ADR_INDEX.md`;
- full build specification preserved in `BUILD_SPECIFICATION.md`;
- manifest and final tree synchronized with the packaged files.
