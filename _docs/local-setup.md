# Local development setup

## Current status

The Python bootstrap and typed configuration loader are ready, with automated tests. No FastAPI or frontend service, database connection, email transport, or marketplace feature exists yet. Loading configuration never starts services or sends email.

## Current layout

- `pyproject.toml` and `requirements.lock`: Python 3.11+ metadata and pinned configuration dependencies.
- `backend/__init__.py`: empty importable project package.
- `tests/test_bootstrap.py`: one package import and path smoke test.
- `backend/config.py` and `tests/test_config.py`: explicit settings loading and isolated configuration tests.
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

On Linux or macOS, use `.venv/bin/python` instead of `.venv/Scripts/python.exe`. Activation is optional. Tests inject synthetic isolated settings and need no .env, real credentials, network, database, SMTP, or running service. The suite includes the original package smoke test and ten configuration tests.

In a restricted Windows environment whose temporary directory is not writable, first create a workspace temporary directory and direct this terminal's TEMP and TMP to it before the commands above:

```powershell
New-Item -ItemType Directory -Force .venv/tmp | Out-Null
$env:TEMP = (Resolve-Path .venv/tmp).Path
$env:TMP = $env:TEMP
```

The pip workflow adds only pydantic-settings 2.15.0 and its resolved configuration dependencies: pydantic 2.14.1, pydantic-core 2.50.1, python-dotenv 1.2.4, annotated-types 0.8.0, typing-inspection 0.4.4, and typing-extensions 4.16.0. All versions are pinned in `requirements.lock`; keep the manifest and export aligned when approved dependencies change. No FastAPI, database, email transport, JWT, or frontend libraries are installed yet.

The future application uses React, FastAPI, PostgreSQL, SQLAlchemy, Alembic, and JWT authentication. Node.js, npm, and PostgreSQL installation requirements will be documented when the relevant tasks establish them.

## Local configuration

Copy `.env.example` to an ignored `.env` and replace credential placeholders before explicitly loading runtime settings. Never commit real secrets. No usable JWT secret is provided or generated: missing, blank, placeholder, or shorter-than-32-character values are rejected. DATABASE_URL is also required and must be a PostgreSQL connection URL. This validates configuration only, not a live connection.

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

Service startup and migration commands are not available yet. Add actual tested commands as each task is implemented. Keep passwords, SMTP credentials, JWT secrets, local .env files, uploads, and credential files out of Git. The configuration contract is implemented above; the decision baseline is recorded in [the plan](plan.md).
