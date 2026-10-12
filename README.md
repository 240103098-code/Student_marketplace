# Student Marketplace

A planned university-only marketplace where verified students list items and contact sellers externally.

The Python scaffold and typed environment configuration are ready; marketplace features and runtime services remain planned. Python 3.11 or newer is supported (verified with Python 3.13.15). Create a virtual environment with `python -m venv .venv`, install the pinned configuration dependencies with `.venv/Scripts/python.exe -m pip install -r requirements.lock`, and run `.venv/Scripts/python.exe -m unittest discover -s tests -v` from the repository root on Windows. See the setup guide for other platforms and configuration details.

## Project documents

- [MVP requirements](_docs/plan.md)
- [40-task backlog](_docs/tasks.md)
- [Development process](_docs/process.md)
- [Local setup and current status](_docs/local-setup.md)

## Planned stack

React, FastAPI, PostgreSQL, SQLAlchemy, and Alembic, with JWT authentication and university-email verification through configured email delivery.

## Project tracking

Use [GitHub Issues](https://github.com/240103098-code/Student_marketplace/issues) in [this repository](https://github.com/240103098-code/Student_marketplace). Follow the documented process one issue at a time. Service startup commands will be documented when their corresponding tasks are implemented.
