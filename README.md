# Student Marketplace

A university-only marketplace for verified students to buy and sell items.

## Planned stack

- Backend: Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic
- Frontend: React
- Email verification: SMTP or configured email provider
- Development: local deployment

## Local setup

Read [the local development setup guide](_docs/local-setup.md) for prerequisites, command examples, the current project layout, and the status of services that are not implemented yet.

## Project tracking

See [GitHub Issues](https://github.com/240103098-code/student-marketplace/issues) for the development backlog.

The project bootstrap is ready: install Python 3.11 or newer and uv, then run
`uv sync` and `uv run pytest` from the repository root. The initial suite contains
one smoke test; backend and frontend application features are still planned.
