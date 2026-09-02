# Bridge-Gap Projection

The bridge-gap projection answers one bounded question:

> Which capabilities or outputs have an observed earlier lifecycle state but no
> observed edge proving the next state?

It consumes an already validated, materialized Topology Packet. It does not scan
repositories or live platforms, and it does not activate, dispatch, mutate, or decide
architecture.

## Outputs

Default report rendering now includes:

- `bridge-gaps.json`: machine-readable `l9.bridge-gap-projection/v1`;
- `BRIDGE_GAPS.md`: operator-facing decision report.

Both are indexed by the existing `report-manifest.json` and committed only through an
`OutputSink`.

## Version 1 gap classes

| Type | Proven condition | Missing transition |
|---|---|---|
| `BUILT_UNREACHABLE` | Capability has an observed implementer but no exposure or route | `IMPLEMENTED_TO_EXPOSED` or `VALIDATED_TO_EXPOSED` |
| `EXPOSED_UNCONSUMED` | Capability has an exposure or route but no consumer | `EXPOSED_TO_CONSUMED` |
| `ORPHAN_OUTPUT` | Non-capability subject has a producer but no consumer | `PRODUCED_TO_CONSUMED` |

A direct consumer closes earlier capability gaps. The projection does not demand a
redundant `EXPOSES` edge when `CONSUMES` already proves reachability.

## Activation intent

Every finding carries an independent intent:

- `REQUIRED` → `ACTION_REQUIRED`
- `OPTIONAL` or `DEFERRED` → `INTENTIONAL_DORMANCY`
- `PROHIBITED` → `CORRECTLY_DISCONNECTED`
- `UNKNOWN` → `DECISION_REQUIRED`

Intent can be supplied by a capability graph node property named
`activation_intent` or by an explicit caller overlay. Invalid values do not default to
required. They remain unknown.

## Evidence and identity

Each finding preserves the evidence references carried by the capability or relation
records that establish the observed state. Finding identity binds:

- bridge-gap policy ID and version;
- subject identity;
- gap type.

Projection identity also binds the source packet ID, source semantic hash, policy
hash, findings, counts, and unknown-intent count. Wall-clock time is excluded.

## What version 1 does not claim

The projector cannot prove live GitHub ruleset state, deployed service state, runtime
calls, scheduled execution, provider registration, or production authority unless an
upstream evidence producer first records those facts in canonical topology.

Future live-state adapters should enrich Repository Model Packets or another accepted
packet boundary. They should not add network access to this pure projection.
