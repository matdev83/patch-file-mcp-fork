# Repository Guidelines

## Project Structure & Module Organization
- `src/patch_file_mcp/`: Python package and server entrypoint (`server.py`).
- `tests/`: Pytest suite with unit/integration coverage; markers `unit`, `integration`, `slow`.
- `pyproject.toml`: Packaging, pytest config, and console script (`patch-file-mcp`).
- `mcp_config*.json`: Example/config files for MCP clients.
- Generated: `logs/` (runtime logs), `htmlcov/` (coverage HTML), `.coverage`.

## Build, Test, and Development Commands
- Install (editable + tests):
  - Windows PowerShell
    - `python -m venv .venv; .venv\Scripts\Activate.ps1`
    - `pip install -e .[test]`
- Run tests
  - Quick: `pytest`
  - With coverage HTML: `pytest --cov=src/patch_file_mcp --cov-report=html:htmlcov`
  - Helper: `python run_tests.py`
- Run server locally
  - Example: `patch-file-mcp --allowed-dir C:\path\to\repo --log-file logs/app.log --log-level INFO`
  - Alt (module): `python -m patch_file_mcp.server --allowed-dir .`
- Lint/format/type-check (run in project venv)
  - `ruff check --fix .`
  - `black .`
  - `mypy src/patch_file_mcp`

## Coding Style & Naming Conventions
- Python ≥ 3.10, 4-space indentation, type hints required on new/changed code.
- Format with Black; lint with Ruff; keep lint clean before PRs.
- Naming: modules/files `snake_case.py`, functions/vars `snake_case`, classes `CapWords`.
- Tests: files `tests/test_*.py`; fixtures in `tests/conftest.py`.

## Testing Guidelines
- Framework: Pytest; default options set in `pyproject.toml` (verbose, strict markers).
- Coverage: enforced minimum 25% (`--cov` on `src/patch_file_mcp`; HTML in `htmlcov/`).
- Selection: `pytest -m unit`, `pytest tests/test_venv_detection.py::TestClass::test_case`.
- Add tests for new behavior; update existing tests when interfaces change.

## Commit & Pull Request Guidelines
- Commits: imperative, concise summary (≤72 chars) + rationale (what/why). Examples: "Add validation for patch block integrity", "Refactor search/replace parsing".
- PRs: clear description, link issues (`#123`), list changes, test results, and any config/logging impacts. Include tests and doc updates.

## Security & Configuration Tips
- Always run as a regular user; do not start the server as Administrator/root.
- Required: `--allowed-dir` restricts file operations; use project root or a specific workspace.
- Logs default to `logs/app.log`; redact secrets in examples and PRs.
- If no project venv is detected, QA (Ruff/Black/MyPy) is skipped—run the tools manually before merging.

