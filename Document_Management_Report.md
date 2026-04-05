# Document Management Report

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: config/settings.py, cli/commands.py, api/app.py, api/models.py, api/service.py, workflows/*.py, tests/*
Validation Method: Code + Tests

Date: 2026-04-05
Repository: NepseSignal
Audit Basis: Full repository markdown/text audit validated against code, tests, and runtime behavior.

## 1. Summary Dashboard

- Total documents analyzed: 30
- Documents updated/refactored: 20
- Documents deleted (obsolete): 5
- Documents kept as relevant: 5
- High-priority items addressed:
  - API contract drift and endpoint mismatch
  - Workflow modularization documentation gap
  - Blue-chip scoring model drift
  - Configuration/env reference incompleteness

## 2. Documents Requiring Updates

Status convention: Outdated

### [README.md](README.md)
- Issues:
  - Missing workflow architecture and contract docs linkage
  - Incomplete env/config surface
- Update Actions:
  - MODIFY: overview, docs links, command section
  - ADD: workflow/config/api-contract references
  - REMOVE: stale structural references
  - VERIFY: CLI/API command examples
- Traceability:
  - Derived From: [cli/commands.py](cli/commands.py), [config/settings.py](config/settings.py), [api/app.py](api/app.py)
  - Validated By: [tests/test_cli_commands.py](tests/test_cli_commands.py), [tests/test_api_app.py](tests/test_api_app.py)

### [docs/getting-started.md](docs/getting-started.md)
- Issues:
  - Missing current env set from runtime settings
- Update Actions:
  - MODIFY: setup and run guidance
  - ADD: pointer to full config reference
  - REMOVE: implicit/partial settings guidance
  - VERIFY: setup commands and runtime commands
- Traceability:
  - Derived From: [config/settings.py](config/settings.py), [.env.example](.env.example)
  - Validated By: [tests/test_workflows.py](tests/test_workflows.py)

### [docs/architecture.md](docs/architecture.md)
- Issues:
  - Did not reflect workflow layer and typed contexts
- Update Actions:
  - MODIFY: runtime layers and orchestration model
  - ADD: API middleware/telemetry/cache behavior
  - REMOVE: generic non-traceable architecture language
  - VERIFY: module references exist
- Traceability:
  - Derived From: [workflows/market_scan.py](workflows/market_scan.py), [workflows/symbol_analysis.py](workflows/symbol_analysis.py), [api/telemetry.py](api/telemetry.py)
  - Validated By: [tests/test_workflows.py](tests/test_workflows.py)

### [docs/api-server.md](docs/api-server.md)
- Issues:
  - Missing /metrics and /contracts routes
  - Missing API contract headers
- Update Actions:
  - MODIFY: endpoint family list and startup instructions
  - ADD: runtime headers and contract references
  - REMOVE: stale assumptions
  - VERIFY: route family coverage
- Traceability:
  - Derived From: [api/app.py](api/app.py)
  - Validated By: [tests/test_api_app.py](tests/test_api_app.py)

### [docs/api.md](docs/api.md)
- Issues:
  - Over-emphasized upstream endpoint internals vs local API contract
- Update Actions:
  - MODIFY: integration-boundary focused content
  - ADD: error/contract pointers
  - REMOVE: speculative low-value endpoint detail
  - VERIFY: references to active modules only
- Traceability:
  - Derived From: [api/service.py](api/service.py), [api/app.py](api/app.py)
  - Validated By: [tests/test_api_app.py](tests/test_api_app.py)

### [docs/cli.md](docs/cli.md)
- Issues:
  - Missing sector-relative flags and benchmark artifacts
- Update Actions:
  - MODIFY: command argument surfaces
  - ADD: benchmark output artifacts
  - REMOVE: missing/implicit command details
  - VERIFY: command names and options
- Traceability:
  - Derived From: [cli/commands.py](cli/commands.py)
  - Validated By: [tests/test_cli_commands.py](tests/test_cli_commands.py)

### [docs/features/01-data-fetching.md](docs/features/01-data-fetching.md)
- Issues:
  - API examples included unsupported route assumptions
- Update Actions:
  - MODIFY: verified public fetcher API listing
  - ADD: cache and retry behavior notes
  - REMOVE: unsupported route examples
  - VERIFY: method names/signatures
- Traceability:
  - Derived From: [nepse_api/data_fetcher.py](nepse_api/data_fetcher.py)
  - Validated By: [tests/test_data_fetcher_flows.py](tests/test_data_fetcher_flows.py)

### [docs/features/02-market-scanning.md](docs/features/02-market-scanning.md)
- Issues:
  - Used unsupported MarketScanner constructor parameters
- Update Actions:
  - MODIFY: scanner API and workflow entrypoint usage
  - ADD: output artifact list
  - REMOVE: invalid constructor examples
  - VERIFY: tuple return semantics
- Traceability:
  - Derived From: [market/market_scanner.py](market/market_scanner.py), [workflows/market_scan.py](workflows/market_scan.py)
  - Validated By: [tests/test_workflows.py](tests/test_workflows.py)

### [docs/features/03-signal-generation.md](docs/features/03-signal-generation.md)
- Issues:
  - Signature mismatch for build_trade_signal and threshold drift
- Update Actions:
  - MODIFY: accepted inputs and required columns
  - ADD: threshold definitions
  - REMOVE: fundamentals-as-argument examples
  - VERIFY: function signatures
- Traceability:
  - Derived From: [analysis/signal_engine.py](analysis/signal_engine.py), [signals/signal_engine.py](signals/signal_engine.py)
  - Validated By: [tests/test_signal_engine.py](tests/test_signal_engine.py)

### [docs/features/04-ranking.md](docs/features/04-ranking.md)
- Issues:
  - Outdated detector API assumptions
- Update Actions:
  - MODIFY: scoring and ranking API references
  - ADD: output buckets and explainability hooks
  - REMOVE: non-existent methods
  - VERIFY: method names against detector/ranker modules
- Traceability:
  - Derived From: [bluechip/detector.py](bluechip/detector.py), [ranking/opportunity_ranker.py](ranking/opportunity_ranker.py)
  - Validated By: [tests/test_bluechip_detector.py](tests/test_bluechip_detector.py)

### [docs/features/05-backtesting.md](docs/features/05-backtesting.md)
- Issues:
  - Legacy function signatures and output shape mismatch
- Update Actions:
  - MODIFY: dataclass result fields and valid signatures
  - ADD: portfolio backtest call shape
  - REMOVE: unsupported parameters/metrics
  - VERIFY: backtest engine signatures
- Traceability:
  - Derived From: [backtesting/backtest_engine.py](backtesting/backtest_engine.py)
  - Validated By: [tests/test_backtest_engine.py](tests/test_backtest_engine.py)

### [docs/features/06-visualization.md](docs/features/06-visualization.md)
- Issues:
  - Outdated chart naming and unsupported kwargs
- Update Actions:
  - MODIFY: function signatures and naming
  - ADD: optional dependency behavior
  - REMOVE: unsupported chart options
  - VERIFY: chart helper signatures
- Traceability:
  - Derived From: [visualization/charts.py](visualization/charts.py)
  - Validated By: [tests/test_visualization_charts.py](tests/test_visualization_charts.py)

### [docs/features/07-api-server.md](docs/features/07-api-server.md)
- Issues:
  - Mismatch in response assumptions and missing contract notes
- Update Actions:
  - MODIFY: endpoint families and startup guidance
  - ADD: contract references and negotiation behavior
  - REMOVE: stale response envelope assumptions
  - VERIFY: routes and models
- Traceability:
  - Derived From: [api/app.py](api/app.py), [api/models.py](api/models.py)
  - Validated By: [tests/test_api_app.py](tests/test_api_app.py)

## 3. Criteria for Document Deletion

A document is deletable only when all checks pass:

1. No references in code, scripts, CI/CD, or active docs.
2. Covers deprecated/removed behavior and has no migration value.
3. Duplicates another maintained document with higher accuracy.
4. Stale/misleading beyond efficient recovery.
5. No owner and no maintenance path.

Applied deletions were validated with repository text search and cross-doc link review.

## 4. Recommended Actions Table

| File | Status | Action | Priority | Effort | Justification |
|---|---|---|---|---|---|
| [README.md](README.md) | Relevant | Update (done) | High | M | Aligned with CLI/workflow/API modules |
| [docs/README.md](docs/README.md) | Relevant | Update (done) | High | S | Reindexed to canonical docs |
| [docs/getting-started.md](docs/getting-started.md) | Relevant | Update (done) | High | S | Config alignment with Settings |
| [docs/architecture.md](docs/architecture.md) | Relevant | Update (done) | High | M | Added workflow and API telemetry layers |
| [docs/cli.md](docs/cli.md) | Relevant | Update (done) | High | S | Correct command and output coverage |
| [docs/api-server.md](docs/api-server.md) | Relevant | Update (done) | High | S | Added /metrics and /contracts coverage |
| [docs/api.md](docs/api.md) | Relevant | Update (done) | Medium | S | Integration boundary focus |
| [docs/features/*.md](docs/features/README.md) | Relevant | Update (done) | High | L | Replaced invalid examples with verified APIs |
| [docs/workflows.md](docs/workflows.md) | Relevant | Add (done) | High | M | Missing workflow contract docs |
| [docs/api-contracts.md](docs/api-contracts.md) | Relevant | Add (done) | High | M | Missing canonical endpoint contract doc |
| [docs/configuration.md](docs/configuration.md) | Relevant | Add (done) | High | S | Missing full env/runtime settings doc |
| [docs/bluechip-scoring.md](docs/bluechip-scoring.md) | Relevant | Add (done) | Medium | S | Missing scoring model specification |
| [docs/standards.md](docs/standards.md) | Relevant | Add (done) | High | S | Governance and DoD requirements |
| [docs/FEATURE_STATUS.md](docs/FEATURE_STATUS.md) | Obsolete | Delete (done) | Medium | S | Snapshot status became stale and misleading |
| [docs/FEATURE_LIST.md](docs/FEATURE_LIST.md) | Obsolete | Delete (done) | Medium | S | Duplicate and drift-prone listing |
| [docs/CODE_ANALYSIS.md](docs/CODE_ANALYSIS.md) | Obsolete | Delete (done) | Medium | S | Historical analysis drifted from runtime |
| [docs/TODO.md](docs/TODO.md) | Obsolete | Delete (done) | Low | S | Completed checklist artifact |
| [cookies.txt](cookies.txt) | Obsolete | Delete (done) | Low | S | Unused and not referenced |

## 5. Impact of Recent Changes

### Workflow modularization
- Impact: legacy docs described scanner/CLI internals inaccurately.
- Required updates: workflow reference, feature examples, architecture layering.
- Code sources: [workflows/market_scan.py](workflows/market_scan.py), [workflows/market_backtest.py](workflows/market_backtest.py), [workflows/symbol_analysis.py](workflows/symbol_analysis.py)

### API contract changes
- Impact: endpoint/response/error details drifted.
- Required updates: api-server guide, feature API guide, canonical contract doc.
- Code sources: [api/app.py](api/app.py), [api/models.py](api/models.py), [tests/test_api_app.py](tests/test_api_app.py)

### Blue-chip scoring updates
- Impact: old weight/model explanations were invalid.
- Required updates: feature ranking guide and dedicated scoring doc.
- Code sources: [bluechip/detector.py](bluechip/detector.py), [tests/test_bluechip_detector.py](tests/test_bluechip_detector.py)

### Config/env changes
- Impact: env references were incomplete.
- Required updates: getting-started and dedicated configuration reference.
- Code sources: [config/settings.py](config/settings.py), [.env.example](.env.example)

## 6. Documentation Gaps

The following missing docs were added in this refactor:

- [docs/workflows.md](docs/workflows.md)
- [docs/api-contracts.md](docs/api-contracts.md)
- [docs/configuration.md](docs/configuration.md)
- [docs/bluechip-scoring.md](docs/bluechip-scoring.md)

## 7. Best Practices Alignment

Implemented alignment:

- Single source of truth:
  - API contracts centralized in [docs/api-contracts.md](docs/api-contracts.md)
  - Runtime settings centralized in [docs/configuration.md](docs/configuration.md)
- Modular docs:
  - Separated architecture, workflows, API contracts, scoring, and standards
- Ownership tracking:
  - Metadata block added across maintained documents
- Version awareness:
  - Contract version behavior documented through API contracts and server guide

Governance hooks added:

- Documentation standards file: [docs/standards.md](docs/standards.md)
- PR checklist with docs gate: [.github/pull_request_template.md](.github/pull_request_template.md)
- Automation recommendations documented in standards
