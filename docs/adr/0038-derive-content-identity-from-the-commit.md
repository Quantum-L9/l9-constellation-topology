# ADR-0038: Derive content identity from the commit, never a committed manifest

**Status:** Accepted on merge by the repository owner, who directed the change on 2026-11-11.

- **Decision owner:** Repository owner
- **Scope:** `scripts/git_tree_manifest.py`, `scripts/validate_git_integrity.py`, `scripts/validate_release_readiness.py`, `Repo.mk`, `.gitignore`, the release and operator procedures
- **Supersedes:** the `GIT_TREE_MANIFEST.json` part of the release-integrity remediation recorded in `CHANGELOG.md` and `VALIDATION.md`, and the `--omit GIT_TREE_MANIFEST.json` / regenerate step in [ADR-0031](0031-bind-repository-metadata-to-l9-meta-injector.md)

## Context

`GIT_TREE_MANIFEST.json` recorded the path, mode, object type, and Git object ID of every tracked entry except itself. `scripts/validate_git_integrity.py` failed any commit whose committed manifest differed from its tree, so every pull request that changed any file had to regenerate and commit the manifest.

That record adds nothing the commit does not already bind. A commit SHA names exactly one tree object, and that tree names every path, mode, object type, and object ID. The manifest only restated the commit, at the cost of:

- a generated file in every pull request, whatever the change;
- a textual conflict between any two open pull requests, because both rewrite the same file;
- a release and operator procedure with a regenerate-and-stage step (`RELEASING.md`, `RUNBOOK.md`, `DEVELOPMENT.md`, `REGRESSION_GUARD.md`).

The pull-request template already reports the changed files of every pull request (its machine-owned "Files touched" and "Changes by intent" sections), so the manifest is also not needed to show what a change touched.

## Decision

1. `GIT_TREE_MANIFEST.json` is not tracked. It is git-ignored at the repository root.
2. `scripts/validate_git_integrity.py` computes the content inventory from the validated commit (`git ls-tree` of `HEAD`) and reports the commit SHA, tree SHA, entry count, and the inventory digest `git_tree_entries_sha256`. CI writes that report to `validation/commit-bound-validation.json` as before. It fails a commit that tracks `GIT_TREE_MANIFEST.json`, so the file cannot return through a pull request.
3. `scripts/git_tree_manifest.py` prints the inventory of a treeish to standard output and writes nothing to the repository. Release evidence that needs the full inventory captures that output outside the tree.
4. The `git-manifest` make target and every regenerate-and-stage instruction are removed.

`MANIFEST.md` (the human responsibility inventory) and `FINAL_TREE.md` are unchanged by this decision.

## Consequences

- No pull request carries a generated content manifest, and two open pull requests no longer conflict on one.
- Commit-bound validation still names the exact commit, tree, and inventory digest it validated, now taken from Git rather than from a file the commit carries.
- The integrity report's schema changes: `git_tree_manifest_*`, `missing_from_git_tree_manifest`, `absent_from_git_tree`, and `content_identity_mismatches` are removed; `git_tree_entry_count` and `committed_tree_manifest` are added. `validation_tool_version` is `3.0.0`.
- Historical records that name `GIT_TREE_MANIFEST.json` (`CHANGELOG.md` history, `CHANGE_SUMMARY.md`, `FIX_MAP.md`, `CURRENT_VALIDATION_REPORT.md`, `reports/`) describe the state when they were written and are not rewritten.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Keep the committed manifest and have CI regenerate it after merge | A post-merge commit on `main` still changes the file, open pull requests still conflict with it, and CI writing to `main` adds a mutation path the validation ladder forbids ("validation never rewrites the worktree"). |
| Keep the manifest but mark it generated so conflicts self-resolve | Removes the conflict, not the per-pull-request regeneration, and the file still restates the commit. |
| Drop content identity from the integrity report entirely | Loses the inventory digest that release evidence cites; computing it from the commit costs nothing. |

## Compliance and validation

- `tests/test_git_integrity.py` proves a commit without the manifest passes, a commit that tracks `GIT_TREE_MANIFEST.json` fails, the inventory digest follows committed content, an inventory omission still fails, and `scripts/git_tree_manifest.py` writes nothing to the repository.
- `l9-pr-validate` runs `scripts/validate_git_integrity.py --out validation/commit-bound-validation.json` on every pull request, so the refusal is enforced in CI.
- `scripts/validate_release_readiness.py` no longer requires the file.

## Related artifacts

- [ADR-0031](0031-bind-repository-metadata-to-l9-meta-injector.md) — its `--omit GIT_TREE_MANIFEST.json` flag and regenerate step are no longer needed; the producer already skips git-ignored files.
- `scripts/git_tree_manifest.py`, `scripts/validate_git_integrity.py`, `scripts/validate_release_readiness.py`
- `RELEASING.md`, `RUNBOOK.md`, `DEVELOPMENT.md`, `REGRESSION_GUARD.md`, `VALIDATION.md`, `AGENTS.md` (2026-11-11 correction)
