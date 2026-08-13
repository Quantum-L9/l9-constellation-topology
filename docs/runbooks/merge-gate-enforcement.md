# Runbook: Enforce the governed merge gate on `main` (audit F-01)

## Why this exists

The runtime-enforcement audit (2026-08-13) recorded a `CRITICAL` bypass: pull request
`#3` merged into protected `main` **after** the governed check `l9-pr-validate / validate`
had concluded `failure` (run `31082040352`). A tree the repository's own validation
rejected became accepted `main` state.

This is not a code defect and cannot be fixed by any change in this repository. The GitHub
*merge* operation was not technically dependent on the governed check succeeding. The fix
lives entirely in GitHub branch-protection / repository-ruleset configuration, which
requires repository-admin access. This runbook records the required configuration and a
negative test that proves it.

The exact ruleset/bypass configuration in force at the time of the audit was inaccessible
(`branch protection API` returned an authorization/plan error), so the current state is an
audit `UNKNOWN`. Apply the configuration below and verify with the negative test.

## Required configuration

Configure a ruleset (or classic branch protection) on `main` with:

1. **Require a pull request before merging.** Direct pushes to `main` are prohibited by
   `GOVERNANCE.md`; enforce that at the ruleset, not only in documentation.
2. **Require status checks to pass**, and add the exact context
   **`l9-pr-validate / validate`** to the required set. Require branches to be up to date
   before merging so the check runs against the merge result.
3. **Do not allow bypass.** Remove role/app/actor bypass entries. If an emergency
   break-glass path is genuinely required, make it a separate, explicitly named,
   time-boxed, and auditable bypass — never an always-on admin override.
4. **Include administrators** so the rule applies to maintainers as well.
5. Keep the check `l9-pr-validate` wired as the authoritative gate (its ladder is defined
   in `.github/workflows/l9-pr-validate.yml`).

## Negative test (must pass before closing F-01)

1. Open a pull request whose governed check will fail — for example a branch that
   deliberately leaves `MANIFEST.md` out of sync so
   `scripts/validate_release_readiness.py` reports blocking findings (the exact failure
   mode from PR `#3`).
2. Wait for `l9-pr-validate / validate` to conclude `failure`.
3. Confirm the merge button is **blocked** and the merge cannot be completed by any actor,
   including administrators (except through the explicit, audited break-glass path if one
   is configured).
4. Push a fix so the governed check passes, then confirm the merge becomes available.

Record the ruleset export and the negative-test result alongside the audit evidence.

## Related remediations already applied in code

- Freshness, one-time-use nonce, and an authoritative execution lease now gate the stage
  worker's protected side effects (`worker/execution_authority.py`,
  `worker/stage_runner.py`).
- `l9-analysis.yml` now selects the governed profile by event so post-merge analysis is
  reachable on `push` (audit F-06).
- `MANIFEST.md` is back in sync so the release-readiness ladder runs to completion (audit
  F-07). This makes the negative test above straightforward to construct and to clear.
