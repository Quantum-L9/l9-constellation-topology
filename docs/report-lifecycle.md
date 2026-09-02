# Report Lifecycle

Reports are lazy projections of a validated Topology Packet.

## Projection identity

The cache key is derived from:

```text
topology semantic hash
+ renderer ID
+ renderer version
+ report profile hash
```

Execution timestamps do not alter the projection cache key or report-manifest semantic hash.

## Supported projections

- Markdown topology report
- Mermaid diagram
- Maturity CSV
- Repository inventory YAML
- Combined topology JSON
- Graph-record JSONL
- Neo4j candidate JSONL
- Risk register Markdown
- Bridge-gap JSON
- Bridge-gap Markdown

The bridge-gap projections identify only missing lifecycle transitions proven by the
supplied topology. They preserve activation intent separately and carry no activation,
dispatch, or mutation authority.

Each projection is represented by a `RenderedArtifact`, committed only through an `OutputSink`, and indexed by a `ReportManifest`.

## Authority

- Topology Packet: canonical machine artifact
- Validation Receipt: validation evidence
- Report Manifest: projection index
- Human reports and graph exports: derived, never canonical stage inputs
- Neo4j candidate: downstream planning input only, never a direct graph write
- Bridge-gap projection: decision support only, never an activation order
