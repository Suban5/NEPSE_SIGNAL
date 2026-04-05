Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: .github/copilot-instructions.md
Validation Method: Code + Tests

# Repository Standards

- Use environment variables from `.env` via `python-dotenv`.
- Always use a local `.venv` virtual environment for Python setup and package installation.
- Keep API/data/analysis/ranking/visualization/cli responsibilities separated.
- Use type hints and Google style docstrings.
- Use logging instead of `print()`.
- Add tests for business logic under `tests/`.

## AI Coding Guardrails

When generating code in this repository always:

1. Prefer readability over cleverness.
2. Avoid generating placeholder implementations.
3. Generate fully working implementations whenever possible.
4. Avoid TODO comments unless explicitly requested.
5. Ensure imports are correct and minimal.
6. Ensure code runs without syntax errors.
7. Follow repository folder structure strictly.
8. Add docstrings and type hints automatically.
9. Validate external API responses.
10. Ensure generated code is testable.

## AI Principles

Generated code must:

- be deterministic
- be testable
- follow single responsibility principle
- avoid hidden side effects
- avoid global mutable state
