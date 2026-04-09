# Streamlit UI Development Guidance for Copilot

Metadata:
- Owner: suban
- Created: 2026-04-09
- Last Reviewed: 2026-04-09
- Purpose: Implementation guidance for read-only Streamlit dashboard development
- Source Inputs:
  - docs/UI1_Dashboard_Scope.md
  - docs/UI1_API_Contract_Mapping.md
  - docs/UI2_Endpoint_View_Mapping.md
  - docs/api-contracts.md
- Validation Method: Code + API Contract + UI Behavior Audit

---

## Implementation Checklist (Copilot Execution)

Use this table as the primary execution tracker.

| ID | Task | Output Artifact | Validation Gate | Status |
|---|---|---|---|---|
| C1 | Create Streamlit app shell and tab layout | `ui/app.py` | App starts and tabs render | Done |
| C2 | Implement centralized API client with timeout and retry | `ui/api_client.py` | Unit tests pass for retries and failures | Done |
| C3 | Add core panel components (signals, rankings, opportunities, backtest, metrics) | `ui/components/*.py` | Each panel renders with API response | Done |
| C4 | Enforce endpoint and query parameter contracts in UI controls | `ui/components/*.py` | No out-of-contract request emitted | Done |
| C5 | Implement version negotiation and diagnostics (`/contracts`, response headers) | `ui/app.py`, `ui/api_client.py` | v1/v2 and fallback behavior verified | Done |
| C6 | Add observability correlation (`execution_id` with `/metrics`) | `ui/components/metrics.py` | Correlation visible in UI | Done |
| C7 | Add error, empty, loading, timeout states with request_id visibility | `ui/utils/error_handling.py`, components | Failure states are actionable and consistent | Done |
| C8 | Add API explorer coverage for non-core endpoint groups | `ui/components/explorer.py` | Coverage matrix complete for documented endpoints | Done |
| C9 | Add test suite (unit, smoke, contract) | `tests/ui/*` | CI test stage passes | Done |
| C10 | Add CI checks for contract drift and deployment packaging | `.github/workflows/*`, `Dockerfile` | CI passes and image builds | Blocked |

Status values:
- Not Started
- In Progress
- Blocked
- Done

Completion rule:
- The implementation is release-ready only when all C1 to C10 rows are marked Done and Definition of Done is satisfied.

Current blocker for C10:
- Local environment does not have an active Docker daemon, so local `docker build -f Dockerfile.ui ...` validation cannot complete.

Unblock options:
- run with a working Docker daemon and execute `docker build -f Dockerfile.ui -t nepsesignal-ui:test .`
- or rely on GitHub Actions runner to validate the Docker build step in CI

---

## Non-Negotiable Rules (STRICT)

1. UI is strictly READ-ONLY.
2. UI must NOT implement:
   - scoring logic
   - ranking logic
   - signal generation
   - backtest computation
3. UI must ONLY:
   - call backend APIs over HTTP
   - display API responses
4. UI allows ONLY client-side:
   - sorting
   - filtering
5. UI must NOT:
   - recompute metrics
   - derive new fields
   - modify API payload data
6. If a field is missing from API response:
   - DO NOT infer or compute it
   - display fallback or omit safely

---

## Anti-Hallucination Rules (CRITICAL)

- Do NOT invent:
  - API endpoints
  - response fields
  - query parameters
- Do NOT assume:
  - backend capabilities
  - data availability
- If something is not defined in API contracts:
  - omit it OR mark as "Not Available"
- Always align with source documents

---

## 1) Dashboard Purpose and Key Features

### Objective

Provide read-only operational visibility of backend analytics outputs.

### Scope Definition (FIXED)

Panels (exactly 4):
1. Top Trade Signals
2. Blue-Chip Rankings
3. Portfolio Backtest Summary
4. Workflow Observability (optional)

### Allowed User Actions

- refresh data
- client-side filter
- client-side sort
- tab navigation
- optional export (displayed data only)

### Out of Scope (STRICT)

- business logic in UI
- write/update APIs
- real-time/streaming
- user authentication (v1)
- persistent state (v1)

### Implementation Phases

- Phase A: Core UI1 panels only
- Phase B: Optional read-only API explorer

---

## 2) Data Sources and Mapping to UI Elements

### Requirements

- Every UI element MUST map to:
  - a real API endpoint
  - defined response fields

### Step-by-Step Execution

1. Build endpoint mapping matrix from source docs
2. For each panel define:
   - endpoint path
   - query params (with defaults)
   - required fields
   - optional fields
   - UI component mapping

### Phase A Endpoint Mapping

- `/analytics/signal-summary` → signals table
- `/analytics/bluechip-ranking` → ranking table
- `/analytics/opportunities` → opportunities table (or API explorer mandatory card)
- `/analytics/backtest-summary` → metrics + validation
- `/health` → service status
- `/metrics` → observability table
- `/contracts` → contract/version diagnostics

### Phase B (Optional)

- API Explorer:
  - endpoint selector
  - grouped tabs
  - raw JSON viewer (no transformation)

### Endpoint Coverage Matrix (MANDATORY)

Maintain a coverage table in the UI repo to prove endpoint utilization.

| Endpoint Group | Coverage Mode | Status | Notes |
|---|---|---|---|
| Health | Core panel | Required | `/health` |
| Observability | Core panel | Required | `/metrics`, `/contracts` |
| Analytics | Core panels | Required | signal-summary, bluechip-ranking, opportunities, backtest-summary |
| Market | API explorer | Required | `/market/*` |
| Company/Security | API explorer | Required | `/companies*`, `/securities` |
| Trading | API explorer | Required | `/trading/*` |
| News | API explorer | Required | `/news/*` |
| Other | API explorer | Required | `/other/*` |
| Mappings | API explorer | Required | `/mappings/*` |

Completion rule:
- Every documented API endpoint must be represented in either a core panel or the API explorer.

### Enforcement Rules

- UI must NOT display fields not present in API response
- Field names must match API exactly
- No transformation beyond formatting

### Query Parameter Contract (MANDATORY)

Apply backend constraints directly to Streamlit controls:

| Endpoint | Parameter | Constraint |
|---|---|---|
| `/analytics/bluechip-ranking` | `top_n` | int, 1 to 200 |
| `/analytics/opportunities` | `top_n` | int, 1 to 200 |
| `/analytics/signal-summary` | `top_n` | int, 1 to 200 |
| `/analytics/backtest-summary` | `top_n` | int, 1 to 200 |
| `/analytics/backtest-summary` | `lookback_days` | int, 1 to 2000 |
| `/analytics/backtest-summary` | `rebalance` | enum: `static`, `weekly`, `monthly` |
| analytics endpoints | `sector_relative` | bool |

Rule:
- UI controls must block values outside contract constraints before request dispatch.

---

## 3) API Integration and Data Handling

### Requirements

- Centralized API client module REQUIRED
- One function per endpoint group

### Implementation Rules

1. Use HTTP GET only
2. Use timeout for all requests
3. Implement retry with backoff
4. Validate response structure:
   - required top-level keys
5. Handle optional fields safely
6. Implement caching:
   - short TTL OR manual refresh
7. Display:
   - execution_id
   - timestamps (if available)

### Version Negotiation and Correlation (MANDATORY)

1. On app startup, call `/contracts` and display negotiated version metadata.
2. Add a UI version selector for `X-API-Version` with values `v1` and `v2`.
3. Validate unknown version fallback behavior during smoke checks.
4. Capture and display response headers:
   - `X-Request-Id`
   - `X-API-Contract-Version`
   - `X-API-Supported-Versions`
5. For analytics panels, display `execution_id` and correlate with `/metrics` fields:
   - `execution_trace_counts`
   - `last_execution_id_by_endpoint`

### Schema Compatibility Rules

- Treat additive fields as non-breaking.
- Fail only when required top-level fields are missing.
- Render unknown extra keys in a raw JSON expander, not in computed columns.

### Refresh and Cache UX Rules

- Show last fetch timestamp per panel.
- Provide explicit manual refresh action per panel.
- Surface `/metrics.cache_stats` in Observability panel.
- Use short UI cache TTL and avoid hidden background refresh.

### Error Handling (MANDATORY)

- Never fail silently
- Always display:
  - endpoint
  - status code
  - error message
- Include `request_id` when available.
- Provide retry option

### Timeout Handling Rules

- When timeout-style errors occur, show a dedicated timeout state.
- Keep endpoint + request_id visible in timeout state.
- Provide safe retry without mutating filters/inputs.

---

## 4) UI Design Principles and Components

### Layout

- Header:
  - app title
  - health status
  - last refresh timestamp
- Tabs:
  - Signals
  - Rankings
  - Backtest
  - Metrics (optional)

### Table Rules

- Use API fields only
- Enable client-side sorting/filtering
- No computed columns

### Metrics Rules

- Use `st.metric`
- Formatting allowed:
  - percentage
  - decimal rounding
- No derived metrics

### Chart Rules

- Only plot fields from API
- No indicator computation

### Standard UI States

- Loading
- Empty
- Error
- Contract mismatch warning

---

## 5) Code Structure (MANDATORY)

Project structure:

```
ui/
   app.py
   api_client.py
   components/
      signals.py
      rankings.py
      backtest.py
      metrics.py
   utils/
      formatting.py
      error_handling.py

```

### Code Quality Rules

- Use type hints
- Use docstrings
- Keep functions small and focused
- Avoid duplication
- Use environment variables for config

---

## 6) Testing and Deployment

### Testing Requirements

1. Unit Tests:
   - API client
   - error handling
   - response validation

2. Contract Smoke Tests:
   - /analytics/signal-summary
   - /analytics/bluechip-ranking
   - /analytics/opportunities
   - /analytics/backtest-summary
   - /health
   - /metrics
   - /contracts

3. UI Smoke Tests:
   - panel rendering
   - empty state
   - error state

### CI Requirements

- lint
- tests
- contract checks

### Contract Drift Check (MANDATORY)

- Add CI step to compare UI endpoint/parameter matrix with runtime OpenAPI/contract output.
- Build must fail if:
   - endpoint used by UI is missing from API
   - required query parameter constraints drift
   - required top-level response fields for core panels are removed/renamed

### Deployment

- containerized (Docker)
- API base URL via environment variable
- environment promotion:
  - dev → staging → prod

---

## 7) Performance and Reliability Constraints

- Cached response latency: < 1.5s
- Uncached latency: < 4s
- API success rate: >= 99% (healthy backend)
- UI must remain responsive under expected dataset size

### UI Logging Guardrails

- Log only endpoint, request_id, status, duration, and version metadata.
- Do not log secrets or full response payloads by default.
- Allow verbose payload logging only in explicit local debug mode.

---

## Final Execution Sequence

1. Build endpoint mapping matrix
2. Implement Streamlit shell (tabs + layout)
3. Implement API client (timeout, retry, cache)
4. Implement panel components
5. Add error handling and UI states
6. Add tests and CI
7. Deploy containerized app

---

## Definition of Done

Implementation is complete only if:

- All panels render correctly
- All API calls match contract
- API contract version behavior validated for `X-API-Version: v1` and `X-API-Version: v2` on core endpoints
- Unknown version header fallback behavior validated against documented contract policy
- Response headers are captured and visible for diagnostics (`X-Request-Id`, `X-API-Contract-Version`, `X-API-Supported-Versions`)
- Analytics execution_id correlation validated against `/metrics` traces
- No business logic exists in UI
- Errors are handled and visible
- Code is modular and maintainable
- Tests pass
- App runs with `streamlit run app.py`

---

## Future Enhancements (Controlled)

- Add new panels ONLY if backed by API contracts
- Keep all additions read-only
- Avoid introducing UI-side computation
- Consider migration to more scalable UI framework if complexity grows

---

