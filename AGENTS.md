Commands

- Python 3.11 or newer is supported (verified with Python 3.13.15). Run these commands from the repository root on Windows; use `.venv/bin/python` on other platforms.
- `python -m venv .venv` - create the isolated Python environment.
- `.venv/Scripts/python.exe -m pip install -r requirements.lock` - install the pinned Python dependencies.
- `.venv/Scripts/python.exe -m unittest discover -s tests -v` - run service-free tests; real PostgreSQL tests are opt-in using the dedicated database contract in `_docs/local-setup.md`.
- `.venv/Scripts/python.exe -m backend.database check` - explicitly check configured PostgreSQL connectivity.
- `.venv/Scripts/python.exe -m alembic upgrade head` / `downgrade base` - apply/revert migrations. Current head creates account/code/refresh and category/listing/photo/report tables; use downgrades only on disposable data.
- From `frontend`, `npm ci`, `npm run test -- --run`, and `npm run build` install/test/build the React preview shell; `npm run dev` serves it at http://127.0.0.1:5173/ (Ctrl+C to stop).
- Frontend verification uses Node 24.19.0 and npm 12.2.0; see `_docs/local-setup.md` for supported versions and workspace-local npm.
- `.venv/Scripts/python.exe -m uvicorn backend.main:create_runtime_app --factory --host 127.0.0.1 --port 8000` - start the configured backend; stop with Ctrl+C. Apply migrations first.

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
