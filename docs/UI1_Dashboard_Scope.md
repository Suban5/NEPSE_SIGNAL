# UI1: Minimal Dashboard Scope Definition

Goal:
Define a production-ready, minimal, read-only dashboard scope based strictly on existing backend capabilities and frozen API contracts.

---

## Instructions

### 1. Source Alignment (STRICT)
- Use ONLY:
  - Execution-Plan.md (UI1 tasks)
  - api-contracts.md (frozen endpoints)
  - existing backend modules (analysis, ranking, signals, backtesting)
- Do NOT invent new endpoints, fields, or features
- Do NOT assume functionality not present in code

---

### 2. Output Structure (MUST FOLLOW EXACTLY)

Generate the document with the following sections in order:

1. Metadata
2. Overview
3. Dashboard Panels
   - Panel 1: Top Trade Signals
   - Panel 2: Blue-Chip Rankings
   - Panel 3: Portfolio Backtest Summary
   - Panel 4: Workflow Observability (optional)
4. Dashboard Layout and Navigation
5. Data Refresh Strategy
6. Scope Boundaries (What’s NOT Included)
7. Business Logic Audit (table format REQUIRED)
8. UI1 Task Progress (table format REQUIRED)
9. Next Steps
10. References

---

### 3. Panel Definition Requirements

For EACH panel include:

- Purpose
- Data Source (exact API endpoint + query params)
- Rendering Requirements
- Key Fields from API (explicit field names)
- Constraints (STRICT: no UI-side computation)
- User Interactions (client-side only unless API call required)

---

### 4. Critical Constraints (NON-NEGOTIABLE)

- UI must be strictly READ-ONLY
- NO business logic in UI:
  - no scoring
  - no ranking
  - no signal generation
  - no backtest computation
- UI only:
  - displays API responses
  - sorts/filter responses client-side
- Do NOT introduce:
  - real-time features
  - streaming
  - new data sources
  - user state persistence

---

### 5. Business Logic Audit (STRICT FORMAT)

Include a table:

| Backend Component | Logic | UI Role | Duplication? |

Rules:
- Map real backend modules only
- Explicitly confirm "❌ None" for duplication
- Do NOT leave ambiguous statements

---

### 6. Task Progress Table (STRICT)

Use:

| Task | Status | Details |

Rules:
- Status must be one of:
  - Completed
  - In Progress
  - Not Started
- Align with Execution-Plan.md UI1 tasks
- Do NOT invent tasks

---

### 7. Writing Style

- Be precise and technical (no fluff)
- Avoid vague terms like "may", "could", "should"
- Use bullet points and structured sections
- Keep content concise but complete
- Ensure consistency across all panels

---

### 8. Validation Requirements

Before finalizing:
- Ensure all panels map to real API endpoints
- Ensure no duplication of backend logic
- Ensure all constraints are enforced consistently
- Ensure document can be used directly for implementation

---

### Goal

Produce a clean, structured, implementation-ready scope definition that:
- prevents UI/backend logic leakage
- aligns strictly with backend contracts
- is suitable for engineering execution without reinterpretation

If a required detail is not explicitly present in the source files, do NOT guess.
Instead, omit it or mark it as "Not Available in API Contract".