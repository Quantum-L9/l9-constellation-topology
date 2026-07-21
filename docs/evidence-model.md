# Evidence Model

Evidence is a first-class record with a stable ID, subject, optional field, production stage, evidence class, source type, source reference, value, decomposed confidence, producer, and producer version.

Authority order:

1. Human-declared source
2. Validated Repository Model Packet evidence
3. Deterministic direct observation
4. Cross-record deterministic derivation
5. Heuristic derivation
6. Model-assisted inference
7. Prior generated topology

Conflicts are preserved as records. Unknowns are explicit records. Neither is resolved through last-write-wins behavior.
