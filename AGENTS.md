Commands

- Python 3.11 or newer is supported; the bootstrap has no third-party dependencies or installation step.
- `python -m unittest discover -s tests -v` - run the single bootstrap smoke test from the repository root (verified with Python 3.13.15).
- No backend or frontend service startup commands are available yet.

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
