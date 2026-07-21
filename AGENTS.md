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
