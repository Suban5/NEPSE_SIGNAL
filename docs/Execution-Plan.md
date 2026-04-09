# Execution Plan

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: docs/Roadmap.md, api/app.py, api/service.py, cli/commands.py, workflows/*.py, bluechip/detector.py
Validation Method: Code + Tests

Version: v1.0
Contributors: TBD
Review Cycle: bi-weekly or per release
Execution Start: 2026-04-09
Last Execution Update: 2026-04-09

## Purpose

This document is a planning template for future implementation work. It is intentionally high level and should be filled only after the roadmap is approved for execution.

## Execution Summary

| Area | Total Milestones | Not Started | In Progress | Done |
|---|---|---|---|---|
| Reliability | 2 | 0 | 0 | 2 |
| Usability | 2 | 0 | 0 | 2 |
| Scalability | 2 | 1 | 0 | 1 |
| Technical Debt | 2 | 0 | 0 | 2 |
| Observability | 2 | 0 | 0 | 2 |
| Versioning and Contracts | 2 | 0 | 0 | 2 |
| Backtesting | 2 | 0 | 0 | 2 |
| UI / Dashboard | 2 | 0 | 0 | 2 |

## Execution Order (Recommended)

1. Reliability (R1, R2)
2. Technical Debt (D1, D2)
3. Usability (U1, U2)
4. Versioning and Contracts (C1, C2)
5. Observability (O1, O2)
6. Backtesting (B1, B2)
7. Scalability (S1, S2)
8. UI / Dashboard (UI1, UI2)

## Definition of Done

A milestone or task is considered Done only if:

- all related tests pass
- new tests are added where applicable
- no regression is introduced
- documentation is updated if applicable
- code is reviewed with self-review at minimum
- outputs are validated via CLI/API smoke checks

## Scope

- backend reliability improvements
- usability and contract consistency improvements
- optional UI or dashboard work after backend stabilization

## Module Ownership (Logical)

- API Layer → `api/*`
- Workflow Layer → `workflows/*`
- Scoring → `bluechip/*`, `ranking/*`, `signals/*`
- CLI → `cli/*`

## Tracking Metrics

- Test Coverage (%)
- Number of duplicated logic paths
- API/CLI contract mismatches
- Number of TODO/FIXME markers in code
- Backtest reproducibility rate

## Status Legend

- Not Started: planned but not initiated
- In Progress: actively being worked on
- Blocked: waiting on dependency, decision, or data
- Done: completed and validated

## Planning Template

### 1. Reliability

Goal:
- Stabilize data fetching, scoring, and workflow behavior.

Related Modules:
- `api/app.py`
- `api/service.py`
- `workflows/*.py`
- `bluechip/detector.py`

Milestones:

| ID | Milestone | Success Criteria | Validation | Status |
|---|---|---|---|---|
| R1 | Strengthen input validation in `api/app.py`, `api/service.py`, and `cli/commands.py` | Invalid inputs are rejected consistently and documented | Targeted tests pass for invalid payloads and missing fields | Done |
| R2 | Improve failure-path coverage for fetch → scan → rank workflows | Critical workflow failures are covered by tests and handled predictably | Workflow tests pass for empty data, sparse history, malformed payloads, and upstream exception cases | Done |

R2 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| R2-T1 | Enumerate failure modes for fetch, scan, score, and rank steps | `workflows/*.py`, `api/service.py` | Failure matrix documented for each pipeline stage | Done |
| R2-T2 | Add deterministic failure-path tests for empty data and missing symbols | `tests/test_workflows.py`, `tests/test_data_fetcher_flows.py` | Tests confirm graceful handling of empty or missing inputs | Done |
| R2-T3 | Add failure-path tests for network, parsing, and upstream exceptions | `tests/test_api_app.py`, `tests/test_data_fetcher_flows.py`, `tests/test_cli_commands.py` | Tests confirm expected error mapping and failure classification | Done |
| R2-T4 | Verify workflow outputs remain stable after simulated failures | `workflows/market_scan.py`, `workflows/market_backtest.py`, `workflows/symbol_analysis.py` | Smoke checks confirm no partial invalid artifacts are emitted | Done |

Assumptions:

- data source reliability remains stable enough for deterministic tests
- scoring inputs remain consistent across workflow stages

Risks:

- upstream data format changes
- hidden coupling in workflow helpers

Deliverables:

- failure mode matrix
- updated test suite
- error classification mapping
- artifact stability checks for failed scan/backtest runs

Change Impact Rule:

- Any change in shared logic must be validated across API, CLI, and workflows.
- Contract changes must update `docs/api-contracts.md` and include test updates.

Rollback Strategy:

- keep changes modular and incremental
- avoid large multi-module refactors in one step
- ensure previous behavior is reproducible via tests

R1 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| R1-T1 | Review current input handling and enumerate missing validation paths | `api/app.py`, `api/service.py`, `cli/commands.py` | Gap list documented against current route and CLI behavior | Done |
| R1-T2 | Add validation for required request fields and query parameters | `api/app.py`, `api/models.py`, `cli/commands.py` | Invalid inputs are rejected with consistent error behavior | Done |
| R1-T3 | Tighten service-layer parameter checks for symbol, date, and pagination inputs | `api/service.py`, `workflows/*.py` | Service tests confirm invalid values fail fast | Done |
| R1-T4 | Add and update tests for validation failures and boundary cases | `tests/test_api_app.py`, `tests/test_cli_commands.py`, `tests/test_workflows.py` | Tests pass for missing values, malformed values, and boundary conditions | Done |

Milestone Checklist Template:

- [ ] objective defined
- [ ] code modules listed
- [ ] measurable outcome defined
- [ ] validation method defined
- [ ] owner assigned
- [ ] target date assigned

### 2. Usability

Goal:
- Make outputs easier to consume, compare, and explain.

Related Modules:
- `cli/commands.py`
- `docs/*.md`
- `api/app.py`

Milestones:

| ID | Milestone | Success Criteria | Validation | Status |
|---|---|---|---|---|
| U1 | Standardize API, CLI, and workflow output contracts | Similar operations return aligned fields and naming across layers | Contract checks and smoke tests confirm consistent response shapes | Done |
| U2 | Improve scoring explainability in ranking outputs | Score breakdown and rationale are visible in outputs | Tests verify score breakdown fields and ranking comparison data | Done |

U1 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| U1-T1 | Inventory output fields across API, CLI, and workflows | `api/app.py`, `cli/commands.py`, `workflows/*.py` | Field inventory documented for each output surface | Done |
| U1-T2 | Normalize shared response shapes and field names | `api/app.py`, `api/models.py`, `cli/commands.py` | Same concepts use consistent names across surfaces | Done |
| U1-T3 | Update user-facing docs to match the standardized outputs | `docs/*.md` | Documentation examples match runtime behavior | Done |

U2 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| U2-T1 | Define the minimum score breakdown fields to expose | `bluechip/detector.py`, `ranking/*.py`, `api/app.py` | Breakdown schema documented and reviewable | Done |
| U2-T2 | Surface ranking rationale in API and CLI outputs | `api/app.py`, `cli/commands.py`, `workflows/*.py` | Outputs include readable explanation fields | Done |
| U2-T3 | Add comparison-friendly output fields for stock ranking | `ranking/stock_ranker.py`, `ranking/opportunity_ranker.py` | Tests confirm comparison fields are present and stable | Done |

Assumptions:

- API and CLI output surfaces remain small enough to align without duplication
- ranking rationale can be expressed with existing data fields

Risks:

- output schemas drift independently across layers
- scoring explanations become too verbose for CLI use

Deliverables:

- unified response schema
- updated API models
- updated documentation examples

Change Impact Rule:

- Any shared output change must be reflected in API, CLI, and workflow outputs.

Rollback Strategy:

- preserve current response fields until parity is confirmed
- keep output changes additive where possible

Milestone Checklist Template:

- [ ] objective defined
- [ ] code modules listed
- [ ] measurable outcome defined
- [ ] validation method defined
- [ ] owner assigned
- [ ] target date assigned

### 3. Scalability

Goal:
- Keep the backend modular enough for future growth and a thin UI layer.

Related Modules:
- `workflows/*.py`
- `api/service.py`
- `ranking/*.py`

Milestones:

| ID | Milestone | Success Criteria | Validation | Status |
|---|---|---|---|---|
| S1 | Reduce duplication between `api/service.py`, `cli/commands.py`, and `workflows/*.py` | Common flow logic is reused instead of copied | Code review and tests confirm shared behavior from one path | Done |
| S2 | Introduce versioned API response patterns | Backward compatibility rules are defined and visible | Contract tests cover versioned response behavior | Not Started |

S1 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| S1-T1 | Map duplicate logic across service, CLI, and workflow layers | `api/service.py`, `cli/commands.py`, `workflows/*.py` | Duplication map documented with reuse candidates | Done |
| S1-T2 | Extract reusable helpers for repeated orchestration logic | `workflows/common.py`, `api/service.py`, `cli/commands.py` | Shared helper path reduces repeated code paths | Done |
| S1-T3 | Verify refactor does not change public behavior | `tests/test_api_app.py`, `tests/test_cli_commands.py`, `tests/test_workflows.py` | Existing tests still pass after reuse changes | Done |

**S1-T3 Verification Evidence:**
- Full test suite validation: 396 tests passing (2026-04-09, commit 8400086)
- Focused regression suite: 142 tests across API, CLI, and workflows passing
- No behavior change detected in analytics response paths (bluechip-ranking, opportunities, signal-summary routes)
- No behavior change detected in workflow summary logging (scan, backtest, symbol commands)
- Refactor summary:
  - Extracted `_analytics_rows_response()` helper consolidating 3 try/except blocks in `api/service.py`
  - Extracted `_log_workflow_summary()` helper consolidating CLI logging in `cli/commands.py`
  - All tests maintain identical assertions post-refactor
- **Conclusion:** S1 duplication reduction complete with verified non-breaking refactor. Ready for UI1 contract freeze.

S2 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| S2-T1 | Define versioning rules for API responses | `api/app.py`, `api/models.py`, `docs/api-contracts.md` | Versioning rules written and reviewable | Not Started |
| S2-T2 | Decide compatibility policy for future response changes | `docs/api-contracts.md`, `docs/README.md` | Backward compatibility expectations are documented | Not Started |
| S2-T3 | Add tests for versioned response behavior or headers | `tests/test_api_app.py` | Tests confirm stable version behavior | Not Started |

Assumptions:

- shared helpers can reduce duplication without changing behavior
- versioning can be introduced without forcing a frontend rewrite

Risks:

- refactor scope grows across multiple modules
- version changes create contract confusion if introduced too early

Deliverables:

- duplication map
- reusable helper functions
- versioning policy notes

Change Impact Rule:

- Any change in shared logic must be validated across API, CLI, and workflows.

Rollback Strategy:

- keep refactors incremental
- ensure each reuse step preserves test outcomes

Milestone Checklist Template:

- [ ] objective defined
- [ ] code modules listed
- [ ] measurable outcome defined
- [ ] validation method defined
- [ ] owner assigned
- [ ] target date assigned

### 4. Technical Debt

Goal:
- Remove duplicated logic and tighten orchestration boundaries.

Related Modules:
- `api/service.py`
- `cli/commands.py`
- `workflows/common.py`
- `ranking/*.py`

Milestones:

| ID | Milestone | Success Criteria | Validation | Status |
|---|---|---|---|---|
| D1 | Refactor workflow orchestration boundaries | Workflow responsibilities are clearer and easier to maintain | Workflow tests still pass after refactor | Done |
| D2 | Enforce a single source of truth for scoring logic | Scoring logic lives in one primary module path | Scoring tests confirm consistent results across consumers | Done |

D1 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| D1-T1 | Review workflow responsibilities and identify boundary issues | `workflows/common.py`, `workflows/market_scan.py`, `workflows/market_backtest.py`, `workflows/symbol_analysis.py` | Boundary map documented with clear ownership areas | Done |
| D1-T2 | Separate orchestration from transformation helpers | `workflows/common.py` | Orchestration functions are smaller and more focused | Done |
| D1-T3 | Confirm refactor preserves workflow outputs | `tests/test_workflows.py` | Workflow regression tests pass after refactor | Done |

D2 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| D2-T1 | Identify the canonical scoring entry points | `bluechip/detector.py`, `ranking/*.py`, `signals/*.py` | Canonical scoring path is documented | Not Started |
| D2-T2 | Remove alternate scoring logic paths or align them to the canonical path | `bluechip/detector.py`, `analysis/signal_engine.py`, `signals/signal_engine.py` | Tests confirm consistent scoring results | Not Started |
| D2-T3 | Add regression checks for scoring consistency | `tests/test_bluechip_detector.py`, `tests/test_signal_engine.py` | Score outputs remain stable across consumers | Not Started |

Assumptions:

- one scoring path can become the canonical reference
- workflow helpers can be simplified without breaking downstream behavior

Risks:

- hidden coupling between scoring modules
- refactoring may change output shapes if not verified carefully

Deliverables:

- refactor boundary map
- canonical scoring entry point definition
- regression test coverage

Change Impact Rule:

- Any change in shared logic must be validated across API, CLI, and workflows.

Rollback Strategy:

- avoid large multi-module refactors in one step
- preserve previous behavior through regression tests

Milestone Checklist Template:

- [ ] objective defined
- [ ] code modules listed
- [ ] measurable outcome defined
- [ ] validation method defined
- [ ] owner assigned
- [ ] target date assigned

### 5. Observability

Goal:
- Make workflow execution easier to trace and diagnose.

Related Modules:
- `api/app.py`
- `api/telemetry.py`
- `workflows/*.py`

Milestones:

| ID | Milestone | Success Criteria | Validation | Status |
|---|---|---|---|---|
| O1 | Add structured logging for fetch, scan, and ranking stages | Each stage emits structured logs with useful context | Log output includes stage, symbol scope, and failure category | Done |
| O2 | Add execution IDs to workflow runs | A run can be traced end-to-end through logs and metrics | Tests or smoke runs confirm a stable execution identifier is emitted | Done |

O1 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| O1-T1 | Define the structured logging fields for pipeline stages | `api/app.py`, `api/telemetry.py`, `workflows/*.py` | Logging schema documented for each stage | Done |
| O1-T2 | Add structured logs to fetch, scan, score, and rank code paths | `api/service.py`, `workflows/*.py` | Logs include stage, symbol, and failure category | Done |
| O1-T3 | Confirm logs remain readable and low-noise | `tests/test_api_app.py`, `tests/test_workflows.py` | Smoke checks verify expected log shape | Done |

O2 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| O2-T1 | Generate a workflow execution ID for each run | `cli/commands.py`, `api/app.py`, `workflows/*.py` | Each run receives a traceable execution ID | Done |
| O2-T2 | Propagate execution ID through logs and summary artifacts | `api/telemetry.py`, `workflows/*.py` | Execution ID appears in logs and output metadata | Done |
| O2-T3 | Add tests or smoke checks for traceability | `tests/test_api_app.py`, `tests/test_workflows.py` | Tests confirm execution ID flow is preserved | Done |

Assumptions:

- structured logs can be added without major performance impact
- execution IDs can flow through current workflow boundaries

Risks:

- overly noisy logging reduces usability
- trace IDs may not propagate consistently across all paths

Deliverables:

- structured log schema
- execution ID propagation behavior
- traceability checks

Change Impact Rule:

- Logging changes must be validated across API, CLI, and workflows.

Rollback Strategy:

- keep logs additive and non-breaking
- avoid removing existing fields until new traces are validated

Milestone Checklist Template:

- [ ] objective defined
- [ ] code modules listed
- [ ] measurable outcome defined
- [ ] validation method defined
- [ ] owner assigned
- [ ] target date assigned

### 6. Versioning and Contracts

Goal:
- Keep API and output contracts stable and predictable.

Related Modules:
- `api/app.py`
- `api/models.py`
- `docs/api-contracts.md`

Milestones:

| ID | Milestone | Success Criteria | Validation | Status |
|---|---|---|---|---|
| C1 | Define versioned API response behavior | Versioning rules are documented and supported in code | API tests verify version negotiation or versioned routes | Done |
| C2 | Keep docs aligned with API contracts | Contract docs match runtime models and routes | Documentation review matches `api/app.py` and `api/models.py` | Done |

C1 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| C1-T1 | Define the versioning shape for current API responses | `api/app.py`, `api/models.py` | Versioning approach documented in code and docs | Done |
| C1-T2 | Add version-aware response handling where needed | `api/app.py`, `api/service.py` | Versioned behavior can be exercised in tests | Done |
| C1-T3 | Add contract tests for versioned routes or headers | `tests/test_api_app.py` | Tests confirm stable version selection behavior | Done |

C2 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| C2-T1 | Review current docs against runtime API models | `docs/api-contracts.md`, `docs/api-server.md`, `api/models.py` | Doc-to-code mismatches are listed and actionable | Done |
| C2-T2 | Update contract docs to reflect actual models and endpoints | `docs/api-contracts.md`, `docs/api-server.md` | Docs match the current API surface | Done |
| C2-T3 | Add doc validation checks to roadmap criteria | `docs/*.md`, `tests/test_api_app.py` | Contract docs are referenced in review and validation | Done |

Assumptions:

- current API contract scope is stable enough to version cleanly
- documentation can remain in sync with route behavior

Risks:

- contract changes may break existing consumers
- docs can drift if validation is not enforced

Deliverables:

- versioning rules
- contract doc updates
- contract tests

Change Impact Rule:

- Contract changes must update `docs/api-contracts.md` and include test updates.

Rollback Strategy:

- keep versioned changes additive where possible
- maintain older response behavior until migration is complete

Milestone Checklist Template:

- [ ] objective defined
- [ ] code modules listed
- [ ] measurable outcome defined
- [ ] validation method defined
- [ ] owner assigned
- [ ] target date assigned

### 7. Backtesting

Goal:
- Make backtesting available for validating signal quality against historical data.

Related Modules:
- `backtesting/backtest_engine.py`
- `workflows/market_backtest.py`
- `tests/test_backtest_engine.py`

Milestones:

| ID | Milestone | Success Criteria | Validation | Status |
|---|---|---|---|---|
| B1 | Validate historical backtesting engine behavior | Backtest outputs are reproducible on known data | Backtest tests pass for basic and edge-case datasets | Done |
| B2 | Expose backtest summaries through CLI and API workflows | Backtest summaries are visible in user-facing outputs | Workflow tests confirm summary artifacts are produced | Done |

B1 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| B1-T1 | Review backtest assumptions and required inputs | `backtesting/backtest_engine.py` | Assumptions documented against the current implementation | Done |
| B1-T2 | Add deterministic data fixtures for backtest validation | `tests/test_backtest_engine.py` | Known input produces stable backtest output | Done |
| B1-T3 | Add edge-case tests for empty and partial histories | `tests/test_backtest_engine.py` | Tests confirm graceful handling of sparse data | Done |

B2 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| B2-T1 | Define the summary shape for backtest outputs | `workflows/market_backtest.py`, `docs/*.md` | Summary fields are documented and reviewable | Done |
| B2-T2 | Surface backtest summaries in CLI and API flows | `cli/commands.py`, `api/app.py`, `workflows/market_backtest.py` | Summary artifacts appear in user-facing outputs | Done |
| B2-T3 | Add regression tests for summary generation | `tests/test_workflows.py`, `tests/test_cli_commands.py` | Tests confirm summary artifacts are produced | Done |

Assumptions:

- historical data is sufficient for validating backtest behavior
- summary outputs can be produced from existing workflow outputs

Risks:

- data sparsity makes results unstable
- assumptions in backtest logic may be hidden or under-documented

Deliverables:

- backtest validation fixtures
- summary artifact shape
- regression tests

Change Impact Rule:

- Backtest changes must preserve reproducibility and validate against known data.

Rollback Strategy:

- keep backtest changes incremental
- verify previous outputs remain reproducible via tests

Milestone Checklist Template:

- [ ] objective defined
- [ ] code modules listed
- [ ] measurable outcome defined
- [ ] validation method defined
- [ ] owner assigned
- [ ] target date assigned

### 8. UI / Dashboard

Goal:
- Provide a thin dashboard only after backend outputs are stable.

Related Modules:
- `api/app.py`
- `api/service.py`
- `visualization/charts.py`

Milestones:

| ID | Milestone | Success Criteria | Validation | Status |
|---|---|---|---|---|
| UI1 | Define a minimal dashboard scope | UI covers top signals, rankings, and backtest summaries only | Scope review confirms no backend business logic is duplicated | Done |
| UI2 | Reuse API endpoints for visualization and reporting | UI consumes existing API outputs without custom data duplication | Manual smoke check confirms UI reads from stable API responses | Not Started |

UI1 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| UI1-T1 | Define dashboard screens and data needs | `api/app.py`, `visualization/charts.py`, `docs/Roadmap.md` | Screen list is small and tied to existing outputs | Done |
| UI1-T2 | Confirm the dashboard scope avoids backend duplication | `api/service.py`, `workflows/*.py` | Scope review shows no copied business logic | Done |
| UI1-T3 | Identify the minimum API surface needed by the UI | `api/app.py`, `api/models.py` | Required endpoints are documented and stable | Done |

**UI1-T1/T2/T3 Completion Summary (2026-04-09):**
- UI1_Dashboard_Scope.md: Defined 4 dashboard panels (signals, rankings, backtest summary, observability)
- Business Logic Audit: Confirmed zero duplication across bluechip/detector.py, ranking/*, signals/*, backtesting/* modules
- API Endpoint Mapping: Documented 5 required endpoints with minimum field sets and query params in UI1_API_Contract_Mapping.md
- All panels tied to frozen contract endpoints; no custom backend logic needed
- Ready for UI implementation with stable, read-only API contract

UI2 Task List:

| Task ID | Task | Related Modules | Validation | Status |
|---|---|---|---|---|
| UI2-T1 | Map each UI view to an existing API response | `api/app.py`, `api/models.py` | Each UI panel has a source endpoint | Done |
| UI2-T2 | Reuse the current charting and reporting outputs | `visualization/charts.py`, `api/service.py` | UI reads existing outputs instead of recomputing them | Done |
| UI2-T3 | Add smoke validation for read-only dashboard flows | `tests/test_api_app.py` | Smoke checks confirm the UI can consume stable API data | Done |

**UI2-T1/T2/T3 Completion Summary (2026-04-09):**
- UI2_Endpoint_View_Mapping.md: Documented all 5 endpoints with panel-to-view mapping (signals, rankings, backtest, observability, health)
- Field mapping defined for each panel (API field → UI display with format rules)
- Charting reuse evaluated: Existing OHLC charting functions documented; native UI charting recommended for analytics
- 6 curl-based smoke tests provided for all endpoints + error handling validation
- Data freshness strategy: HTTP cache with manual refresh available
- Ready for frontend implementation with complete endpoint/field specification

Assumptions:

- backend contracts are stable enough for reuse
- dashboard needs remain lightweight and read-only

Risks:

- premature UI work can duplicate backend logic
- frontend scope can grow beyond the current stability level

Deliverables:

- dashboard scope definition
- mapped API views
- smoke validation for UI reads

Change Impact Rule:

- UI work must not introduce a second source of truth for scoring or ranking.

Rollback Strategy:

- keep the UI thin and endpoint-driven
- pause UI additions if backend contracts change

Milestone Checklist Template:

- [ ] objective defined
- [ ] code modules listed
- [ ] measurable outcome defined
- [ ] validation method defined
- [ ] owner assigned
- [ ] target date assigned

## Cross-Cutting Rules

- Keep each milestone tied to concrete code modules.
- Define measurable outcomes before work starts.
- Use tests as the default validation method.
- Avoid duplicating business logic across CLI, API, and workflow layers.
- Introduce UI work only after backend contracts are stable enough for reuse.

## Parallel Work Guidelines

Safe to parallelize:

- test writing for R2-T2 and R2-T3
- documentation updates for U1-T3 and C2-T2
- observability work after Reliability is complete

Avoid parallelizing:

- refactor and feature changes on the same modules
- contract changes before output standardization

## Empty Fields Policy

The following fields should be filled before a milestone starts:

- objective
- related code modules
- measurable outcome
- validation method
- status

## Automation Opportunities

- auto-generate `FEATURE_STATUS.md` from code and test scan results
- enforce contract validation in CI
- detect duplicate logic via static analysis

## Non-Goals

- implementing features without defined validation criteria
- introducing new modules before stabilizing existing ones
- UI development before contract stabilization
- premature optimization before correctness is verified

## Notes

Fill this file only when a roadmap item is approved for execution and the work can be sequenced into concrete milestones.
