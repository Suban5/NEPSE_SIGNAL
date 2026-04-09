# NepseSignal Documentation Index

Metadata:
Owner: suban
Last Reviewed: 2026-04-09
Source of Truth: docs/*.md, api/app.py, api/service.py, cli/commands.py, workflows/*.py, nepse_api/*.py
Validation Method: Code + Tests

## Quick Links

**Starting Out?**
- [Getting Started](getting-started.md) — setup and first commands
- [CLI Reference](cli.md) — all command-line options
- [Configuration Reference](configuration.md) — environment variables and settings
- [Streamlit Dashboard Guide](streamlit-dashboard.md) — run and validate the read-only UI

**Architecture & Design:**
- [Architecture Guide](architecture.md) — system components and data flows
- [API Contracts](api-contracts.md) — endpoint signatures and error handling
- [Workflow Reference](workflows.md) — orchestration and execution patterns
- [Blue-Chip Scoring](bluechip-scoring.md) — ranking logic and explainability

Recent updates:
- API Contracts now includes symbol/date/pagination validation notes and the backtest summary response contract
- Workflow Reference now documents historical backtest validation and portfolio metric summaries
- Blue-Chip Scoring now documents the detector-owned score access and merge helpers used by workflows and ranking views
- U1 output standardization is documented with explicit field inventories across API analytics responses, workflow summaries, and CLI summary logs
- U2 scoring explainability is documented with minimum score-breakdown fields, rationale fields, and comparison-friendly ranking fields
- C1 versioning now documents header-negotiated v1/v2 behavior with additive `v2` analytics contract metadata
- C2 doc alignment now includes runtime contract audit notes and test-backed doc validation checks
- O1 observability now documents structured stage logs with stage, category, and symbol-scope metadata
- O2 observability now documents execution-ID traceability in analytics logs and `/metrics` snapshots
- B1 backtesting now includes deterministic fixture validation and sparse-history edge-case coverage in engine tests
- S2 versioning now extends additive `v2` contract metadata to non-analytics typed endpoints (`/health`, `/metrics`) with test-backed fallback behavior
- Streamlit UI implementation now includes C1-C9 completion with API-backed panels, observability correlation, API explorer coverage, and UI smoke/contract tests
- C10 CI and Docker packaging steps are implemented; local image build remains environment-dependent on Docker daemon availability

**Operations:**
- [API Server Guide](api-server.md) — deployment and HTTP usage
- [Troubleshooting](troubleshooting.md) — common issues and solutions
- [Execution Plan](Execution-Plan.md) — historical implementation roadmap
- [Architecture Evolution](REFACTOR_PLAN.md) — completed work and current status

**Exploration:**
- [Feature Guides](features/README.md) — detailed feature documentation
- [Candlestick Patterns Guide](CandelStick.md) — technical analysis reference
- [Roadmap](Roadmap.md) — long-term product direction

## Feature Guides

- [Feature Index](features/README.md)
- [Data Fetching](features/01-data-fetching.md)
- [Market Scanning](features/02-market-scanning.md)
- [Signal Generation](features/03-signal-generation.md)
- [Ranking](features/04-ranking.md)
- [Backtesting](features/05-backtesting.md)
- [Visualization](features/06-visualization.md)
- [HTTP API](features/07-api-server.md)

## Documentation Standards

All documentation follows [standards.md](standards.md):

- Metadata block (Owner, Last Reviewed, Source of Truth, Validation Method)
- Code examples must be validated
- References must link to source of truth in codebase
- Regular review cycle (bi-weekly or per release)
