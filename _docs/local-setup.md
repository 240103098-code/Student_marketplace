# Local development setup

## Current status

The Python bootstrap, typed configuration loader, PostgreSQL engine/session helpers, connection-check command, and empty Alembic baseline are ready, with automated tests. No FastAPI or frontend service, account/listing schema, email transport, or marketplace feature exists yet. Importing configuration/database helpers never starts services, connects, or creates tables.

## Current layout

- `pyproject.toml` and `requirements.lock`: Python 3.11+ metadata and pinned dependencies.
- `backend/__init__.py`: empty importable project package.
- `tests/test_bootstrap.py`: one package import and path smoke test.
- `backend/config.py` and `tests/test_config.py`: explicit settings loading and isolated configuration tests.
- `backend/database.py`, `alembic.ini`, and `migrations/`: PostgreSQL infrastructure and the empty baseline revision.
- `tests/test_database.py` and `tests/test_database_integration.py`: unit checks and opt-in actual PostgreSQL integration tests.
- `.env.example`: supported configuration names, formats, defaults, and placeholders.
- `README.md`: project overview and links.
- `AGENTS.md`: contribution rules and document references.
- `_docs/plan.md`: MVP requirements and unresolved product choices.
- `_docs/tasks.md`: the new 40-task backlog.
- `_docs/process.md` and `_docs/team/`: development roles and workflow.
- `_docs/api.md`, `_docs/design-system.md`, and `_docs/testing-guidelines.md`: guidance for related implementation tasks.
- `_docs/backlog-history.md`: preserved historical documentation.

## Getting started

Clone [Student_marketplace](https://github.com/240103098-code/Student_marketplace) using Git, open the repository directory, and check its working changes before editing. Read [AGENTS.md](../AGENTS.md), [the process](process.md), and the selected [GitHub issue](https://github.com/240103098-code/Student_marketplace/issues). Review its acceptance criteria before implementation and before review.

Use Python 3.11 or newer; the following PowerShell commands were tested with Python 3.13.15 from the repository root:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

On Linux or macOS, use `.venv/bin/python` instead of `.venv/Scripts/python.exe`. Activation is optional. The default run has eighteen service-free tests and skips the PostgreSQL integration class. Unit tests inject synthetic isolated settings and need no .env, real credentials, network, database, SMTP, or running service. Opt in to three actual PostgreSQL tests using the preparation below.

In a restricted Windows environment whose temporary directory is not writable, first create a workspace temporary directory and direct this terminal's TEMP and TMP to it before the commands above:

```powershell
New-Item -ItemType Directory -Force .venv/tmp | Out-Null
$env:TEMP = (Resolve-Path .venv/tmp).Path
$env:TMP = $env:TEMP
```

The pip workflow adds pydantic-settings 2.15.0 with its six resolved configuration dependencies, plus SQLAlchemy 2.1.4, Alembic 1.20.0, and psycopg[binary] 3.3.6. Database transitive additions are psycopg-binary 3.3.6, Mako 1.4.3, MarkupSafe 3.0.4, and tzdata 2026.5. All versions are pinned in `requirements.lock`; keep the manifest and export aligned when approved dependencies change. No FastAPI, email transport, JWT, or frontend libraries are installed yet.

The future application uses React, FastAPI, PostgreSQL, SQLAlchemy, Alembic, and JWT authentication. Node.js and npm installation requirements will be documented when the React task establishes them.

## Local configuration

Copy `.env.example` to an ignored `.env` and replace credential placeholders before explicitly loading runtime settings. Never commit real secrets. No usable JWT secret is provided or generated: missing, blank, placeholder, or shorter-than-32-character values are rejected. DATABASE_URL is also required and must be a PostgreSQL connection URL. Configuration loading validates the URL only; the separate connection-check command contacts PostgreSQL.

Call `backend.config.load_settings()` explicitly; importing the module does not load or validate settings. Environment variables override `.env` values, which override safe non-secret defaults. Both a relative .env filename and a relative UPLOAD_DIR resolve from the repository root, independent of the caller's working directory. Tests can pass `environ={...}, env_file=None` to ignore ambient settings and disable file loading. Errors name the invalid setting without printing its value; database credentials, JWT secrets, and SMTP credentials are redacted from settings representations.

The complete setting contract is documented beside each name in `.env.example`: APP_ENV, DATABASE_URL, UNIVERSITY_EMAIL_DOMAIN, FRONTEND_ORIGINS, JWT_SECRET_KEY, JWT_ACCESS_MINUTES, REFRESH_SESSION_DAYS, UPLOAD_DIR, REFRESH_COOKIE_SECURE, REFRESH_COOKIE_HTTPONLY, REFRESH_COOKIE_SAMESITE, SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL, and SMTP_SECURITY. FRONTEND_ORIGINS is a JSON array of explicit origins without paths; wildcard origins are rejected. The university domain is exactly sdu.edu.kz.

Production requires HTTPS frontend origins and a Secure refresh cookie (automatically true if omitted in production). Development/test allow HTTP loopback origins and a non-Secure cookie; HttpOnly and SameSite=lax are mandatory in every mode. This task validates settings; cookie, CORS, and CSRF enforcement remain future application work.

SMTP is optional during early setup. Before enabling email delivery, call `settings.validate_email_delivery()` to require host, port, username, password, and sender together. SMTP_SECURITY is starttls by default or tls; select the server's actual mode and port. This check never connects or sends mail. Real SMTP credentials and a live mail account remain external operator setup, and transport is deferred to task 8.

## Setup tasks

- [Task 1](https://github.com/240103098-code/Student_marketplace/issues/1) establishes the empty project and first automated test.
- [Task 3](https://github.com/240103098-code/Student_marketplace/issues/3) defines environment-based configuration and the example configuration file.
- [Task 4](https://github.com/240103098-code/Student_marketplace/issues/4) connects PostgreSQL and introduces migrations.
- [Task 5](https://github.com/240103098-code/Student_marketplace/issues/5) creates the React application shell and a component test.
- [Task 8](https://github.com/240103098-code/Student_marketplace/issues/8) configures real verification-email delivery.
- [Task 40](https://github.com/240103098-code/Student_marketplace/issues/40) verifies and documents the complete local MVP demonstration.

Application service startup commands are not available yet. Keep passwords, SMTP credentials, JWT secrets, local .env files, uploads, and credential files out of Git. The configuration contract is implemented above; the decision baseline is recorded in [the plan](plan.md).

## PostgreSQL connection and migrations

Configure DATABASE_URL for a PostgreSQL database that you control, using `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE` (plain `postgresql://` also selects psycopg). Explicit database construction creates a lazy engine and session factory; importing the module never loads settings or connects. Connections have a three-second driver timeout and a five-second statement timeout. Session contexts commit on success, roll back on failure, and always close; the owner explicitly disposes the engine.

From the repository root, with runtime settings configured, these tested commands perform the connection check and empty baseline migration:

```powershell
.venv/Scripts/python.exe -m backend.database check
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic current
.venv/Scripts/python.exe -m alembic downgrade base
.venv/Scripts/python.exe -m alembic upgrade head
```

The check returns a nonzero exit code and a sanitized message on connection failure. Alembic reads the same explicit settings contract; `alembic.ini` contains no URL or credentials. Baseline `0001_baseline` only tracks the revision in `alembic_version`; it creates no application tables.

## Dedicated PostgreSQL integration tests

Tests never reuse DATABASE_URL as their target. Prepare a separate empty database named `student_marketplace_test_<suffix>` on loopback and explicitly set TEST_DATABASE_URL plus TEST_DATABASE_CONFIRM equal to that exact database name. Tests reject non-loopback hosts, unconfirmed names, and databases containing application tables. They do not drop/reset arbitrary databases; temporary transaction probes are cleaned up and baseline downgrade is applied afterward.

Verification used PostgreSQL **18.6**, from [EDB's official binary archive page](https://www.enterprisedb.com/download-postgresql-binaries), which is [linked by PostgreSQL's Windows download page](https://www.postgresql.org/download/windows/). Archive: [postgresql-18.6-5-windows-x64-binaries.zip](https://get.enterprisedb.com/postgresql/postgresql-18.6-5-windows-x64-binaries.zip). Binaries, data, and logs stayed in sibling `../pg-runtime`, outside this tracked repository. No installer, system service, or global configuration was changed.

After downloading/extracting the archive's `pgsql/bin`, `pgsql/lib`, and `pgsql/share` into that sibling runtime directory, initialization was:

```powershell
& ../pg-runtime/pgsql/bin/initdb.exe -D ../pg-runtime/data-issue4 -U issue4_admin -A trust --encoding=UTF8 --locale=C
```

This disposable test cluster uses trust authentication only on loopback; it has no real credentials and must not be exposed externally or used as an application deployment. Start it on the dedicated port **55434**, create the dedicated test database once, run tests, and stop in the same shell lifecycle. The tested database preparation used psycopg because the sandbox blocked createdb.exe:

```powershell
& ../pg-runtime/pgsql/bin/pg_ctl.exe -D ../pg-runtime/data-issue4 -l ../pg-runtime/issue4-postgresql.log -o '-h 127.0.0.1 -p 55434' -w -t 20 start
try {
    # Run this creation line once, after initializing a fresh disposable cluster.
    .venv/Scripts/python.exe -c "import psycopg; c=psycopg.connect('host=127.0.0.1 port=55434 user=issue4_admin dbname=postgres connect_timeout=3',autocommit=True); c.execute('CREATE DATABASE student_marketplace_test_issue4'); c.close()"
    $env:TEST_DATABASE_URL = 'postgresql+psycopg://issue4_admin@127.0.0.1:55434/student_marketplace_test_issue4'
    $env:TEST_DATABASE_CONFIRM = 'student_marketplace_test_issue4'
    .venv/Scripts/python.exe -m unittest discover -s tests -v
} finally {
    & ../pg-runtime/pgsql/bin/pg_ctl.exe -D ../pg-runtime/data-issue4 -w -t 15 stop
}
```

For a previously prepared dedicated cluster, omit only the CREATE DATABASE line. This environment required approved execution outside the networking sandbox for loopback clients and the single start/test/stop lifecycle. All **21 tests passed with no skips**, including actual PostgreSQL CLI success/unreachable failure, baseline upgrade/downgrade/second-upgrade, and real session commit/rollback cleanup. The temporary server was stopped after verification. QA can repeat this exact lifecycle using the retained sibling runtime, without creating any system service.
