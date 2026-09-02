# ADR-0028: Project bridge gaps as non-authoritative decision support

**Status:** Accepted

## Context

The canonical topology already records capabilities and versioned relations such as
`IMPLEMENTS`, `EXPOSES`, `VALIDATED_BY`, `PRODUCES`, `CONSUMES`, and `ROUTES_TO`.
Those records can prove that part of a capability lifecycle exists while a later
transition is absent from the compiled topology.

Absence alone is not an instruction to activate anything. A disconnected capability
may be optional, deliberately deferred, prohibited, obsolete, or simply missing an
operator decision. Treating every missing edge as a defect would convert a topology
compiler into an unauthorized architecture planner. Ignoring the pattern entirely
would hide investments that are implemented and validated but never reach a live
consumer.

## Decision

Add a deterministic `l9.bridge-gap-projection/v1` decision-support projection over a
validated materialized Topology Packet.

Version 1 reports only gaps that current canonical topology can prove without live
control-plane access:

1. `BUILT_UNREACHABLE`: an implemented capability has no `EXPOSES` or `ROUTES_TO`
   path;
2. `EXPOSED_UNCONSUMED`: an exposed or routed capability has no `CONSUMES` edge;
3. `ORPHAN_OUTPUT`: a produced non-capability output has no `CONSUMES` edge.

A real `CONSUMES` edge closes earlier reachability gaps because consumption is
stronger evidence than an omitted intermediate exposure relation. Gap rules use
precedence so one subject does not receive a stack of derivative symptoms.

Observed topology state and activation intent remain separate. Intent is one of
`REQUIRED`, `OPTIONAL`, `DEFERRED`, `PROHIBITED`, or `UNKNOWN`; absent or invalid
intent remains `UNKNOWN`. The projection maps intent to a disposition but never
changes topology, activates a capability, dispatches an effect, or mutates a source
repository.

The projection is emitted lazily as `bridge-gaps.json` and `BRIDGE_GAPS.md` through
the existing renderer and `OutputSink` boundary. It is a derived report beside the
Topology Packet, not a new packet payload, canonical contract, runtime authority, or
publication effect. Its generated schema therefore lives under `schemas/`, not
`contracts/`.

## Consequences

- The organization can query which already-observed capabilities or outputs have not
  crossed their next lifecycle boundary.
- Optional and prohibited capabilities remain visible without being mislabeled as
  automatic activation work.
- Unknown intent becomes an explicit decision requirement instead of an invented
  recommendation.
- Projection identity is deterministic and bound to source packet identity and a
  versioned bridge-gap policy hash.
- Live rulesets, deployments, service registrations, feature flags, and runtime calls
  remain outside version 1 unless an upstream producer supplies evidence into the
  canonical topology.
- Future gap classes must be added through a new policy version and evidence-backed
  topology semantics, not heuristic repository scraping inside the projector.

## Alternatives considered

### Add bridge gaps to the canonical Topology Packet payload

Rejected. A gap is a policy-driven interpretation of canonical topology, not source
truth. Binding it into the packet would contaminate packet identity with a report
policy and create recursive derived truth.

### Activate every disconnected capability automatically

Rejected. Disconnection may be intentional or safety-critical. The compiler has no
execution authority and does not own operator intent.

### Build a new organization scanner or bridge-gap service

Rejected. Repository observation, topology compilation, graph relations, report
projection, and output controls already exist. A second scanner or control plane
would duplicate authority.

### Infer live state from README or configuration claims

Rejected. Repository declarations do not prove live control-plane or runtime state.
Such evidence must enter through an explicit upstream adapter before it can support a
stronger gap class.

## Compliance and validation

- Unit tests cover all three gap classes, lifecycle precedence, direct-consumer
  closure, activation-intent dispositions, deterministic identity, and JSON
  serialization.
- Renderer tests prove JSON and Markdown artifacts are lazy, manifest-indexed
  projections.
- Generated-schema checks bind `l9.bridge-gap-projection/v1` to its Pydantic model.
- Architecture-boundary validation confirms the feature introduces no scanner,
  network client, direct write, dispatch, or packet-payload dependency.
- Full repository validation remains the merge authority.

## Related artifacts

- `src/l9_constellation_topology/domain/bridge_gap.py`
- `src/l9_constellation_topology/topology/bridge_gaps.py`
- `src/l9_constellation_topology/renderers/bridge_gap_report.py`
- `schemas/bridge-gap-projection.schema.json`
- `docs/bridge-gap-projection.md`
- `tests/test_bridge_gap_projection.py`
- `tests/test_bridge_gap_renderer.py`
- `docs/adr/0013-keep-graph-construction-pure-and-edge-taxonomy-versioned.md`
- `docs/adr/0015-treat-reports-as-lazy-projections.md`
