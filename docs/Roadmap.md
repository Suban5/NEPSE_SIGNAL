# Roadmap

Metadata:
Owner: suban
Last Reviewed: 2026-04-08
Source of Truth: api/app.py, api/service.py, cli/commands.py, workflows/*.py, bluechip/detector.py, docs/*.md
Validation Method: Code + Tests

Version: v1.0
Owner: suban (single owner)
Contributors: TBD
Review Cycle: bi-weekly or per release

## Purpose

This document describes the next major improvement areas for NepseSignal at a high level. It is intentionally not an execution plan.

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

## Product Direction

NepseSignal should evolve with three consistent goals:

- keep analysis and scoring reliable
- improve usability of outputs and APIs
- expose insights through a lightweight interface

## Current Gaps (Code-Derived)

- inconsistent response schema between API and CLI paths
- duplicated logic between service and workflow layers
- limited error handling in data fetch workflows
- insufficient test coverage in `workflows/*`

## Milestones

### Short-Term (Completed)

Stabilization phase focused on reliability and contract consistency:

✅ **Completed (2026-04-08)**:
- Unified NEPSE data access with provider/coordinator/normalizer pattern
- Migrated CLI, workflows, and API to shared coordinator factory
- Added end-to-end parity tests for all data paths
- Locked in force-refresh and fallback semantics across all callers
- Deprecated legacy fetcher with backward-compatible alias
- Added structured workflow logging with execution IDs and benchmark correlation
- Exposed analytics execution IDs in API responses for end-to-end traceability
- Tightened analytics OpenAPI contracts with typed response models for response metadata

Remaining stabilization tasks:
- Increase test coverage to at least 80 percent for service and workflow layers
- Standardize output contracts across `api/app.py`, `cli/commands.py`, and `workflows/*.py`
- Add failure classification for fetch, scan, and ranking workflows
- Strengthen input validation across all entry points

### Mid-Term

Platform consistency, technical debt reduction, and contract stability:

- reduce duplicate logic across `api/service.py`, `cli/commands.py`, and `workflows/*.py`
- enforce a single source of truth for scoring logic in `bluechip/detector.py` and related ranking modules
- introduce versioned API responses and define backward compatibility rules
- add backtesting validation against historical NEPSE data and expose summary results via API and CLI
- enhance documentation around contracts, configuration behavior, and scoring logic
- add quality gates through automated checks in CI

### Long-Term

Product expansion and accessibility:

- introduce a stable analytics API surface for external consumers
- provide a lightweight dashboard for exploration and reporting
- support richer visualization and historical comparison views
- improve release and versioning discipline for long-term maintainability

## Technical Debt Reduction

- remove duplicated logic across layers
- refactor workflow orchestration boundaries
- enforce a single source of truth for scoring and ranking behavior
- tighten schema and payload contracts across API and CLI outputs

## Strategy Triggers

### Choose Backend-First if:

- scoring logic is still unstable
- API contracts change frequently
- test coverage is low or failure-path behavior is unclear

### Choose UI-First if:

- API contracts are stable enough for consumption
- stakeholder demos or user validation are needed quickly
- backend behavior is already covered by tests and observability

## Strategy Options

### Backend-First Path

Best when reliability and maintainability are the top priorities:

- stabilize data, scoring, and contract behavior first
- complete quality gates and observability before UI work
- add UI only after core outputs are trusted
- treat contract stability and test coverage as release gates

### UI-First Path

Best when early demos and user adoption are the top priorities:

- deliver a minimal dashboard quickly using existing API endpoints
- iterate on usability and reporting workflows with user feedback
- harden backend contracts in parallel as UI usage grows
- keep the UI thin and avoid duplicating backend business logic

## Recommended Default

For this project stage, prefer a backend-first path with a thin UI introduced once core outputs are stable.

## Non-Goals (Current Phase)

- real-time trading execution
- high-frequency data ingestion
- complex frontend frameworks
- speculative features without code or test support

## Long-Term Shape

The project should remain centered on these capabilities:

- market data fetching and normalization
- signal generation and ranking
- backtesting and analysis
- API access for automation and integrations
- optional UI for reporting and exploration

## Documentation Strategy

Documentation should stay aligned with code and tests through maintained reference files such as:

- FEATURE_STATUS.md
- API_CONTRACT.md
- SCORING_LOGIC.md
- api-contracts.md
- bluechip-scoring.md

Where possible, docs should be validated against runtime signatures and route behavior.

## Notes

This roadmap is intentionally high level. Detailed sequencing, ownership, and timelines should be defined in a separate execution plan document.
