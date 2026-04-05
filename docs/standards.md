# Documentation Standards

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: docs/standards.md
Validation Method: Code + Tests

## Required Metadata Block

Every maintained documentation file must include:

Metadata:
Owner: <team or person>
Last Reviewed: <YYYY-MM-DD>
Source of Truth: <module paths>
Validation Method: Code + Tests

## Definition of Done

A documentation change is complete only when:

- examples match actual function signatures
- referenced files and endpoints exist
- unsupported parameters or deprecated APIs are removed
- behavior statements are traceable to code and tests
- terminology is normalized to Relevant, Outdated, Obsolete

## Update Rules

- Prefer canonical docs over duplicated narrative
- Prefer concise validated examples over speculative guidance
- If a document is stale beyond repair, delete or mark deprecated
- Keep API contracts aligned with OpenAPI and route tests

## Governance

- Owner must be assigned (TODO is temporary)
- Last Reviewed must be updated in every doc-impacting PR
- Source of Truth modules must be listed

## Automation Hooks (Recommended)

- Compare documented function signatures against runtime stubs
- Generate API references from OpenAPI schema
- Flag docs with stale Last Reviewed dates
- Add CI check for missing metadata block
