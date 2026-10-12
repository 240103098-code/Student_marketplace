Commands

- `uv sync` - install dependencies
- `uv run python -m pytest` - the whole suite
- `uv run python -m pytest tests/test_home.py` - one test file

Rules

- Use the minimal dependencies needed to implement approved backlog issues.
  Add Python dependencies in `pyproject.toml` and frontend dependencies in
  `frontend/package.json`; keep the corresponding lockfiles updated.
- The user grants standing approval to add and install dependencies needed for
  those issues. Document dependency changes in the implementation report.

## Documents

- Read `_docs/process.md` before starting work.
- Before writing tests, read `_docs/testing-guidelines.md`.
- For anything touching the UI, read `_docs/design-system.md`.
- Before working on APIs, read `_docs/api.md`.
