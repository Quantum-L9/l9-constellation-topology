# Agent Operating Contract

1. Treat `SPECIFICATION.md`, JSON Schemas, and `.l9/*.yaml` as repository authority.
2. Never introduce `PacketEnvelope`; `TransportPacket` is canonical.
3. Do not write to Neo4j, Graphiti, or source repositories.
4. Do not use reports as compiler inputs.
5. Do not add filesystem mutation outside `src/l9_constellation_topology/io/`.
6. Preserve evidence lineage, conflicts, and unknowns.
7. Validation returns immutable receipt data; it does not rewrite the subject under validation.
8. Add or update tests for every behavioral change.
9. Do not claim execution or deployment success without captured evidence.
10. Prefer compatibility adapters over contaminating the canonical domain model with legacy fields.
11. Treat `BUILD_SPECIFICATION.md` and accepted ADRs as binding architecture authority.
12. Create a new ADR before changing packet boundaries, authority, identity, effects, or orchestration.
13. Keep root governance, manifest, final tree, and validation evidence synchronized.
14. Inspect `AGENTS.md`, `README.md`, `DEVELOPMENT.md`, `RUNBOOK.md`, and `VALIDATION.md` for every command, validation, generated-artifact, developer-workflow, or operator-workflow change. Update all five when the change affects their contract or instructions.
15. Generated schemas and checked-in packet fixtures are derived artifacts. Run `make generated-check` before declaring validation complete.
16. When canonical models, schema generation, sample repositories, packet construction, or fixture generation changes, run the applicable explicit update target: `make schemas-update`, `make fixtures-update`, or `make generated-update`. Review the generated diff before committing.
17. Never make validation mutate generated artifacts. Check targets are read-only and fail closed; update targets are explicit mutation commands.
18. After changing tracked files, regenerate or update `MANIFEST.md`, `FINAL_TREE.md`, `GIT_TREE_MANIFEST.json`, traceability records, and validation evidence as required by repository governance. Commit-bound integrity must be generated from the final staged tree.
