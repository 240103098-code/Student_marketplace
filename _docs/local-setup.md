# Local development setup

## Current status

The Python bootstrap, typed configuration loader, PostgreSQL engine/session helpers, connection-check command, account/code/refresh-session schema, registration API with configured SMTP verification-code delivery, and React preview shell are ready, with automated tests. The backend HTTP service currently supports registration only. No listing schema, activation, login, token issuance, or marketplace authorization exists yet. Live internet inbox delivery remains unverified. Importing configuration/database helpers never starts services, connects, or creates tables. Frontend routes are placeholders and make no backend requests.

## Current layout

- `pyproject.toml` and `requirements.lock`: Python 3.11+ metadata and pinned dependencies.
- `backend/__init__.py`: empty importable project package.
- `tests/test_bootstrap.py`: one package import and path smoke test.
- `backend/config.py` and `tests/test_config.py`: explicit settings loading and isolated configuration tests.
- `backend/database.py`, `alembic.ini`, and `migrations/`: PostgreSQL infrastructure, the baseline, and account schema revision.
- `tests/test_database.py` and `tests/test_database_integration.py`: unit checks and opt-in actual PostgreSQL baseline tests.
- `backend/models.py` and `tests/test_models*`: account/code/refresh models, redacted representations, and actual PostgreSQL integrity tests.
- `frontend/`: React/Vite preview shell, two component tests, and a resolved npm lockfile.
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

On Linux or macOS, use `.venv/bin/python` instead of `.venv/Scripts/python.exe`. Activation is optional. The default run has twenty-six service-free tests and skips four PostgreSQL integration classes. Unit tests inject synthetic isolated settings and need no .env, real credentials, network, database, SMTP, or running service. Opt in to twenty-one PostgreSQL/loopback-SMTP integration cases using the preparation below.

In a restricted Windows environment whose temporary directory is not writable, first create a workspace temporary directory and direct this terminal's TEMP and TMP to it before the commands above:

```powershell
New-Item -ItemType Directory -Force .venv/tmp | Out-Null
$env:TEMP = (Resolve-Path .venv/tmp).Path
$env:TMP = $env:TEMP
```

The pip workflow adds pydantic-settings 2.15.0 with its six resolved configuration dependencies, plus SQLAlchemy 2.1.4, Alembic 1.20.0, and psycopg[binary] 3.3.6. Database transitive additions are psycopg-binary 3.3.6, Mako 1.4.3, MarkupSafe 3.0.4, and tzdata 2026.5. All versions are pinned in `requirements.lock`; keep the manifest and export aligned when approved dependencies change. Registration adds FastAPI 0.143.0, uvicorn 0.54.0, argon2-cffi 25.1.0, email-validator 2.3.0, and httpx 0.28.1 with their required resolved dependencies, all pinned in requirements.lock. SMTP delivery uses only the standard library; this task adds no dependencies. No JWT feature library has been added.

The planned complete application uses React, FastAPI, PostgreSQL, SQLAlchemy, Alembic, and JWT authentication. The current React shell is described below; activation, login, and authenticated marketplace access remain future work.

## Local configuration

Copy `.env.example` to an ignored `.env` and replace credential placeholders before explicitly loading runtime settings. Never commit real secrets. No usable JWT secret is provided or generated: missing, blank, placeholder, or shorter-than-32-character values are rejected. DATABASE_URL is also required and must be a PostgreSQL connection URL. Configuration loading validates the URL only; the separate connection-check command contacts PostgreSQL.

Call `backend.config.load_settings()` explicitly; importing the module does not load or validate settings. Environment variables override `.env` values, which override safe non-secret defaults. Both a relative .env filename and a relative UPLOAD_DIR resolve from the repository root, independent of the caller's working directory. Tests can pass `environ={...}, env_file=None` to ignore ambient settings and disable file loading. Errors name the invalid setting without printing its value; database credentials, JWT secrets, and SMTP credentials are redacted from settings representations.

The complete setting contract is documented beside each name in `.env.example`: APP_ENV, DATABASE_URL, UNIVERSITY_EMAIL_DOMAIN, FRONTEND_ORIGINS, JWT_SECRET_KEY, JWT_ACCESS_MINUTES, REFRESH_SESSION_DAYS, UPLOAD_DIR, REFRESH_COOKIE_SECURE, REFRESH_COOKIE_HTTPONLY, REFRESH_COOKIE_SAMESITE, SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL, and SMTP_SECURITY. FRONTEND_ORIGINS is a JSON array of explicit origins without paths; wildcard origins are rejected. The university domain is exactly sdu.edu.kz.

Production requires HTTPS frontend origins and a Secure refresh cookie (automatically true if omitted in production). Development/test allow HTTP loopback origins and a non-Secure cookie; HttpOnly and SameSite=lax are mandatory in every mode. This task validates settings; cookie, CORS, and CSRF enforcement remain future application work.

SMTP is optional during early setup. Before enabling email delivery, call `settings.validate_email_delivery()` to require host, port, username, password, and sender together. SMTP_SECURITY is starttls by default or tls; select the server's actual mode and port. This check never connects or sends mail. Real SMTP credentials and a live mail account remain external operator setup. The implemented SMTP sender uses this check and verified TLS/STARTTLS before authentication, a ten-second network timeout, and cleanup on success/failure.

## Setup tasks

- [Task 1](https://github.com/240103098-code/Student_marketplace/issues/1) establishes the empty project and first automated test.
- [Task 3](https://github.com/240103098-code/Student_marketplace/issues/3) defines environment-based configuration and the example configuration file.
- [Task 4](https://github.com/240103098-code/Student_marketplace/issues/4) connects PostgreSQL and introduces migrations.
- [Task 5](https://github.com/240103098-code/Student_marketplace/issues/5) creates the React application shell and a component test.
- [Task 8](https://github.com/240103098-code/Student_marketplace/issues/8) configures real verification-email delivery.
- [Task 40](https://github.com/240103098-code/Student_marketplace/issues/40) verifies and documents the complete local MVP demonstration.

The registration-only backend startup command is documented below. Keep passwords, SMTP credentials, JWT secrets, local .env files, uploads, and credential files out of Git. The configuration contract is implemented above; the decision baseline is recorded in [the plan](plan.md).

## Registration-only backend service

After configuring ignored runtime settings and starting your PostgreSQL database, apply `.venv/Scripts/python.exe -m alembic upgrade head`. Then run this tested command from the repository root:

```powershell
.venv/Scripts/python.exe -m uvicorn backend.main:create_runtime_app --factory --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` or `/openapi.json`; stop with Ctrl+C. Startup was verified on loopback with Python 3.13.15, FastAPI 0.143.0, and uvicorn 0.54.0. The explicit runtime factory loads validated settings, creates lazy database infrastructure, and disposes owned resources on normal shutdown. Injected borrowed infrastructure remains its caller's responsibility.

POST /auth/register validates strict email/password JSON fields and persists an unverified, unsuspended student with an Argon2id password hash. See [the API contract](api.md) for exact normalization, limits, responses, and safe errors. Registration now generates a cryptographically random six-digit code, stores only its keyed digest, and sends it by configured SMTP. Missing/incomplete settings or delivery errors return sanitized 503 and roll back the account/code transaction. Registration does not activate the account or issue tokens. Frontend forms and API integration remain future work.

The seven registration regression tests use an explicitly injected test sender and cover hash verification/mismatch, normalization, duplicate/concurrent uniqueness, rollback, domain/lookalike rejection, password boundaries without trimming/coercion, malformed/missing/extra inputs, and safe errors/logs. They use the same confirmed disposable database safeguards, migrate their schema, clean test records, and downgrade to baseline after completion. Dependency consistency and frontend regressions passed.

## Verification-email delivery and live check

Configure all SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM_EMAIL values in ignored runtime configuration. Use SMTP_SECURITY=starttls for explicit STARTTLS (commonly port 587), or tls for SMTP-over-TLS (commonly port 465), matching the actual server rather than assuming its ports. Production uses the default verified SSL context and never disables hostname/certificate checks or falls back to plaintext/console delivery. An explicit ASCII client hostname avoids machine-name disclosure and Unicode EHLO failures.

Code issuance uses secrets.randbelow for six digits (including leading zeros), a ten-minute lifetime, and HMAC-SHA256 keyed from validated JWT_SECRET_KEY with domain-separated user/purpose binding. It persists only the digest, creation/expiry, zero attempts, and state. It locks the user's row, invalidates earlier usable same-purpose codes, and sends inside the caller transaction; failure restores the previous usable code by rollback. Verification, resend cooldown/endpoint, activation, and recovery endpoints are later work.

The normal full backend test command from the disposable PostgreSQL lifecycle also runs the controlled SMTP fixture. It binds only to 127.0.0.1 on an ephemeral port and keeps received MIME messages in test memory. Its transport substitution is explicitly test-only; TLS/auth ordering and verified SSL contexts are checked separately without any production bypass. No external recipient messages were sent.

**Live internet university-inbox delivery has not been verified.** Provider hostname, port, sender, credentials, and a real SMTP account remain external operator setup. For that later credential-dependent check, an operator should configure their own provider securely, start PostgreSQL/apply migrations and the backend, intentionally register their own sdu.edu.kz address through the API, and inspect their own inbox for the verification message. Do not publish the code or credentials. This operator check has not been run, and no SMTP credentials or live delivery are fabricated.

## React preview shell

Supported Node versions match `frontend/package.json`: 22.22.2+ on the 22.x line, 24.15.0+ on the 24.x line, or 26+. Verification used the available **Node 24.19.0** and **npm 12.2.0**. Use npm 12.2.0 or newer with a compatible Node version. No global tooling configuration was changed.

From `frontend`, these clean installation, noninteractive test, and production-build commands passed:

```powershell
npm ci
npm run test -- --run
npm run build
npm run dev
```

Open `http://127.0.0.1:5173/` and stop the development server with Ctrl+C. It binds only to loopback with a strict port; an occupied 5173 reports an error rather than changing the URL. Known routes `/`, `/login`, `/register`, `/verify`, and `/marketplace` support direct opening/reload through Vite's SPA fallback; other routes display Page not found.

Navigation uses ordinary links with client-side history, a shared header/main landmark, skip link, visible focus styles, and a wrapping mobile layout. The preview collects no passwords or codes, fabricates no listings or seller data, and simulates no authentication. Verified-only authorization remains future work; a visible marketplace link grants no access to real content.

Direct dependencies are React/React DOM 19.3.0. Development dependencies are Vite 8.3.4, Vitest 5.0.4, Testing Library React 16.3.3, and jsdom 30.1.2. No routing, backend client, UI framework, or state library is added. `package-lock.json` pins the resolved dependency graph; `node_modules` and `dist` remain ignored. Two focused tests follow user-visible links and verify destination/not-found headings; the production build writes `frontend/dist`.

npm was not available on PATH in the verification environment. Its official package was obtained from [the npm registry](https://registry.npmjs.org/npm/12.2.0), extracted to sibling `../npm-runtime/package`, outside this repository. To repeat that workspace-local setup without global installation, run from the repository root:

```powershell
New-Item -ItemType Directory -Force ../npm-runtime | Out-Null
Invoke-WebRequest https://registry.npmjs.org/npm/-/npm-12.2.0.tgz -OutFile ../npm-runtime/npm.tgz
tar -xzf ../npm-runtime/npm.tgz -C ../npm-runtime
```

Then, from `frontend`, replace the commands above with their tested local equivalents:

```powershell
node ../../npm-runtime/package/bin/npm-cli.js ci --cache ../../npm-runtime/cache --no-fund --no-audit
node ../../npm-runtime/package/bin/npm-cli.js run test -- --run
node ../../npm-runtime/package/bin/npm-cli.js run build
node ../../npm-runtime/package/bin/npm-cli.js run dev
```

Dependency retrieval and local server connections required approved execution outside this environment's networking sandbox. Backend files and schemas were unchanged; the existing backend tests passed, while actual PostgreSQL integration tests are opt-in and remains separately documented below.

## PostgreSQL connection and migrations

Configure DATABASE_URL for a PostgreSQL database that you control, using `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE` (plain `postgresql://` also selects psycopg). Explicit database construction creates a lazy engine and session factory; importing the module never loads settings or connects. Connections have a three-second driver timeout and a five-second statement timeout. Session contexts commit on success, roll back on failure, and always close; the owner explicitly disposes the engine.

From the repository root, with runtime settings configured, these tested commands perform connection checks and migrations. Normal setup uses upgrade head; the downgrade/roundtrip commands are for disposable databases because downgrading the account revision drops its tables and data:

```powershell
.venv/Scripts/python.exe -m backend.database check
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic current
.venv/Scripts/python.exe -m alembic downgrade base
.venv/Scripts/python.exe -m alembic upgrade head
```

The check returns a nonzero exit code and a sanitized message on connection failure. Alembic reads the same explicit settings contract; `alembic.ini` contains no URL or credentials. Baseline `0001_baseline` only tracks the revision in `alembic_version`; current head `0002_accounts` additionally creates exactly users, email_codes, and refresh_sessions. Revert just this schema with `.venv/Scripts/python.exe -m alembic downgrade 0001_baseline`, then reapply with `upgrade head`; both directions were verified against actual PostgreSQL.

## Dedicated PostgreSQL integration tests

### Account schema representation

`users` stores a normalized, unique university email, password hash, verification/suspension flags, student/admin role, creation timestamp, and nullable name/avatar/contact fields. Model assignment trims/lowercases email; PostgreSQL also rejects non-normalized values, unsupported roles, empty identity/hash values, and domains other than exactly sdu.edu.kz. The unique email constraint supplies the lookup index. New persisted users are unverified, unsuspended students; profile completion belongs to a later workflow.

`email_codes` stores only a digest, registration or password_reset purpose, user FK, timezone-aware creation/expiry, zero-to-five wrong attempts, and nullable consumption/invalidation timestamps. Its composite user/purpose index supports purpose-specific lookup. `refresh_sessions` stores only a unique token digest, user FK, UUID family, timezone-aware creation/expiry/revocation, and nullable unique predecessor/successor IDs. Its user/family index supports revocation queries; digest uniqueness supplies lookup indexing. UUID defaults use PostgreSQL's built-in gen_random_uuid().

Deleting a user cascades to their codes and sessions. Session lineage FKs use SET NULL on deletion, so no dangling predecessor/successor references remain. Family matching and rotation/reuse/revocation behavior are later service responsibilities; this task provides their representation only. Expired, revoked, consumed, and invalidated records remain representable. Repr methods omit password hashes and digests. No plaintext password/code/token fields, login, verification, or refresh flow exist; the registration endpoint stores only password hashes.

Models register the shared SQLAlchemy metadata without loading configuration or connecting. The original migration is unchanged, and revision 0002 follows it. Integration tests require an initially empty confirmed disposable database, create only their account schema, clean test records, and downgrade to baseline afterward; they never reset an arbitrary application database. No new dependency was required for this schema task.

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

For a previously prepared dedicated cluster, omit only the CREATE DATABASE line. This environment required approved execution outside the networking sandbox for loopback clients and the single start/test/stop lifecycle. All **47 backend tests passed with no skips**, including twenty-one PostgreSQL/SMTP integration cases: baseline/connection/session regressions, six account-schema integrity/roundtrip tests, seven registration HTTP/persistence regressions, and five SMTP delivery/replacement/rollback cases. Four focused transport unit tests verify TLS/auth order, certificate verification, bounded timeout, cleanup, and sanitized failures. The historical baseline test targets 0001_baseline explicitly; the new schema test targets head, so both migration contracts remain covered. Frontend tests and production build also passed. The temporary server was stopped after verification. QA can repeat this exact lifecycle using the retained sibling runtime, without creating any system service.
