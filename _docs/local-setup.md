# Local development setup

## Current status

The empty Python bootstrap from [task 1](https://github.com/240103098-code/Student_marketplace/issues/1) is ready, with an importable backend package and one automated smoke test. No backend or frontend service, database integration, or marketplace feature exists yet.

## Current layout

- `pyproject.toml`: Python 3.11+ project metadata with no third-party dependencies.
- `backend/__init__.py`: empty importable project package.
- `tests/test_bootstrap.py`: one package import and path smoke test.
- `README.md`: project overview and links.
- `AGENTS.md`: contribution rules and document references.
- `_docs/plan.md`: MVP requirements and unresolved product choices.
- `_docs/tasks.md`: the new 40-task backlog.
- `_docs/process.md` and `_docs/team/`: development roles and workflow.
- `_docs/api.md`, `_docs/design-system.md`, and `_docs/testing-guidelines.md`: guidance for related implementation tasks.
- `_docs/backlog-history.md`: preserved historical documentation.

## Getting started

Clone [Student_marketplace](https://github.com/240103098-code/Student_marketplace) using Git, open the repository directory, and check its working changes before editing. Read [AGENTS.md](../AGENTS.md), [the process](process.md), and the selected [GitHub issue](https://github.com/240103098-code/Student_marketplace/issues). Review its acceptance criteria before implementation and before review.

Git is sufficient to inspect the documents. To run the bootstrap test, use Python 3.11 or newer; no dependency installation, external service, or secrets are required. From the repository root, run `python -m unittest discover -s tests -v`; it collects exactly one passing test (verified with Python 3.13.15). The future application uses React, FastAPI, PostgreSQL, SQLAlchemy, Alembic, and JWT authentication. Additional dependency tooling, Node.js, npm, and PostgreSQL versions and installation requirements will be documented when the relevant implementation tasks establish them.

## Setup tasks

- [Task 1](https://github.com/240103098-code/Student_marketplace/issues/1) establishes the empty project and first automated test.
- [Task 3](https://github.com/240103098-code/Student_marketplace/issues/3) defines environment-based configuration and the example configuration file.
- [Task 4](https://github.com/240103098-code/Student_marketplace/issues/4) connects PostgreSQL and introduces migrations.
- [Task 5](https://github.com/240103098-code/Student_marketplace/issues/5) creates the React application shell and a component test.
- [Task 8](https://github.com/240103098-code/Student_marketplace/issues/8) configures real verification-email delivery.
- [Task 40](https://github.com/240103098-code/Student_marketplace/issues/40) verifies and documents the complete local MVP demonstration.

Service startup, dependency installation, and migration commands are not available yet. Add actual tested commands to this guide as each task is implemented. Keep passwords, email-provider credentials, JWT secrets, and local environment files out of Git; configuration names and values will be established in task 3 and the decisions recorded in task 2.
