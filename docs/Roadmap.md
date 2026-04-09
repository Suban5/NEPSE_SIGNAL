# Roadmap

Metadata:
- Owner: suban
- Last Reviewed: 2026-04-09
- Source of Truth: api/app.py, api/service.py, cli/commands.py, workflows/*.py, bluechip/detector.py, docs/*.md
- Validation Method: Code + Tests

## Purpose

This document tracks feature-level progress and remaining product milestones. It is intentionally not an execution plan.

## Core Pillars

### Reliability

- deterministic scoring and ranking behavior
- robust error handling across fetch, scan, and API paths
- automated test coverage and CI enforcement

### Usability

- consistent API, CLI, and workflow outputs
- explainable signals and ranking decisions
- clear and validated documentation

### Scalability

- modular workflows with reusable services
- stable API contracts for consumers and integrations
- clear boundaries between orchestration and domain logic

## Completed

### data / nepse_api
- [x] Unified NEPSE data access with provider/coordinator/normalizer pattern.
- [x] Migrated CLI, workflows, and API to shared coordinator factory.
- [x] Added end-to-end parity tests for all data paths.
- [x] Locked in force-refresh and fallback semantics across all callers.

### workflows
- [x] Added structured workflow logging with execution IDs and benchmark correlation.
- [x] Added workflow failure classification for fetch, scan, score, rank, signal, and backtest stages.
- [x] Added shared validation helpers for workflow and CLI inputs.
- [x] Standardized workflow summary payloads for scan, backtest, and symbol analysis.

### api
- [x] Exposed analytics execution IDs in API responses for end-to-end traceability.
- [x] Tightened analytics OpenAPI contracts with typed response models for response metadata.
- [x] Added typed row models for opportunities and signal summary analytics responses.
- [x] Exposed workflow category, stage, and workflow metadata in API error responses.

### cli
- [x] Preserved CLI workflow commands with shared dependency wiring.
- [x] Kept user-facing validation behavior aligned with workflow validation.
- [x] Logged standardized workflow summary payloads for scan, backtest, and symbol analysis.

## In Progress

### api / cli / workflows
- [ ] Standardize output contracts across `api/app.py`, `cli/commands.py`, and `workflows/*.py`.
- [ ] Remove duplicated output assembly between `api/service.py` and workflow helpers.

### testing
- [ ] Increase test coverage to at least 80 percent for service and workflow layers.
- [ ] Expand regression coverage for negative-path behavior in workflows and API routes.

## Remaining / Planned

### api
- [ ] Introduce versioned API responses and explicit backward compatibility rules.
- [ ] Expand generated API docs checks in CI.

### analysis / ranking / backtesting
- [ ] Add backtesting validation against historical NEPSE data and expose summary results via API and CLI.
- [ ] Enforce a single source of truth for scoring logic in `bluechip/detector.py` and related ranking modules.

### product
- [ ] Provide a lightweight dashboard for exploration and reporting.
- [ ] Support richer visualization and historical comparison views.
- [ ] Improve release and versioning discipline for long-term maintainability.

## Strategy Notes

### Backend-First Path

- stabilize data, scoring, and contract behavior first
- complete quality gates and observability before UI work
- add UI only after core outputs are trusted
- treat contract stability and test coverage as release gates

### Recommended Default

- Prefer a backend-first path with a thin UI introduced once core outputs are stable.

## Non-Goals

- real-time trading execution
- high-frequency data ingestion
- complex frontend frameworks
- speculative features without code or test support

## Documentation Strategy

Documentation should stay aligned with code and tests through maintained reference files such as:

- FEATURE_STATUS.md
- API_CONTRACT.md
- SCORING_LOGIC.md
- api-contracts.md
- bluechip-scoring.md

Where possible, docs should be validated against runtime signatures and route behavior.
