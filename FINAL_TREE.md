# Final Tree

```text
l9-constellation-topology/
├── .github
│   ├── governance
│   │   ├── execution-profiles.yaml
│   │   ├── promotion-policy.yaml
│   │   ├── provider-requiredness.yaml
│   │   ├── quality-thresholds.yaml
│   │   ├── rule-modes.yaml
│   │   ├── semgrep-identity-map.yaml
│   │   ├── semgrep-policy.yaml
│   │   └── waivers.yaml
│   ├── ISSUE_TEMPLATE
│   │   ├── 1-bug.yml
│   │   ├── 2-feature.yml
│   │   ├── 3-task.yml
│   │   ├── 4-incident.yml
│   │   ├── architecture_change.yml
│   │   ├── bug_report.yml
│   │   ├── ci-failure.yml
│   │   ├── config.yml
│   │   └── gov-violation.yml
│   ├── PULL_REQUEST_TEMPLATE
│   │   └── release.md
│   ├── workflows
│   │   ├── compile.yml
│   │   ├── l9-ingress.yml
│   │   ├── l9-manual-replay.yml
│   │   ├── l9-pr-validate.yml
│   │   └── l9-stage-worker.yml
│   ├── CODEOWNERS
│   ├── dependabot.yml
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── pull_request_template.md
├── .l9
│   ├── callback-policy.yaml
│   ├── maturity-profile.yaml
│   ├── meta-authority.yaml
│   ├── metadata-index.jsonl
│   ├── output-policy.yaml
│   ├── packet-profile.yaml
│   ├── pipeline.yaml
│   ├── publication-policy.yaml
│   ├── repo-workflow.json
│   ├── report-profile.yaml
│   ├── risk-profile.yaml
│   └── topology-profile.yaml
├── config
│   ├── repo_sources.yaml
│   ├── report_profiles.yaml
│   ├── scanner_rules.yaml
│   └── topology_roles.yaml
├── contracts
│   ├── commit-receipt.schema.json
│   ├── execution-failure.schema.json
│   ├── github-ingress.schema.json
│   ├── packet-bundle-manifest.schema.json
│   ├── render-request.schema.json
│   ├── render-result.schema.json
│   ├── replay-request.schema.json
│   ├── report-manifest.schema.json
│   ├── repository-model-packet.schema.json
│   ├── stage-dispatch.schema.json
│   ├── stage-result.schema.json
│   ├── topology-packet.schema.json
│   ├── transport-packet.schema.json
│   ├── validation-receipt.schema.json
│   └── validation-request.schema.json
├── docs
│   ├── adr
│   │   ├── 0001-packet-native-middle-end-compiler-boundary.md
│   │   ├── 0002-transportpacket-is-the-only-control-plane-envelope.md
│   │   ├── 0003-repository-model-packets-are-canonical-inputs.md
│   │   ├── 0004-topology-packet-is-the-canonical-output.md
│   │   ├── 0005-validation-receipts-remain-separate-and-immutable.md
│   │   ├── 0006-use-a-run-scoped-signal-plane.md
│   │   ├── 0007-outputsink-is-the-only-write-boundary.md
│   │   ├── 0008-separate-semantic-hashes-from-artifact-hashes.md
│   │   ├── 0009-preserve-evidence-authority-conflicts-and-unknowns.md
│   │   ├── 0010-use-decomposed-confidence-assessment.md
│   │   ├── 0011-permit-only-bounded-read-only-fallback-observation.md
│   │   ├── 0012-use-stable-repository-and-entity-identity.md
│   │   ├── 0013-keep-graph-construction-pure-and-edge-taxonomy-versioned.md
│   │   ├── 0014-drive-maturity-and-risk-from-versioned-profiles.md
│   │   ├── 0015-treat-reports-as-lazy-projections.md
│   │   ├── 0016-use-postgres-model-b-orchestration-with-github-actions-workers.md
│   │   ├── 0017-require-signed-exact-revision-worker-execution.md
│   │   ├── 0018-use-immutable-oci-packet-storage-and-an-external-registry.md
│   │   ├── 0019-use-idempotency-reuse-replay-and-reconciliation.md
│   │   ├── 0020-delegate-publication-planning-to-the-ingestion-bridge.md
│   │   ├── 0021-internalize-publication-planning-and-memory-lowering.md
│   │   ├── 0022-key-memory-effects-by-fact-not-snapshot.md
│   │   ├── 0023-declare-field-cardinality-before-detecting-conflicts.md
│   │   ├── 0024-compile-repository-model-assertions-into-semantic-claims.md
│   │   ├── 0025-separate-fact-identity-from-durable-write-identity.md
│   │   ├── 0026-accept-corpus-intelligence-as-an-auxiliary-packet.md
│   │   ├── 0027-separate-observation-time-from-publication-time.md
│   │   ├── 0028-project-bridge-gaps-as-decision-support.md
│   │   ├── 0029-authorize-a-bounded-github-native-direct-compile-seam.md
│   │   ├── 0030-accept-corpus-intelligence-v1-1-domains-not-run.md
│   │   ├── 0031-bind-repository-metadata-to-l9-meta-injector.md
│   │   ├── 0032-adopt-core-repository-execution-v2.md
│   │   ├── 0033-register-governed-header-predicates-as-declaration-only.md
│   │   ├── 0034-semantic-claim-read-model-and-managed-header-vocabulary.md
│   │   ├── 0035-conflict-aware-projection-and-resolution-aware-impact.md
│   │   ├── 0036-evidence-qualified-relation-publication.md
│   │   ├── 0037-stop-promoting-artifact-classification-to-relations.md
│   │   └── README.md
│   ├── archive
│   │   └── v4
│   │       ├── 01_SPEC_ATTACK.md
│   │       ├── 02_IMPLEMENTATION_CONTRACT.md
│   │       ├── 03_DEPENDENCY_DAG.md
│   │       ├── 07_VALIDATION_REPORT.md
│   │       ├── 08_EXECUTION_CHECKLIST_REPORT.md
│   │       ├── architecture.md
│   │       ├── machine-summary.json
│   │       ├── MANIFEST.md
│   │       └── README.md
│   ├── design
│   │   └── l9-constellation-topology-spec.md
│   ├── runbooks
│   │   └── merge-gate-enforcement.md
│   ├── acceptance-matrix.md
│   ├── architecture.md
│   ├── bridge-gap-projection.md
│   ├── candidate-topology.md
│   ├── corpus-intelligence-boundary.md
│   ├── deployment.md
│   ├── evidence-model.md
│   ├── migration-v4-to-v5.md
│   ├── output-sink.md
│   ├── packet-contracts.md
│   ├── publication-boundary.md
│   ├── recovery.md
│   ├── report-lifecycle.md
│   ├── topology-model.md
│   └── worker-contract.md
├── evidence
│   └── live-qualify-2026-08-02
│       ├── odoo-e2e-recipes
│       │   ├── odoo-etc-e2e
│       │   │   └── odoo.conf
│       │   ├── constraints.odoo-e2e.txt
│       │   ├── docker-compose.odoo-e2e.override.yml
│       │   └── Dockerfile.odoo-e2e
│       ├── A0-GATE-LIVE-QUALIFY-NONDESTRUCTIVE-20260802.json
│       ├── CAMPAIGN-GATE-LIVE-QUALIFY-NONDESTRUCTIVE.json
│       ├── DEFER-GATE-004.json
│       ├── DEFER-GATE-008.json
│       ├── DEFER-GATE-011.json
│       ├── DEFER-GATE-012.json
│       ├── DEFER-GATE-013.json
│       ├── DEFER-GATE-015.json
│       ├── DEFER-GATE-018.json
│       ├── DEFER-GATE-019.json
│       ├── DEFER-GATE-020.json
│       ├── DEFER-GATE-021.json
│       ├── DEFER-GATE-022.json
│       ├── DEFER-GATE-023.json
│       ├── DEFER-GATE-025.json
│       ├── DEFER-GATE-026.json
│       ├── DEFER-GATE-027.json
│       ├── DEFER-GATE-028.json
│       ├── DEFER-GATE-029.json
│       ├── DEFER-GATE-032.json
│       ├── DEFER-GATE-034.json
│       ├── DEFER-GATE-035.json
│       ├── DEFER-GATE-036.json
│       ├── DEFER-GATE-037.json
│       ├── DEFER-GATE-038.json
│       ├── DEFER-GATE-042.json
│       ├── DEFER-GATE-045.json
│       ├── DEFER-GATE-046.json
│       ├── DEFER-GATE-060.json
│       ├── DEFER-GATE-061.json
│       ├── DEFER-GATE-062.json
│       ├── E2E-STACK-STATUS.json
│       ├── GATE-059-REPOSITORY-TEST-EVIDENCE.json
│       ├── GATE-066-REPOSITORY-TEST-EVIDENCE.json
│       ├── GATE-QUALIFY-SUMMARY.json
│       ├── LIVE-INTEGRATION-EVIDENCE.json
│       ├── OPERATOR-APPROVE-SLIP.json
│       ├── PROGRAM-COMPLETION-REPORT.json
│       ├── PROGRAM-E2E-PROOF.json
│       ├── README.md
│       ├── run_gate_qualify.py
│       └── STACK-HEALTH-SNAPSHOT.json
├── outputs
│   └── .gitkeep
├── schemas
│   ├── artifact-record.schema.json
│   ├── bridge-gap-projection.schema.json
│   ├── capability-record.schema.json
│   ├── diagnostic-record.schema.json
│   ├── edge-record.schema.json
│   ├── edge_card.schema.json
│   ├── evidence-record.schema.json
│   ├── flow-record.schema.json
│   ├── flow_card.schema.json
│   ├── graph-record.schema.json
│   ├── maturity-assessment.schema.json
│   ├── repo_card.schema.json
│   ├── repository-record.schema.json
│   ├── risk-record.schema.json
│   ├── risk_register.schema.json
│   ├── semantic-claim-record.schema.json
│   ├── topology-publication-plan.schema.json
│   └── topology_report.schema.json
├── scripts
│   ├── architecture_boundary_check.py
│   ├── build_control_packet.py
│   ├── capture_downstream_contract.py
│   ├── compile_topology_packet.py
│   ├── evaluate_hash_locality.py
│   ├── generate_fixture_packets.py
│   ├── generate_schemas.py
│   ├── generated_artifact_sync.py
│   ├── git_tree_manifest.py
│   ├── qualify_repository_model_assertions.py
│   ├── render_topology_reports.py
│   ├── validate_contracts.py
│   ├── validate_git_integrity.py
│   ├── validate_nuclear_execution.py
│   ├── validate_release_readiness.py
│   ├── validate_workflows.py
│   └── verify_determinism.py
├── src
│   └── l9_constellation_topology
│       ├── compatibility
│       │   ├── __init__.py
│       │   ├── repo_card_adapter.py
│       │   └── v4_models.py
│       ├── domain
│       │   ├── __init__.py
│       │   ├── artifact.py
│       │   ├── assessment.py
│       │   ├── base.py
│       │   ├── bridge_gap.py
│       │   ├── candidate.py
│       │   ├── capability.py
│       │   ├── claim.py
│       │   ├── confidence.py
│       │   ├── corpus.py
│       │   ├── diagnostic.py
│       │   ├── edge.py
│       │   ├── flow.py
│       │   ├── readiness.py
│       │   ├── reasoning.py
│       │   ├── repository.py
│       │   └── topology.py
│       ├── io
│       │   ├── __init__.py
│       │   ├── composite_output_sink.py
│       │   ├── failure_report.py
│       │   ├── filesystem_output_sink.py
│       │   ├── memory_output_sink.py
│       │   ├── output_sink.py
│       │   ├── packet_bundle_output_sink.py
│       │   ├── rendered_artifact.py
│       │   ├── write_intent.py
│       │   ├── write_plan.py
│       │   └── write_policy.py
│       ├── packets
│       │   ├── adapters
│       │   │   ├── __init__.py
│       │   │   ├── errors.py
│       │   │   ├── meta_generation.py
│       │   │   ├── meta_work_signals.py
│       │   │   └── repository_model_v1.py
│       │   ├── __init__.py
│       │   ├── assertion_evidence.py
│       │   ├── bundle.py
│       │   ├── bundle_verification.py
│       │   ├── common.py
│       │   ├── control.py
│       │   ├── corpus_bundle.py
│       │   ├── corpus_evidence.py
│       │   ├── corpus_ingress.py
│       │   ├── corpus_intelligence.py
│       │   ├── corpus_validator.py
│       │   ├── document_signal_evidence.py
│       │   ├── loader.py
│       │   ├── payloads.py
│       │   ├── refs.py
│       │   ├── report_manifest.py
│       │   ├── repository_bundle.py
│       │   ├── repository_model.py
│       │   ├── stage_result.py
│       │   ├── topology_packet.py
│       │   ├── transport.py
│       │   ├── validation_receipt.py
│       │   └── validator.py
│       ├── publication
│       │   ├── __init__.py
│       │   ├── bundle.py
│       │   ├── contracts.py
│       │   ├── eligibility.py
│       │   ├── identity.py
│       │   ├── lowering.py
│       │   ├── plan.py
│       │   ├── policy.py
│       │   └── qualification.py
│       ├── reconciliation
│       │   ├── __init__.py
│       │   ├── cardinality.py
│       │   ├── inputs.py
│       │   └── predicates.py
│       ├── renderers
│       │   ├── __init__.py
│       │   ├── bridge_gap_report.py
│       │   ├── common.py
│       │   ├── csv_export.py
│       │   ├── json_export.py
│       │   ├── markdown_report.py
│       │   ├── mermaid_export.py
│       │   ├── report_renderer.py
│       │   └── risk_report.py
│       ├── run
│       │   ├── __init__.py
│       │   ├── context.py
│       │   ├── diagnostics.py
│       │   ├── evidence.py
│       │   └── receipts.py
│       ├── scanners
│       │   ├── __init__.py
│       │   ├── adr_scanner.py
│       │   ├── ci_scanner.py
│       │   ├── dependency_scanner.py
│       │   ├── governance_scanner.py
│       │   ├── graphiti_scanner.py
│       │   ├── manifest_scanner.py
│       │   ├── repo_scanner.py
│       │   └── repository_model_scanner.py
│       ├── sources
│       │   ├── __init__.py
│       │   ├── filesystem_reader.py
│       │   ├── reader.py
│       │   ├── repository_registry.py
│       │   └── source_snapshot.py
│       ├── stages
│       │   ├── __init__.py
│       │   ├── aggregate_capabilities.py
│       │   ├── aggregate_repositories.py
│       │   ├── assess_impact.py
│       │   ├── assess_maturity.py
│       │   ├── assess_risk.py
│       │   ├── build_graph.py
│       │   ├── classify_roles.py
│       │   ├── derive_unknowns.py
│       │   ├── ingest_packets.py
│       │   ├── normalize_models.py
│       │   ├── observe_fallbacks.py
│       │   ├── reconcile_assertions.py
│       │   ├── reconcile_evidence.py
│       │   ├── resolve_config.py
│       │   └── validate_topology.py
│       ├── topology
│       │   ├── __init__.py
│       │   ├── bridge_gaps.py
│       │   ├── candidates.py
│       │   ├── capability_builder.py
│       │   ├── claim_projection.py
│       │   ├── claim_view.py
│       │   ├── classifier.py
│       │   ├── corpus_model.py
│       │   ├── duplicates.py
│       │   ├── flow_builder.py
│       │   ├── graph_builder.py
│       │   ├── impact.py
│       │   ├── maturity.py
│       │   ├── readiness.py
│       │   ├── reasoning_router.py
│       │   ├── risk.py
│       │   └── work_projection.py
│       ├── validation
│       │   ├── __init__.py
│       │   ├── invariant_validator.py
│       │   ├── schema_validator.py
│       │   ├── topology_validator.py
│       │   └── validation_report.py
│       ├── worker
│       │   ├── __init__.py
│       │   ├── callback.py
│       │   ├── control_packet.py
│       │   ├── errors.py
│       │   ├── execution_authority.py
│       │   ├── failure.py
│       │   ├── packet_store.py
│       │   ├── registry.py
│       │   ├── signature.py
│       │   ├── stage_runner.py
│       │   └── transport_factory.py
│       ├── __init__.py
│       ├── cardinality.py
│       ├── cli.py
│       ├── compiler.py
│       ├── config.py
│       ├── evidence.py
│       ├── models.py
│       └── py.typed
├── tests
│   ├── fixtures
│   │   ├── corpus_intelligence
│   │   │   └── producer-emitted
│   │   │       ├── corpus-intelligence
│   │   │       │   ├── payload
│   │   │       │   │   ├── consolidation-candidates.json
│   │   │       │   │   ├── document-work-signals.json
│   │   │       │   │   ├── exact-duplicate-relations.json
│   │   │       │   │   ├── project-candidates.json
│   │   │       │   │   ├── readiness-evidence.json
│   │   │       │   │   ├── reasoning-candidates.json
│   │   │       │   │   ├── reasoning-evidence-pack-refs.json
│   │   │       │   │   ├── semantic-pair-relations.json
│   │   │       │   │   └── topic-candidates.json
│   │   │       │   ├── manifest.json
│   │   │       │   └── packet.json
│   │   │       ├── roots
│   │   │       │   ├── ArchiveZips
│   │   │       │   │   ├── receipts
│   │   │       │   │   │   └── validation-receipt.json
│   │   │       │   │   ├── manifest.json
│   │   │       │   │   └── packet.json
│   │   │       │   ├── Backup
│   │   │       │   │   ├── receipts
│   │   │       │   │   │   └── validation-receipt.json
│   │   │       │   │   ├── manifest.json
│   │   │       │   │   └── packet.json
│   │   │       │   ├── corpus
│   │   │       │   │   ├── receipts
│   │   │       │   │   │   └── validation-receipt.json
│   │   │       │   │   ├── manifest.json
│   │   │       │   │   └── packet.json
│   │   │       │   ├── Documents
│   │   │       │   │   ├── receipts
│   │   │       │   │   │   └── validation-receipt.json
│   │   │       │   │   ├── manifest.json
│   │   │       │   │   └── packet.json
│   │   │       │   └── OldSSD
│   │   │       │       ├── receipts
│   │   │       │       │   └── validation-receipt.json
│   │   │       │       ├── manifest.json
│   │   │       │       └── packet.json
│   │   │       └── PROVENANCE.md
│   │   ├── downstream_contracts
│   │   │   └── l9-graphiti-memory-contract.json
│   │   ├── legacy_v4_outputs
│   │   │   ├── 07_VALIDATION_REPORT.md
│   │   │   ├── architecture_diagrams.mmd
│   │   │   ├── dependency_graph.json
│   │   │   ├── edge_cards.yaml
│   │   │   ├── evidence_hashes.json
│   │   │   ├── flow_cards.yaml
│   │   │   ├── graph_records.jsonl
│   │   │   ├── maturity_scorecard.csv
│   │   │   ├── neo4j_import.jsonl
│   │   │   ├── repo_inventory.yaml
│   │   │   ├── report.md
│   │   │   ├── risk_register.md
│   │   │   ├── topology_report.json
│   │   │   └── topology_report.md
│   │   ├── publication_identity
│   │   │   └── golden-vectors.json
│   │   ├── publication_policies
│   │   │   └── legacy-v1
│   │   │       └── .l9
│   │   │           └── publication-policy.yaml
│   │   ├── repository_model_packets
│   │   │   ├── l9-assertion-sample
│   │   │   │   ├── receipts
│   │   │   │   │   └── validation-receipt.json
│   │   │   │   ├── manifest.json
│   │   │   │   └── packet.json
│   │   │   ├── l9-gate-sdk
│   │   │   │   ├── receipts
│   │   │   │   │   └── validation-receipt.json
│   │   │   │   ├── manifest.json
│   │   │   │   ├── packet.json
│   │   │   │   └── PROVENANCE.md
│   │   │   └── l9-mcp-server
│   │   │       ├── receipts
│   │   │       │   └── validation-receipt.json
│   │   │       ├── manifest.json
│   │   │       ├── packet.json
│   │   │       └── PROVENANCE.md
│   │   ├── sample_constellation
│   │   │   ├── l9-gate-sdk
│   │   │   │   ├── .github
│   │   │   │   │   ├── workflows
│   │   │   │   │   │   └── ci.yml
│   │   │   │   │   └── CODEOWNERS
│   │   │   │   ├── docs
│   │   │   │   │   └── adr
│   │   │   │   │       └── adr-001-transport-protocol.md
│   │   │   │   ├── src
│   │   │   │   │   └── l9_gate_sdk
│   │   │   │   │       └── __init__.py
│   │   │   │   ├── pyproject.toml
│   │   │   │   └── README.md
│   │   │   └── l9-mcp-server
│   │   │       ├── .github
│   │   │       │   └── workflows
│   │   │       │       └── deploy.yml
│   │   │       ├── src
│   │   │       │   └── l9_mcp_server
│   │   │       │       └── __init__.py
│   │   │       ├── pyproject.toml
│   │   │       └── README.md
│   │   ├── semantic_assertion_repository
│   │   │   ├── client
│   │   │   │   └── js
│   │   │   │       └── package.json
│   │   │   ├── contracts
│   │   │   │   ├── conformance_checklist.md
│   │   │   │   └── packet_envelope_v1.yaml
│   │   │   ├── engine
│   │   │   │   └── main.py
│   │   │   ├── AGENTS.md
│   │   │   ├── pyproject.toml
│   │   │   ├── README.md
│   │   │   └── spec.yaml
│   │   └── topology_packets
│   │       └── foundational-two-repo
│   │           ├── payload
│   │           │   ├── artifact-records.json
│   │           │   ├── candidate-clusters.json
│   │           │   ├── candidate-relations.json
│   │           │   ├── capability-records.json
│   │           │   ├── conflicts.json
│   │           │   ├── corpus-records.json
│   │           │   ├── diagnostics.json
│   │           │   ├── edge-records.json
│   │           │   ├── evidence.json
│   │           │   ├── flow-records.json
│   │           │   ├── graph-records.json
│   │           │   ├── impact-indexes.json
│   │           │   ├── maturity.json
│   │           │   ├── readiness-evidence.json
│   │           │   ├── repository-records.json
│   │           │   ├── risks.json
│   │           │   ├── root-records.json
│   │           │   ├── semantic-claims.json
│   │           │   ├── topology-reasoning-candidates.json
│   │           │   └── unknowns.json
│   │           ├── receipts
│   │           │   └── validation-receipt.json
│   │           ├── manifest.json
│   │           └── packet.json
│   ├── __init__.py
│   ├── corpus_fixtures.py
│   ├── test_architecture_boundary_v5.py
│   ├── test_assertion_reconciliation.py
│   ├── test_assessments_v5.py
│   ├── test_bridge_gap_projection.py
│   ├── test_bridge_gap_renderer.py
│   ├── test_claim_view.py
│   ├── test_cli_v5.py
│   ├── test_confirmed_findings_remediation.py
│   ├── test_conflict_cardinality.py
│   ├── test_corpus_hash_locality.py
│   ├── test_corpus_ingress.py
│   ├── test_corpus_intelligence_contract.py
│   ├── test_corpus_publication_containment.py
│   ├── test_corpus_topology_compilation.py
│   ├── test_dependency_scanner.py
│   ├── test_direct_observation_adapter_v5.py
│   ├── test_effect_identity_migration_preflight.py
│   ├── test_evidence_v5.py
│   ├── test_execution_authority_v5.py
│   ├── test_field_cardinality.py
│   ├── test_fixture_provenance.py
│   ├── test_generated_artifact_sync.py
│   ├── test_git_integrity.py
│   ├── test_graph_builder.py
│   ├── test_hash_locality.py
│   ├── test_header_predicates.py
│   ├── test_impact.py
│   ├── test_maturity.py
│   ├── test_meta_generation_adapter.py
│   ├── test_meta_work_signal_payload.py
│   ├── test_oci_acceptance_drill_v5.py
│   ├── test_output_sink_v5.py
│   ├── test_packet_ingress_v5.py
│   ├── test_packet_models_v5.py
│   ├── test_packet_store_v5.py
│   ├── test_producer_emitted_corpus_packet.py
│   ├── test_publication_downstream_conformance.py
│   ├── test_publication_edge_coverage.py
│   ├── test_publication_edge_fidelity.py
│   ├── test_publication_effect_identity.py
│   ├── test_publication_identity_golden_vectors.py
│   ├── test_publication_plan_identity.py
│   ├── test_publication_planning.py
│   ├── test_publication_qualification.py
│   ├── test_publication_temporal.py
│   ├── test_qualified_projection.py
│   ├── test_reasoning_router.py
│   ├── test_release_readiness.py
│   ├── test_renderers.py
│   ├── test_repo_scanner.py
│   ├── test_report_projection_v5.py
│   ├── test_repository_aggregation_v5.py
│   ├── test_repository_execution.py
│   ├── test_repository_governance.py
│   ├── test_repository_model_assertions.py
│   ├── test_repository_model_readiness.py
│   ├── test_runtime_boundaries_v5.py
│   ├── test_scan_compatibility_path.py
│   ├── test_semantic_claim_activation.py
│   ├── test_structured_locators.py
│   ├── test_topology_compiler_v5.py
│   ├── test_topology_graph_v5.py
│   ├── test_transport_signature_v5.py
│   ├── test_unknown_derivation.py
│   ├── test_validation.py
│   ├── test_worker_v5.py
│   └── test_workflow_contracts_v5.py
├── validation
│   ├── validation_checks.jsonl
│   ├── validation_findings.jsonl
│   └── validation_report.yaml
├── .editorconfig
├── .env.example
├── .gitattributes
├── .gitignore
├── .python-version
├── ADR_INDEX.md
├── AGENTS.md
├── ALIGNMENT_AUDIT.md
├── ARCHITECTURE.md
├── BUILD_SPECIFICATION.md
├── CHANGE_SUMMARY.md
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── CONVERGENCE_REPORT.yaml
├── CURRENT_VALIDATION_REPORT.md
├── DEPENDENCY_POLICY.md
├── DEVELOPMENT.md
├── EFFECT_IDENTITY_MIGRATION_PREFLIGHT.json
├── FINAL_TREE.md
├── FIX_MAP.md
├── GIT_TREE_MANIFEST.json
├── GOVERNANCE.md
├── HASH_LOCALITY_EVALUATION.json
├── INITIAL_COMMIT.md
├── LICENSE
├── MAINTAINERS.md
├── Makefile
├── MANIFEST.md
├── NOTICE.md
├── pyproject.toml
├── QUALIFICATION.json
├── README.md
├── REGRESSION_GUARD.md
├── RELEASING.md
├── Repo.mk
├── ROADMAP.md
├── RUNBOOK.md
├── SECURITY.md
├── SPECIFICATION.md
├── STUB_TODO_THIN_FILE_AUDIT.md
├── SUPPORT.md
├── THREAT_MODEL.md
├── TRACEABILITY_MAP.yaml
├── UNKNOWN_REGISTER.md
├── uv.lock
└── VALIDATION.md
```
