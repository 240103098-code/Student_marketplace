# Student Marketplace

A planned university-only marketplace where verified students list items and contact sellers externally.

The Python scaffold, typed configuration, PostgreSQL connection/session helpers, empty Alembic baseline, and React preview shell are ready. Authentication and marketplace features remain planned. Python 3.11 or newer is supported (verified with Python 3.13.15). Create a virtual environment with `python -m venv .venv`, install pinned dependencies with `.venv/Scripts/python.exe -m pip install -r requirements.lock`, and run `.venv/Scripts/python.exe -m unittest discover -s tests -v` from the repository root on Windows. Real PostgreSQL tests require an explicitly confirmed disposable database; see the setup guide for preparation, migrations, and other platforms.

For the frontend, use Node 24.15.0+ on the 24.x line (verified with 24.19.0) or another manifest-supported version, and npm 12.2.0+. From `frontend`, run `npm ci`, `npm run test -- --run`, `npm run build`, and `npm run dev`. Open `http://127.0.0.1:5173/`; stop with Ctrl+C. This is a placeholder-only preview with no backend requests, account forms, authentication, or listing data. The setup guide includes the workspace-local npm option used for verification.

## Project documents

- [MVP requirements](_docs/plan.md)
- [40-task backlog](_docs/tasks.md)
- [Development process](_docs/process.md)
- [Local setup and current status](_docs/local-setup.md)

## Planned stack

React, FastAPI, PostgreSQL, SQLAlchemy, and Alembic, with JWT authentication and university-email verification through configured email delivery.

## Project tracking

Use [GitHub Issues](https://github.com/240103098-code/Student_marketplace/issues) in [this repository](https://github.com/240103098-code/Student_marketplace). Follow the documented process one issue at a time. Backend service startup commands will be documented when their corresponding tasks are implemented.
