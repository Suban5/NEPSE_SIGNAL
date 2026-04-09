# Copilot Instructions

Metadata:
- Owner: suban
- Last Reviewed: 2026-04-09
- Source of Truth: `.github/copilot-instructions.md`
- Validation Method: Code + Tests

## Repository Standards

- Use environment variables from `.env` via `python-dotenv`.
- Always use the local `.venv`.
- Keep strict separation of concerns across modules.
- Use type hints for all functions and methods.
- Use Google-style docstrings for non-trivial functions.
- Use `logging` instead of `print()`.
- Cover business logic with tests under `tests/`.

## Project Structure Contract

Directory responsibilities must follow the existing codebase:

- `analysis/` -> technical indicators, candlestick aggregation helpers, analysis-level signal utilities
- `api/` -> FastAPI transport layer: routes (`app.py`), request/response contracts (`models.py`), API-facing service adapters (`service.py`), telemetry (`telemetry.py`), caching helpers (`cache.py`)
- `backtesting/` -> single-symbol and portfolio backtest engines and metrics
- `bluechip/` -> blue-chip scoring, normalization policy, detector validation
- `candlestick/` -> candlestick pattern detection primitives used by workflows
- `cli/` -> CLI argument parsing, command dispatch, workflow invocation, user-facing logs
- `config/` -> runtime settings and logging bootstrap
- `data/` -> local datasets, snapshots, cache artifacts (runtime persistence)
- `django/` -> optional Django-specific utilities (keep isolated from core workflow logic)
- `docs/` -> architecture, contracts, guides, roadmap, operational references
- `input/` -> user-provided input artifacts (investment assumptions, ad-hoc inputs)
- `market/` -> market universe construction and scan/filter logic
- `nepse_api/` -> NEPSE data access layer (providers, normalizers, coordinator, factory, persistence)
- `output/` -> generated runtime outputs (CSV/JSON artifacts), not source-of-truth code
- `ranking/` -> opportunity and stock ranking functions
- `signals/` -> trade signal generation logic
- `tests/` -> unit/integration/e2e tests, parity and contract regression tests
- `visualization/` -> chart generation and plotting adapters
- `workflows/` -> orchestration flows (scan/backtest/symbol), shared workflow utilities, context validation

Root file responsibilities:

- `main.py` -> CLI entrypoint only
- `api_server.py` -> ASGI entrypoint for API runtime
- `nepse_analyzer.py` -> compatibility launcher path

Boundary rules:

- `api/` and `cli/` are orchestration/adaptation layers; keep core market/scoring logic out of route/command handlers.
- Core business logic belongs in domain/workflow modules (`analysis`, `market`, `bluechip`, `ranking`, `signals`, `backtesting`, `nepse_api`, `workflows`).
- Reuse existing modules before adding new abstractions.
- No direct network calls in tests unless explicitly integration-scoped and marked.

## Readability and Maintainability Improvements

Apply these defaults for all new or modified code:

- Prefer explicit names over abbreviations (`historical_universe`, not `hist_u`).
- Keep functions focused; target 40 logical lines or fewer where practical.
- Avoid deep nesting; use guard clauses and early returns.
- Add short intent comments only for non-obvious logic branches.
- Keep imports minimal and sorted; remove unused imports.
- Use dataclasses/Pydantic models for structured payloads rather than ad-hoc dict contracts.
- Preserve backward compatibility for API/CLI contracts unless change is explicitly requested.

## Modularity and Best Practice Rules

- Inject dependencies (coordinators, detectors, scanners, callbacks) instead of constructing hidden globals in core logic.
- Keep transformation logic pure where possible (input -> output, minimal side effects).
- Centralize shared orchestration helpers in `workflows/common.py` or dedicated utility modules.
- Avoid duplicating fallback or normalization rules across layers; keep single source-of-truth functions.
- Expose typed contracts at boundaries (API response models, workflow context objects).

## Error Handling

- Never use bare `except`.
- Never silently ignore exceptions.
- Use specific exception classes with actionable messages.
- Log failures with context (symbol, endpoint, execution_id, operation).
- APIs must return structured error payloads (`ApiErrorResponse`).
- Validate external inputs and payload shape before downstream computation.

## Logging and Observability Standards

- Use `logger = logging.getLogger(__name__)`.
- Log levels:
  - `DEBUG` -> detailed internal computation
  - `INFO` -> workflow lifecycle and key milestones
  - `WARNING` -> recoverable issues and fallbacks
  - `ERROR` -> failures requiring action
- Never log secrets, tokens, or credentials.
- Include correlation fields at boundaries:
  - API: `request_id`
  - Workflows/CLI analytics: `execution_id`

## Data and API Contract Rules

- Validate API response fields before use (missing/null/shape changes).
- Do not assume upstream API stability.
- Use timeouts and retry/fallback policies for network access.
- Prefer typed models for endpoint contracts and workflow outputs.
- Maintain contract tests whenever a response schema changes.

## Configuration

- All configurable values must come from environment variables or the config module.
- Never hardcode URLs, credentials, or environment-specific file paths.
- Keep defaults in `config/settings.py` and document externally visible behavior in docs.

## Testing Standards

- Use `pytest`.
- Cover happy paths, edge cases, and failure modes.
- Mock external APIs and file I/O for unit tests.
- Keep tests deterministic, fast, and offline-runnable.
- When contracts change, update:
  - endpoint tests
  - OpenAPI/schema assertions
  - relevant docs under `docs/`

## Anti-Patterns to Avoid

- Functions with mixed concerns (fetch + transform + persist + render)
- Deep nesting (> 3 levels) without guard clauses
- Hidden side effects and implicit state mutation
- Duplicated fallback logic across API/CLI/workflows
- Unstructured dictionaries crossing module boundaries when typed models exist

## Definition of Done

Code is complete only if:

- It runs without errors.
- It follows this project structure contract.
- It includes type hints and appropriate docstrings.
- It handles edge and failure cases explicitly.
- It includes or updates tests for behavior changes.
- It updates impacted documentation (contracts, guides, roadmap, refactor log) when behavior or schema changes.

