# Final Tree

```text
l9-constellation-topology/
├── .github
│   ├── ISSUE_TEMPLATE
│   │   ├── architecture_change.yml
│   │   ├── bug_report.yml
│   │   └── config.yml
│   ├── workflows
│   │   ├── l9-ingress.yml
│   │   ├── l9-manual-replay.yml
│   │   ├── l9-pr-validate.yml
│   │   └── l9-stage-worker.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── .l9
│   ├── callback-policy.yaml
│   ├── maturity-profile.yaml
│   ├── output-policy.yaml
│   ├── packet-profile.yaml
│   ├── pipeline.yaml
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
│   ├── acceptance-matrix.md
│   ├── architecture.md
│   ├── deployment.md
│   ├── evidence-model.md
│   ├── migration-v4-to-v5.md
│   ├── output-sink.md
│   ├── packet-contracts.md
│   ├── recovery.md
│   ├── report-lifecycle.md
│   ├── topology-model.md
│   └── worker-contract.md
├── outputs
│   └── .gitkeep
├── schemas
│   ├── artifact-record.schema.json
│   ├── capability-record.schema.json
│   ├── diagnostic-record.schema.json
│   ├── edge-record.schema.json
│   ├── edge_card.schema.json
│   ├── evidence-record.schema.json
│   ├── flow-record.schema.json
│   ├── flow_card.schema.json
│   ├── graph-record.schema.json
│   ├── graph_record.schema.json
│   ├── maturity-assessment.schema.json
│   ├── repo_card.schema.json
│   ├── repository-record.schema.json
│   ├── risk-record.schema.json
│   ├── risk_register.schema.json
│   └── topology_report.schema.json
├── scripts
│   ├── architecture_boundary_check.py
│   ├── build_control_packet.py
│   ├── compile_topology_packet.py
│   ├── generate_fixture_packets.py
│   ├── generate_schemas.py
│   ├── generated_artifact_sync.py
│   ├── git_tree_manifest.py
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
│       │   ├── capability.py
│       │   ├── confidence.py
│       │   ├── diagnostic.py
│       │   ├── edge.py
│       │   ├── flow.py
│       │   ├── repository.py
│       │   └── topology.py
│       ├── io
│       │   ├── __init__.py
│       │   ├── composite_output_sink.py
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
│       │   │   └── repository_model_v1.py
│       │   ├── __init__.py
│       │   ├── bundle.py
│       │   ├── common.py
│       │   ├── control.py
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
│       ├── renderers
│       │   ├── __init__.py
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
│       │   ├── ingest_packets.py
│       │   ├── normalize_models.py
│       │   ├── observe_fallbacks.py
│       │   ├── reconcile_evidence.py
│       │   ├── resolve_config.py
│       │   └── validate_topology.py
│       ├── topology
│       │   ├── __init__.py
│       │   ├── capability_builder.py
│       │   ├── classifier.py
│       │   ├── flow_builder.py
│       │   ├── graph_builder.py
│       │   ├── impact.py
│       │   ├── maturity.py
│       │   └── risk.py
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
│       │   ├── failure.py
│       │   ├── packet_store.py
│       │   ├── registry.py
│       │   ├── signature.py
│       │   ├── stage_runner.py
│       │   └── transport_factory.py
│       ├── __init__.py
│       ├── cli.py
│       ├── compiler.py
│       ├── config.py
│       ├── evidence.py
│       ├── models.py
│       └── py.typed
├── tests
│   ├── fixtures
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
│   │   ├── repository_model_packets
│   │   │   ├── l9-gate-sdk
│   │   │   │   ├── receipts
│   │   │   │   │   └── validation-receipt.json
│   │   │   │   ├── manifest.json
│   │   │   │   └── packet.json
│   │   │   └── l9-mcp-server
│   │   │       ├── receipts
│   │   │       │   └── validation-receipt.json
│   │   │       ├── manifest.json
│   │   │       └── packet.json
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
│   │   └── topology_packets
│   │       └── foundational-two-repo
│   │           ├── payload
│   │           │   ├── artifact-records.json
│   │           │   ├── capability-records.json
│   │           │   ├── conflicts.json
│   │           │   ├── diagnostics.json
│   │           │   ├── edge-records.json
│   │           │   ├── evidence.json
│   │           │   ├── flow-records.json
│   │           │   ├── graph-records.json
│   │           │   ├── impact-indexes.json
│   │           │   ├── maturity.json
│   │           │   ├── repository-records.json
│   │           │   ├── risks.json
│   │           │   └── unknowns.json
│   │           ├── receipts
│   │           │   └── validation-receipt.json
│   │           ├── manifest.json
│   │           └── packet.json
│   ├── __init__.py
│   ├── test_architecture_boundary_v5.py
│   ├── test_assessments_v5.py
│   ├── test_cli_v5.py
│   ├── test_confirmed_findings_remediation.py
│   ├── test_dependency_scanner.py
│   ├── test_direct_observation_adapter_v5.py
│   ├── test_evidence_v5.py
│   ├── test_generated_artifact_sync.py
│   ├── test_git_integrity.py
│   ├── test_graph_builder.py
│   ├── test_impact.py
│   ├── test_maturity.py
│   ├── test_output_sink_v5.py
│   ├── test_packet_ingress_v5.py
│   ├── test_packet_models_v5.py
│   ├── test_packet_store_v5.py
│   ├── test_release_readiness.py
│   ├── test_renderers.py
│   ├── test_repo_scanner.py
│   ├── test_report_projection_v5.py
│   ├── test_repository_aggregation_v5.py
│   ├── test_repository_governance.py
│   ├── test_runtime_boundaries_v5.py
│   ├── test_topology_compiler_v5.py
│   ├── test_topology_graph_v5.py
│   ├── test_transport_signature_v5.py
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
├── DEPENDENCY_POLICY.md
├── DEVELOPMENT.md
├── FINAL_TREE.md
├── FIX_MAP.md
├── GIT_TREE_MANIFEST.json
├── GOVERNANCE.md
├── INITIAL_COMMIT.md
├── LICENSE
├── MAINTAINERS.md
├── Makefile
├── MANIFEST.md
├── NOTICE.md
├── pyproject.toml
├── README.md
├── REGRESSION_GUARD.md
├── RELEASING.md
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
