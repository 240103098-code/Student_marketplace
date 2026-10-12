Commands

- Python 3.11 or newer is supported (verified with Python 3.13.15). Run these commands from the repository root on Windows; use `.venv/bin/python` on other platforms.
- `python -m venv .venv` - create the isolated Python environment.
- `.venv/Scripts/python.exe -m pip install -r requirements.lock` - install the pinned configuration dependencies.
- `.venv/Scripts/python.exe -m unittest discover -s tests -v` - run bootstrap and configuration tests without external services or secrets.
- No backend or frontend service startup commands are available yet.

Rules

- Use the minimal dependencies needed to implement approved backlog issues.
  Add Python dependencies in `pyproject.toml` and frontend dependencies in
  `frontend/package.json`; keep the corresponding lockfiles updated. The Python
  pip workflow uses `requirements.lock` as its pinned resolved dependency export.
- The user grants standing approval to add and install dependencies needed for
  those issues. Document dependency changes in the implementation report.

## Documents

- Read `_docs/process.md` before starting work.
- Before writing tests, read `_docs/testing-guidelines.md`.
- For anything touching the UI, read `_docs/design-system.md`.
- Before working on APIs, read `_docs/api.md`.
