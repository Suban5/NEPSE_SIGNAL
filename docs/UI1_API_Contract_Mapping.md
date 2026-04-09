# UI1-T2 & UI1-T3: Dashboard Scope Validation and API Endpoint Mapping

Goal:
Validate that the UI1 dashboard does NOT duplicate backend logic and define the exact minimum API surface required for implementation.

---

## Instructions

### 1. Source Alignment (STRICT)
- Use ONLY:
  - UI1_Dashboard_Scope.md
  - Execution-Plan.md (UI1 tasks)
  - api-contracts.md (frozen endpoints)
  - backend modules (signals, ranking, bluechip, backtesting, api)
- Do NOT invent:
  - endpoints
  - fields
  - backend logic
- Do NOT assume missing functionality

---

### 2. Output Structure (MUST FOLLOW EXACTLY)

Generate sections in this exact order:

1. Header (Title, Date, Status)
2. UI1-T2: Confirm Dashboard Scope Avoids Backend Duplication
   - Audit Methodology
   - Audit Results (per panel)
   - Conclusion
3. UI1-T3: Identify Minimum API Surface Needed by UI
   - Panel-wise endpoint mapping
   - Health endpoint
4. Frozen Contract Summary
5. Validation Method (Smoke Check)
6. UI1 Implementation Readiness

---

### 3. Audit Section Requirements (UI1-T2)

For EACH panel:

- Panel Name
- Backend Module(s) (REAL modules only)
- Backend Logic (specific, not generic)
- UI Role (display-only behavior)
- Duplication Status (must explicitly state one of):
  - ✅ None
  - ⚠️ Partial (must explain)
  - ❌ Exists (must explain)

Rules:
- UI must NEVER contain:
  - scoring logic
  - ranking logic
  - signal generation
  - backtest computation
- If any duplication is detected → explicitly describe it

---

### 4. API Mapping Requirements (UI1-T3)

For EACH panel include:

- Endpoint (exact path)
- Query Parameters (name, type, constraints)
- Minimum Required Response Fields (JSON example REQUIRED)
- Optional Fields (clearly marked)

Rules:
- JSON must reflect actual API contract
- Do NOT include fields not present in backend responses
- Maintain consistent field naming

---

### 5. Frozen Contract Section (STRICT)

Must include:

- List of all endpoints used by UI
- Stability guarantees:
  - no field removal
  - no renaming
  - no type changes
- Allowed changes:
  - additive fields only

- Breaking change policy:
  - explicitly defined
  - aligned with UI1 milestone constraints

---

### 6. Validation Section

Include:

- curl-based smoke tests for ALL endpoints:
  - signal-summary
  - bluechip-ranking
  - backtest-summary
  - health
  - metrics

Rules:
- Use realistic query params
- Ensure commands are runnable
- No placeholders

---

### 7. Writing Constraints

- Be precise and technical
- Avoid vague language ("may", "could", "should")
- Use structured formatting (headers, bullets, code blocks)
- Keep content concise but complete
- Ensure consistency across all panels

---

### 8. Critical Constraints (NON-NEGOTIABLE)

- UI is strictly READ-ONLY
- NO business logic in UI
- NO derived metrics in UI
- NO recomputation of backend outputs
- UI only:
  - displays API responses
  - sorts/filters client-side

---

### 9. Validation Before Output

Before finalizing:

- Verify all endpoints exist
- Verify all fields match API contracts
- Verify zero backend logic duplication
- Ensure document is implementation-ready

---

### Goal

Produce a strict, implementation-ready validation and API mapping document that:
- guarantees zero UI/backend logic duplication
- defines a stable API contract for UI1
- eliminates ambiguity for frontend implementation


If any field, endpoint, or module is not explicitly found in the source files, do NOT include it.
Do NOT guess. Omit instead.