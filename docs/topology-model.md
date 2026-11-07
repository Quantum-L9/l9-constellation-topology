# Topology Model

Canonical records include repositories, artifacts, capabilities, edges, flows, graph records, impact indexes, risks, maturity assessments, evidence, conflicts, and unknowns.

Stable entity IDs use semantic identity, not machine-local paths. Supported edge types include `CONTAINS`, `DEPENDS_ON`, `IMPLEMENTS`, `EXPOSES`, `VALIDATED_BY`, `GOVERNED_BY`, `OWNED_BY`, `DOCUMENTED_BY`, `PRODUCES`, `CONSUMES`, `DERIVED_FROM`, `SUPERSEDES`, `ROUTES_TO`, `PUBLISHES_TO`, and `MEMBER_OF`.

An artifact's `artifact_type` is a node property, not a relation (ADR-0037): the graph builder emits `CONTAINS` for every artifact and `IMPLEMENTS` for the capabilities its record lists, but never promotes a classification such as `documentation` or `ci-workflow` into `DOCUMENTED_BY` or `VALIDATED_BY`. Those relations are canonical only when a producer declares or a claim projects them.
