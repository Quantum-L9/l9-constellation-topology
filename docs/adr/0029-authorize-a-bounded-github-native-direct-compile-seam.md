# ADR-0029: Authorize a bounded GitHub-native direct compile seam

- **Status:** Accepted
- **Date:** 2026-09-17
- **Decision owner:** Repository maintainers
- **Scope:** `l9-constellation-topology`

## Context

ADR-0016 makes an external Postgres control plane the durable orchestration
authority and GitHub Actions the exact-revision execution worker. That decision
answers durable scheduling, retries, leases, reconciliation, and global packet
registry state. It does not answer a second, narrower question: how a caller
that already knows exactly which source revision it wants compiled obtains a
validated Topology Packet without standing up the control plane first.

`.github/workflows/compile.yml` introduces that narrower path as a reusable
`workflow_call` interface. Storage authority (ADR-0018) was treated as
sufficient authorization for it. It is not. ADR-0018 governs how a packet is
stored and accepted once produced; it says nothing about who may ask for one to
be produced, or what relationship that request has to Model B. An orchestration
interface added without an orchestration decision leaves downstream consumers
unable to tell a sanctioned bounded compile interface from an alternate
orchestration authority.

## Decision

- Authorize `.github/workflows/compile.yml` as a **bounded, stateless compile
  seam**: a reusable workflow that observes one exact source revision, compiles
  it, validates the resulting Topology Packet, and optionally publishes that
  packet to GHCR under the ADR-0018 acceptance protocol.
- The seam is **caller-driven and single-shot**. It holds no durable state, owns
  no queue, and makes no scheduling decision. Its entire input is the caller's
  argument list; its entire output is the packet identity it returns.
- The seam **does not supersede ADR-0016**. External Postgres Model B remains
  the durable scheduler, the retry and lease owner, and the packet-registry
  authority. ADR-0016 continues to govern every production pipeline that needs
  dependency activation, reconciliation, replay, or registry bookkeeping.
- The seam **may not acquire orchestration responsibilities**. It must not
  schedule follow-on work, retry across runs, record or read lease state,
  maintain a packet registry, or activate a stage from packet existence. A
  change that gives it any of those requires a new ADR that explicitly
  supersedes this one.
- Publication through the seam is **optional and identity-bound**. When
  `publish` is true, the seam must satisfy the full ADR-0018 acceptance
  contract, not a happy-path subset: semantic-hash-derived staging, retention of
  only digest-qualified references, independent resolution of registry
  descriptor metadata, exact packet and manifest digest comparison, and
  fail-closed rejection of both valid-object substitution and mutable-tag
  resolution.
- Authority within the seam follows ADR-0017: the source revision is an exact
  40-character Git object ID, every action is pinned to a full commit SHA, and
  the run holds least privilege — package-write authority exists only inside the
  publication boundary that requires GHCR mutation.

## Consequences

### Positive

- A consumer can obtain a validated, digest-identified Topology Packet for an
  exact revision without provisioning the Model B control plane.
- The boundary between "compile this revision once" and "own the pipeline" is
  written down, so the seam cannot drift into a second orchestrator by
  accretion.
- Packet identity reaching a registry is governed by one contract (ADR-0018)
  regardless of which path produced it.

### Costs and constraints

- Two production paths now reach GHCR, so the ADR-0018 acceptance controls must
  be proven on both rather than inherited by one.
- Callers lose durability by choosing this path: a failed run is simply a failed
  run, with no lease, no retry, and no reconciliation.
- The seam's least-privilege split means compile-only and publishing execution
  are separate permission boundaries and must be validated separately.

## Alternatives considered

- **Rejected:** Treat ADR-0018 storage authority as sufficient authorization.
  Storage authority defines how an artifact is accepted, not who may orchestrate
  its production.
- **Rejected:** Supersede ADR-0016 and make GitHub Actions the orchestration
  authority. Actions remains ephemeral and weak at durable dependencies,
  retries, reconciliation, and registry state — the exact reasons ADR-0016 was
  accepted.
- **Rejected:** Require the Model B control plane for every compile. This makes
  a single exact-revision compilation depend on external infrastructure that the
  request does not otherwise need.
- **Rejected:** Leave the seam unauthorized and undocumented. Consumers would be
  unable to distinguish a sanctioned interface from orchestration drift.

## Compliance and validation

- `scripts/validate_workflows.py` enforces the seam's required controls: exact
  revision rejection, the compile and validation sequence, the ADR-0018
  acceptance controls, and the absence of package-write authority outside the
  publication boundary.
- The direct-compile smoke in `l9-pr-validate.yml` exercises the real producer,
  the real compiler, and the real GHCR publication and acceptance path.
- The acceptance drill must fail closed on valid-object substitution and on a
  mutable-tag reference; a green happy path alone does not discharge ADR-0018.
- ADR-0016 preservation is validated by inspection: the seam carries no
  scheduler, lease, retry, or registry state.

## Related artifacts

- `.github/workflows/compile.yml`
- `docs/adr/0016-use-postgres-model-b-orchestration-with-github-actions-workers.md`
- `docs/adr/0017-require-signed-exact-revision-worker-execution.md`
- `docs/adr/0018-use-immutable-oci-packet-storage-and-an-external-registry.md`
- `docs/deployment.md`
