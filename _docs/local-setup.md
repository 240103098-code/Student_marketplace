# Local development setup

This document describes the tools, project layout, and local startup workflow for Student Marketplace. **Current status:** the repository contains planning documents only. Backend and frontend apps, dependency manifests, tests, and database integrations are not yet committed. Do not treat commands for those components as runnable until their linked issues are implemented.

## Prerequisites

Install the following development tools:

| Tool | Why it is needed | Status |
| --- | --- | --- |
| Git | Clone the repository and commit changes | Needed now |
| Python and [uv](https://docs.astral.sh/uv/getting-started/installation/) | Backend environment and pytest, as required by `AGENTS.md` | Needed once [#1](https://github.com/240103098-code/student-marketplace/issues/1) sets up the Python project |
| Node.js and npm | React frontend development | Needed once [#5](https://github.com/240103098-code/student-marketplace/issues/5) creates the app |
| PostgreSQL | Local database server; `psql` or pgAdmin can be used to inspect it | Needed once [#8](https://github.com/240103098-code/student-marketplace/issues/8) adds database integration |

**Versions:** No Python, Node.js, or PostgreSQL version ranges have been selected or pinned in this repository. Check compatibility against the project's dependency files when they are introduced; do not assume a specific version is officially supported today.

On Windows PowerShell (or a compatible terminal), check the tools you have:

```powershell
git --version
python --version
uv --version
node --version
npm --version
psql --version
```

On Windows, `py --version` may work when `python --version` does not. The `psql` command may not be on your PATH even when PostgreSQL and pgAdmin are installed.

## Clone and inspect the repository

```bash
git clone https://github.com/240103098-code/student-marketplace.git
cd student-marketplace
git status
```

This is the **current** repository layout:

```text
student-marketplace/
├── AGENTS.md
├── README.md
└── _docs/
    ├── plan.md
    ├── process.md
    ├── tasks.md
    ├── testing-guidelines.md
    ├── design-system.md
    ├── api.md
    └── team/
```

The intended application directories are `backend/` and `frontend/` in the repository root. **Neither directory exists yet on the current remote branch.** The Python project/test scaffolding is tracked in [#1](https://github.com/240103098-code/student-marketplace/issues/1), the FastAPI app in [#3](https://github.com/240103098-code/student-marketplace/issues/3), and the React app in [#5](https://github.com/240103098-code/student-marketplace/issues/5). Refer to the corresponding issue for the final module paths and scripts.

## Python dependencies and tests (after issue #1)

The repository's `AGENTS.md` establishes `uv` and `pytest` as the intended backend workflow. **These commands are not runnable yet** because `pyproject.toml` and the test suite do not exist on the remote branch.

After issue #1 supplies them, run from the repository root:

```bash
uv sync
uv run pytest
```

To run the example single-file test referenced in `AGENTS.md`, use `uv run pytest tests/test_home.py` **only once that test file exists**. Avoid installing unapproved dependencies; `AGENTS.md` requires asking before adding any dependency to `pyproject.toml`.

## Backend service (after issue #3)

**Not implemented yet:** there is no FastAPI entry point to start. Once issue #3 adds the app, install Python dependencies using `uv sync`, then use the exact Uvicorn command documented by that implementation.

For reference, a typical FastAPI invocation is:

```text
uv run uvicorn <python.module.path>:app --reload
```

This line is a **template, not a currently executable command**. Replace `<python.module.path>` with the actual module created under issue #3; do not guess the import path. Backend database connectivity is a separate task in [#8](https://github.com/240103098-code/student-marketplace/issues/8).

## Frontend service (after issue #5)

**Not implemented yet:** there is no `frontend/package.json` or React development server. Once issue #5 creates the app, the expected npm workflow from `frontend/` is:

```bash
cd frontend
npm install
npm run dev
npm run build
```

Use the actual package scripts committed by issue #5 if they differ. Frontend test setup is tracked separately in [#6](https://github.com/240103098-code/student-marketplace/issues/6); do not claim that an `npm test` command exists before it is added.

## PostgreSQL (after issue #8)

Install PostgreSQL and start its local server using your operating system's service manager or your existing PostgreSQL installation. The default local port is typically `5432`; your installation may use a different port.

If the command-line tools are available, you can check connectivity with:

```bash
pg_isready -h localhost -p 5432
```

**Not configured yet:** the project does not currently have a database engine, database name, user, or migrations. Issue #8 will specify the application connection, and issue #9 will establish Alembic migrations. Do not run migration commands until those issues provide them.

## Environment variables and local secrets (after issue #7)

**Not implemented yet:** there is no supported `.env` contract or `.env.example` in the current repository. [Issue #7](https://github.com/240103098-code/student-marketplace/issues/7) will define typed settings and the canonical sample file. The following are *illustrative categories of future settings*, **not confirmed application variable names**:

```dotenv
DATABASE_URL=postgresql+psycopg://DB_USER:DB_PASSWORD@localhost:5432/DB_NAME
UNIVERSITY_EMAIL_DOMAIN=example.edu
SMTP_HOST=SMTP_HOST_HERE
SMTP_USERNAME=SMTP_USERNAME_HERE
SMTP_PASSWORD=SMTP_PASSWORD_HERE
JWT_SECRET_KEY=GENERATE_A_PRIVATE_SECRET
FRONTEND_ORIGIN=http://localhost:5173
UPLOAD_DIR=uploads
```

Use the actual names and formats established in issue #7 when it is implemented. Keep real passwords, SMTP credentials, JWT secrets, and local `.env` files **out of Git**. The university domain, SMTP provider, token configuration, and other values may still need product decisions; see [`_docs/plan.md`](plan.md).

## Development workflow

1. Read [`AGENTS.md`](../AGENTS.md) and [`_docs/process.md`](process.md).
2. Work on one [GitHub issue](https://github.com/240103098-code/student-marketplace/issues) at a time; review its acceptance criteria before coding and before review.
3. Use the testing/design/API documents only for related tasks. Commit related changes regularly; do not commit secrets.
4. When a new service or command is implemented, update this guide with the **real tested command**.

The complete three-service local demo (including real SMTP configuration and a walkthrough) is deferred to [#103](https://github.com/240103098-code/student-marketplace/issues/103).
