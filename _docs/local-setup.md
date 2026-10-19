# Local development setup

## Current status

The Python bootstrap, typed configuration loader, PostgreSQL engine/session helpers, connection-check command, account/code/refresh-session schema, registration API with configured SMTP verification-code delivery, and React preview shell are ready, with automated tests. The backend HTTP service supports registration, verification/resend, login, and minimal protected account access. One-time email activation and cooldown-limited resend are also ready; verified-user login/access JWTs and /auth/me are ready; secure refresh rotation/logout are ready; React registration/verification forms are ready; React login, session restoration, and protected navigation are ready; listing submission and fixed-category endpoints are ready; listing-photo append/private reads are ready; the creation UI is ready; browsing/search/filter/detail/report endpoints and explicit admin access are available below. Live internet inbox delivery remains unverified. Importing configuration/database helpers never starts services, connects, or creates tables. Frontend registration/verification/login/profile/photo routes use their implemented API contracts; marketplace content and the protected admin landing use their real API contracts.

## Current layout

- `pyproject.toml` and `requirements.lock`: Python 3.11+ metadata and pinned dependencies.
- `backend/__init__.py`: empty importable project package.
- `tests/test_bootstrap.py`: one package import and path smoke test.
- `backend/config.py` and `tests/test_config.py`: explicit settings loading and isolated configuration tests.
- `backend/database.py`, `alembic.ini`, and `migrations/`: PostgreSQL infrastructure, the baseline, account schema, and listing/report schema revisions.
- `tests/test_database.py` and `tests/test_database_integration.py`: unit checks and opt-in actual PostgreSQL baseline tests.
- `backend/models.py` and `tests/test_models*`: account/code/refresh models, redacted representations, and actual PostgreSQL integrity tests.
- `frontend/`: React/Vite shell and registration/verification forms, eleven interaction tests, and a resolved npm lockfile.
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

On Linux or macOS, use `.venv/bin/python` instead of `.venv/Scripts/python.exe`. Activation is optional. The default run has thirty-one service-free tests and skips seven PostgreSQL integration classes. Unit tests inject synthetic isolated settings and need no .env, real credentials, network, database, SMTP, or running service. Opt in to fifty PostgreSQL/loopback-SMTP integration cases using the preparation below.

In a restricted Windows environment whose temporary directory is not writable, first create a workspace temporary directory and direct this terminal's TEMP and TMP to it before the commands above:

```powershell
New-Item -ItemType Directory -Force .venv/tmp | Out-Null
$env:TEMP = (Resolve-Path .venv/tmp).Path
$env:TMP = $env:TEMP
```

The pip workflow adds pydantic-settings 2.15.0 with its six resolved configuration dependencies, plus SQLAlchemy 2.1.4, Alembic 1.20.0, and psycopg[binary] 3.3.6. Database transitive additions are psycopg-binary 3.3.6, Mako 1.4.3, MarkupSafe 3.0.4, and tzdata 2026.5. All versions are pinned in `requirements.lock`; keep the manifest and export aligned when approved dependencies change. Registration adds FastAPI 0.143.0, uvicorn 0.54.0, argon2-cffi 25.1.0, email-validator 2.3.0, and httpx 0.28.1 with their required resolved dependencies, all pinned in requirements.lock. SMTP delivery uses only the standard library; this task adds no dependencies. Access tokens add only PyJWT 2.15.1, pinned in requirements.lock; it adds no transitive dependencies.

The planned complete application uses React, FastAPI, PostgreSQL, SQLAlchemy, Alembic, and JWT authentication. The current React shell is described below; refresh handling, React authentication, and marketplace endpoints remain future work.

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
.venv/Scripts/python.exe -m uvicorn backend.main:create_runtime_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

Open `http://127.0.0.1:8000/docs` or `/openapi.json`; stop with Ctrl+C. Startup was verified on loopback with Python 3.13.15, FastAPI 0.143.0, and uvicorn 0.54.0. The explicit runtime factory loads validated settings, creates lazy database infrastructure, and disposes owned resources on normal shutdown. Injected borrowed infrastructure remains its caller's responsibility.

POST /auth/register validates strict email/password JSON fields and persists an unverified, unsuspended student with an Argon2id password hash. See [the API contract](api.md) for exact normalization, limits, responses, and safe errors. Registration now generates a cryptographically random six-digit code, stores only its keyed digest, and sends it by configured SMTP. Missing/incomplete settings or delivery errors return sanitized 503 and roll back the account/code transaction. Registration starts the account unverified; the verification endpoint activates it. Neither endpoint issues tokens. Frontend registration and verification forms now use these contracts; login/session UI remains future work.

The seven registration regression tests use an explicitly injected test sender and cover hash verification/mismatch, normalization, duplicate/concurrent uniqueness, rollback, domain/lookalike rejection, password boundaries without trimming/coercion, malformed/missing/extra inputs, and safe errors/logs. They use the same confirmed disposable database safeguards, migrate their schema, clean test records, and downgrade to baseline after completion. Dependency consistency and frontend regressions passed.

## Verification-email delivery and live check

Configure all SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM_EMAIL values in ignored runtime configuration. Use SMTP_SECURITY=starttls for explicit STARTTLS (commonly port 587), or tls for SMTP-over-TLS (commonly port 465), matching the actual server rather than assuming its ports. Production uses the default verified SSL context and never disables hostname/certificate checks or falls back to plaintext/console delivery. An explicit ASCII client hostname avoids machine-name disclosure and Unicode EHLO failures.

Code issuance uses secrets.randbelow for six digits (including leading zeros), a ten-minute lifetime, and HMAC-SHA256 keyed from validated JWT_SECRET_KEY with domain-separated user/purpose binding. It persists only the digest, creation/expiry, zero attempts, and state. It locks the user's row, invalidates earlier usable same-purpose codes, and sends inside the caller transaction; failure restores the previous usable code by rollback. Verification/activation and the sixty-second resend endpoint are implemented; recovery endpoints remain future work.

The normal full backend test command from the disposable PostgreSQL lifecycle also runs the controlled SMTP fixture. It binds only to 127.0.0.1 on an ephemeral port and keeps received MIME messages in test memory. Its transport substitution is explicitly test-only; TLS/auth ordering and verified SSL contexts are checked separately without any production bypass. No external recipient messages were sent.

**Live internet university-inbox delivery has not been verified.** Provider hostname, port, sender, credentials, and a real SMTP account remain external operator setup. For that later credential-dependent check, an operator should configure their own provider securely, start PostgreSQL/apply migrations and the backend, intentionally register their own sdu.edu.kz address through the API, and inspect their own inbox for the verification message. Do not publish the code or credentials. This operator check has not been run, and no SMTP credentials or live delivery are fabricated.

## Email verification and resend

Use the /verify form or documented backend API client to submit POST /auth/verify-email with the normalized email and six ASCII digits delivered to your own inbox. A usable registration code activates once, expires at ten minutes, and is invalidated on the fifth persisted wrong attempt. No login token or session is issued. POST /auth/resend-verification accepts only email and uses a sixty-second issuance cooldown with generic 202/Retry-After:60 for unknown, ineligible, or suppressed requests. SMTP failure is generic 503 and preserves an earlier usable code through rollback. See [the API contract](api.md) for all status/error bodies.

Verification locks both user and code before comparing expiry/digest and commits wrong-attempt state before returning its HTTP error. Resend locks the user before reading current time/latest issuance and sending a replacement. Deterministic test-only clock/mail injection covers expiry at and just before ten minutes, cooldown at and just before sixty seconds, persisted five attempts, replay/purpose rejection, concurrent correct/wrong/resend requests, replacement collision rejection, and failed-send rollback. These tests are included in the same documented disposable PostgreSQL lifecycle; no new schema or dependency was needed. Live internet inbox delivery remains unverified without operator SMTP credentials.

## Login and protected account proof

After verification, POST /auth/login with exactly email/password returns a Bearer access token and expires_in=900 by default. The email is normalized; password case/whitespace is preserved. Unknown, incorrect, unverified, and suspended credentials share a safe 401. Use Authorization: Bearer with GET /auth/me to obtain only id/email/verified plus boolean is_admin; each request reloads the account, so suspension, unverification, or deletion denies an existing signed token immediately.

HS256 is the sole allowed access algorithm. Issuer is student-marketplace, audience is student-marketplace-students; required exact claims are iss/aud/sub/type=access/iat/exp/jti/sid (session-family binding). UTC timestamps and the configured fifteen-minute default are enforced, including exact expiry and future-issued rejection. Tokens contain no sensitive profile/password/code data or trusted eligibility flags. Do not log/store the raw token in files; future browser integration keeps access tokens in memory.

Secure refresh sessions/cookies, rotation, logout, and immediate family revocation are implemented below. This task added only PyJWT 2.15.1 and reused existing Argon2/settings/database infrastructure, with no schema change. The documented backend test lifecycle verifies password boundaries/case/whitespace, generic credential rejection, protected access/current state changes, safe errors, and the focused JWT rejection matrix. API contracts are in [api.md](api.md).

## Refresh sessions, logout, and browser request setup

Login sets a host-only refresh_token cookie: HttpOnly, SameSite=Lax, Path=/auth, Secure in production, with the validated local HTTP exception. Only its digest is stored; the seven-day family expiry is fixed from login and never slides on rotation. Access JWTs require sid and the guard checks an active family plus current eligible account on every request. Old unbound JWTs no longer work.

After login/page reload, GET /auth/csrf with credentials:include retrieves a user/family-bound HMAC token without changing any state; it uses Cache-Control:no-store. Send that value in X-CSRF-Token plus the exact allowed Origin for POST /auth/refresh and /auth/logout, also with credentials:include. Refresh returns a new access token and replaces the HttpOnly cookie; it revokes/links the predecessor atomically. Reuse persistently revokes the whole family before 401, so old and newly returned access tokens stop working immediately. Logout is 204, user/family scoped, idempotent, and clears the cookie with matching attributes.

For absent/unknown/malformed logout cookies, there is no family to mutate or bind: allowed Origin and a well-formed CSRF header are still required; the state-free operation clears the cookie and returns 204. Known cookies always require their family-bound CSRF. Failed Origin/CSRF checks are 403 before mutation. Login rejects a supplied disallowed Origin. Credentialed CORS permits only configured origins and GET/POST/Authorization/Content-Type/X-CSRF-Token, with no wildcard.

For default FRONTEND_ORIGINS, use http://localhost:5173 and http://localhost:8000 consistently, despite the services binding IPv4 loopback. If using 127.0.0.1 in the browser, configure http://127.0.0.1:5173 and use 127.0.0.1 for the API as well; mixing hostnames breaks host-only/SameSite cookie handling. Production uses configured HTTPS origins and Secure cookies.

Ten actual PostgreSQL session tests cover digest-only persistence, fixed expiry/rotation links, old-access preservation within a live family, replay/concurrent family revocation, scoped/idempotent logout, unrelated-user isolation, local/production cookie/deletion flags, read-only CSRF bootstrap, Origin/CSRF/CORS failures without mutation, old unbound-token rejection, and a freshly signed JWT denied by expired family state. No schema/dependency changes or external emails were required. A reusable user-wide revocation helper is available for later password/deletion/admin workflows; no such new endpoint was added here. See api.md for exact error/response contracts.

## React shell and account forms

Supported Node versions match `frontend/package.json`: 22.22.2+ on the 22.x line, 24.15.0+ on the 24.x line, or 26+. Verification used the available **Node 24.19.0** and **npm 12.2.0**. Use npm 12.2.0 or newer with a compatible Node version. No global tooling configuration was changed.

From `frontend`, these clean installation, noninteractive test, and production-build commands passed:

```powershell
npm ci
npm run test -- --run
npm run build
npm run dev
```

Open `http://127.0.0.1:5173/` and stop the development server with Ctrl+C. It binds only to loopback with a strict port; an occupied 5173 reports an error rather than changing the URL. Known routes `/`, `/login`, `/register`, `/verify`, and `/marketplace` support direct opening/reload through Vite's SPA fallback; other routes display Page not found.

Navigation uses ordinary links with client-side history, a shared header/main landmark, skip link, visible focus styles, and a wrapping mobile layout. Registration and verification collect only their required inputs transiently and call the real API. The shell fabricates no listing/seller data and does not simulate login. Verified-only authorization remains future work; a visible marketplace link grants no access to real content.

Direct dependencies are React/React DOM 19.3.0. Development dependencies are Vite 8.3.4, Vitest 5.0.4, Testing Library React 16.3.3, and jsdom 30.1.2. No routing, backend client, UI framework, or state library is added. `package-lock.json` pins the resolved dependency graph; `node_modules` and `dist` remain ignored. Eleven focused tests cover shell links, registration/verification contracts, safe failures, pending-submit prevention, memory-only handoff, and timer-controlled resend behavior; the production build writes `frontend/dist`.

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

### Frontend API origin and registration/verification

Copy frontend/.env.example to ignored frontend/.env.local and set VITE_API_ORIGIN=http://localhost:8000 (or the same 127.0.0.1 hostname used in the browser). Restart Vite after changing configuration. This variable is a public API origin, never a place for JWT secrets, SMTP credentials, passwords, or codes. The fallback matches the browser's local hostname at port 8000. Use the same hostname for frontend/API and configure backend FRONTEND_ORIGINS to match the frontend exactly; requests use credentials:include for CORS/cookie compatibility.

/register validates university email and an untrimmed 12–128-character password, posts only those fields, and navigates to /verify after 201. The normalized email and sixty-second resend cooldown are memory-only; no password/code/email query parameters or browser storage are used. /verify can be opened/reloaded directly and its email is editable. Six ASCII digits are required, verification success shows a sign-in link without authenticating, and the backend's generic failures get honest replacement/expiry guidance with no invented attempt count.

Resend 202 never guarantees delivery: an eligible address may receive an email. Retry-After starts a readable sixty-second countdown; cooldowns remain in React memory while navigating. Pending requests disable overlapping actions; network/503 failures show safe retry feedback and do not add a new cooldown. Labels, autocomplete/inputmode, focus styles, native form Enter submission, and announced pending/error/success feedback support keyboard access. Timer text stays readable without announcing every second to screen readers.

Eleven frontend tests and production build passed with existing dependencies, and all 81 backend tests passed including actual PostgreSQL/loopback SMTP regressions. No backend/dependency changes were required. Live internet university-inbox delivery still needs external provider credentials; no live email claim is made.

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

The check returns a nonzero exit code and a sanitized message on connection failure. Alembic reads the same explicit settings contract; `alembic.ini` contains no URL or credentials. Baseline `0001_baseline` only tracks the revision in `alembic_version`; `0002_accounts` creates users, email_codes, and refresh_sessions; current head `0003_listings` adds categories, listings, listing_photos, and listing_reports. Revert just this schema with `.venv/Scripts/python.exe -m alembic downgrade 0001_baseline`, then reapply with `upgrade head`; both directions were verified against actual PostgreSQL.

## Dedicated PostgreSQL integration tests

### Account schema representation

`users` stores a normalized, unique university email, password hash, verification/suspension flags, student/admin role, creation timestamp, and nullable name/avatar/contact fields. Model assignment trims/lowercases email; PostgreSQL also rejects non-normalized values, unsupported roles, empty identity/hash values, and domains other than exactly sdu.edu.kz. The unique email constraint supplies the lookup index. New persisted users are unverified, unsuspended students; profile completion belongs to a later workflow.

`email_codes` stores only a digest, registration or password_reset purpose, user FK, timezone-aware creation/expiry, zero-to-five wrong attempts, and nullable consumption/invalidation timestamps. Its composite user/purpose index supports purpose-specific lookup. `refresh_sessions` stores only a unique token digest, user FK, UUID family, timezone-aware creation/expiry/revocation, and nullable unique predecessor/successor IDs. Its user/family index supports revocation queries; digest uniqueness supplies lookup indexing. UUID defaults use PostgreSQL's built-in gen_random_uuid().

Deleting a user cascades to their codes and sessions. Session lineage FKs use SET NULL on deletion, so no dangling predecessor/successor references remain. Family matching and rotation/reuse/revocation behavior are later service responsibilities; this task provides their representation only. Expired, revoked, consumed, and invalidated records remain representable. Repr methods omit password hashes and digests. No plaintext password/code/token fields exist; the registration endpoint stores only password hashes.

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

For a previously prepared dedicated cluster, omit only the CREATE DATABASE line. This environment required approved execution outside the networking sandbox for loopback clients and the single start/test/stop lifecycle. All **81 backend tests passed with no skips**, including fifty PostgreSQL/SMTP integration cases: baseline/connection/session regressions, six account-schema integrity/roundtrip tests, seven registration HTTP/persistence regressions, five SMTP delivery/replacement/rollback cases, twelve verification/resend boundary/race/accounting cases, seven login/current-eligibility cases, and ten refresh/cookie/CSRF/CORS/concurrency/logout cases. Five focused JWT tests cover required claims, signature/algorithm rejection, strict types/purpose/issuer/audience, and exact expiry/future-issued time. Four focused transport unit tests verify TLS/auth order, certificate verification, bounded timeout, cleanup, and sanitized failures. The historical baseline test targets 0001_baseline explicitly; the historical account schema test explicitly targets 0002_accounts, and the listing schema test targets head, preserving each revision contract. Frontend tests and production build also passed. The temporary server was stopped after verification. QA can repeat this exact lifecycle using the retained sibling runtime, without creating any system service.


## React browser sessions

Open /login to sign in with a previously verified disposable university account. Login confirms /auth/me before displaying protected Marketplace, Profile, and My Listings content. Reload checks the HttpOnly cookie through /auth/csrf, rotates once, and confirms eligibility while showing a loading state. Anonymous visitors return to /login; after sign-in only the exact internal student destination is restored. Admin navigation and the landing require confirmed current server admin access, documented below.

Keep frontend VITE_API_ORIGIN and backend FRONTEND_ORIGINS on the same hostname as described above. Requests include browser credentials; CSRF and Bearer values stay in memory. Sign out waits for the API to confirm revocation; a failed network/server response shows retry guidance and does not claim success. Registration/verification remain accessible. Shared GET recovery retries once; mutations are not automatically replayed.

Twenty-three frontend interaction tests and the production build passed, together with all 81 existing backend tests against the isolated PostgreSQL/loopback SMTP fixtures. No backend or dependency changes were needed. External SMTP credentials and real university inbox delivery remain operator setup; browser sessions do not supply a demo verification bypass.


## Change your password

After verified sign-in, use **Change password** in navigation or open /account/password. Enter your current password, a 12–128-character new password, and matching confirmation; spaces are preserved, and only current_password/new_password are sent. Confirmed success revokes every session on the account, removes the matching browser cookie, clears the form/auth state, and returns to sign-in. Use the new password afterward. An incorrect current password or network/server failure shows retry feedback without claiming change or sign-out. This screen does not implement forgotten-password email recovery.

Verification passed with 27 frontend interaction tests, production build, and all 88 backend tests with real disposable PostgreSQL/controlled SMTP, including seven password-change persistence/boundary/rollback/isolation/concurrency cases. No dependencies or schema changes were required. External SMTP/inbox setup remains outstanding as documented above.


## Forgotten-password recovery

From /login choose **Forgot your password?**, or open /forgot-password. Use your university email; only verified, unsuspended existing accounts are eligible for a reset email. Every valid request shows the same generic accepted response and sixty-second retry countdown, including unknown/ineligible accounts, suppressed requests, missing SMTP configuration and delivery failures. Acceptance does not guarantee an email arrived. Configure the real external provider as above; live university-inbox delivery is still unverified.

Open /reset-password via the code link or directly and enter your email, six ASCII digits, and a new 12–128-character password with confirmation. Codes expire after ten minutes; five incorrect attempts require replacement. Successful reset consumes the code and changes the password while revoking all account sessions, clears form/auth state and returns to sign-in without automatically logging in. The old password/tokens no longer work. Registration codes and verification status are independent; recovery cannot activate an unverified account.

All 100 backend tests passed with the isolated PostgreSQL and controlled loopback SMTP fixtures, including twelve new recovery delivery/purpose/generic-response/rollback/attempt/expiry/concurrency/session-isolation cases. All 31 frontend tests and production build passed, including four recovery-form interaction tests. No new dependencies or schema changes were required; test PostgreSQL was stopped after verification.


## Backend own-profile support

With verified session-bound Bearer access, GET /users/me reads only your basic profile and PATCH /users/me edits supplied name/contact fields. Empty patches and identity/security/avatar fields are rejected. Name is trimmed and required when supplied; optional phone/Telegram/HTTPS contact values may be cleared with null. Omitted fields are preserved, and initial unset profiles remain null. Profile editing may leave contacts empty; the contact prerequisite belongs to listing submission. See API notes for exact formats and sanitized statuses. Configured credentialed CORS permits PATCH.

The backend endpoints support the /profile browser screen described below; private avatar controls are available as described below. Verification passed with 109 backend tests using actual isolated PostgreSQL/controlled SMTP, including nine profile read/ownership/format/partial-update/security/rollback/stale-guard/CORS cases, plus all 31 frontend tests and production build. No frontend, dependency, or schema change was required.


## Edit your profile in the browser

After verified sign-in, choose **Profile** or open /profile. Loading reads your actual account profile; failed loads offer retry. Verified email stays read-only. Edit name, international phone, Telegram username or HTTPS contact URL using the displayed hints. Optional contacts may all be cleared. Save submits only changed fields; unchanged initial null name is omitted. Successful saving refreshes the form from the server response. Failed saves retain edits and show truthful retry feedback; expired/revoked authorization removes the screen. Private avatar controls are described below; seller-contact display is not available yet.

All 38 frontend interaction tests and production build passed, including seven profile loading/retry/null/identity/partial-save/clearing/validation/pending/failure/session cases. All 109 backend tests passed with actual dedicated PostgreSQL/controlled SMTP fixtures. No backend, dependency, or schema changes were needed.


## Optional private profile photo

On /profile, choose an optional JPEG, PNG or WebP of at most five MiB and twenty million pixels. The backend decodes/re-encodes it without EXIF/embedded metadata, stores a generated owner-specific path beneath UPLOAD_DIR, and serves it only through authenticated /users/me/avatar. Uploading replaces the current photo; Remove photo removes it idempotently. Browser previews use authenticated binary blobs and disposable object URLs, never token-bearing/public URLs. Pending controls and safe errors support retries without claiming unconfirmed changes.

Ensure the configured upload root is writable by the local backend process and not a symlink/junction escape. No public static uploads mount is created. A failed replacement preserves the previous avatar and attempts new-file cleanup; after successful commit, old-file cleanup can still fail. The response then reports cleanup_pending and the browser shows a pending-cleanup notice. A rollback cleanup failure may leave an unreferenced generated file. Reconcile only verified unreferenced generated files under the configured root; disk/database cleanup is not claimed to be fully atomic.

Minimal added dependencies: [Pillow 12.3.0](https://pypi.org/project/pillow/12.3.0/) for actual image decoding/re-encoding and [python-multipart 0.0.32](https://pypi.org/project/python-multipart/0.0.32/) for bounded multipart parsing; both are pinned in pyproject.toml and requirements.lock and installed only in the isolated project environment. No schema change was needed. All 117 backend tests passed with real disposable PostgreSQL/filesystem/loopback SMTP fixtures, including eight avatar formats/limits/privacy/replacement/rollback/cleanup/ownership/symlink-or-junction cases. All 44 frontend tests and production build passed, including six avatar multipart/blob/object-URL/pending/failure/removal cases. Test PostgreSQL was stopped.


## Listing/report schema migration

Run the existing upgrade head command to apply 0003_listings after 0002_accounts. The revision adds four tables and seeds the five fixed category identifiers documented in API notes. Listings store constrained decimal KZT price, title/description, owner/category, new/used condition, pending/active/sold/rejected/removed states and publication/rejection metadata. New listings are unpublished pending records; listing APIs and manual approval controls are documented below. PostgreSQL NUMERIC(12,2) rounds excess scale, so upcoming request validation must reject excess decimal places explicitly.

Ordered photo paths have five unique slots and lowest-position main derivation. Three-reason reports have simple reviewed timestamps. Owner/reporter cascades remove dependent metadata, while category deletion is restricted. These foreign keys do not clean disk files; later upload/deletion services own that work. No file changes or frontend feature is introduced by this schema revision.

Only on disposable data, downgrade to 0002_accounts drops the four new tables while preserving users/codes/sessions; upgrade head recreates tables and stable category seeds. Historical 0001 and 0002 migration checks remain explicit. Verification passed with all 124 backend tests against actual dedicated PostgreSQL/controlled SMTP, including seven new listing/report constraints/ordering/cascade/index/roundtrip cases; all 44 frontend tests and production build passed. No dependencies were added, and test PostgreSQL was stopped.


## Submit listings through the backend API

Verified users with an active session and at least one valid profile contact may POST /listings. There is no name prerequisite. Submit only title/description, price, fixed category_id (1–5), and new/used condition. Text is trimmed and validated; prices are exact finite decimals in KZT, 0–1,000,000,000 with at most two meaningful fractional digits. Use canonical decimal strings for browser/form values to avoid floating arithmetic; JSON numbers are parsed exactly, and unsupported strings/excess precision are rejected before PostgreSQL rounding. Successful 201 returns a private own-listing DTO with canonical two-decimal price and pending/unpublished state. Manual approval is required before marketplace visibility.

Authenticated GET /categories supplies stable ids/keys/labels in fixed id order. Missing/invalid contacts return safe profile guidance; invalid fields/ownership/publication attempts are rejected; expired/revoked/ineligible sessions cannot submit/read categories. See API notes for exact payloads, decimal grammar and sanitized statuses. Listing-photo upload is documented below; the creation UI is documented below; marketplace browsing is documented below; detail and admin approval controls are documented below.

All 132 backend tests passed against real isolated PostgreSQL/controlled SMTP, including eight new submission DTO/persistence/category/field/decimal/ownership/contact/eligibility/rollback/stale-guard cases. The eight focused cases also passed after rejecting NUL text before persistence; negative decimal zero normalization was checked directly. All 44 frontend tests and production build passed. No dependencies, schema or frontend changes were needed; PostgreSQL was stopped.


## Append private listing photos through the API

After creating your pending listing, POST one multipart image field per request to /listings/{id}/photos using Bearer access. Only its current owner can append, up to five photos. Ordered positions start at one; the first is main. The server applies the same decoded JPEG/PNG/WebP, five-MiB/twenty-million-pixel and metadata-stripping protections as avatars and stores generated confined listing paths. Do not supply owner/path/position fields or manually set the multipart boundary. Success returns a photo identifier, position/main flag and protected binary URL without a raw path. The React selection/upload form is documented below.

Fetch the protected photo route with Bearer credentials into a binary blob, never a token query URL. Owners can view their pending/active/sold/rejected photos; verified buyers can view only active listings with eligible sellers. Removed/forbidden/mismatched photos are unavailable. Photo changes are rejected after pending, and no replacement/reordering endpoint is supplied. Account then listing locks serialize eligibility/state and the fifth-slot boundary. Failure rolls back new metadata and attempts new-file cleanup while preserving existing/avatar/other-listing files; unrecoverable cleanup may leave a generated orphan as described above.

All 140 backend tests passed with actual isolated PostgreSQL/disposable upload roots/controlled SMTP, including eight new photo DTO/order/five-six/concurrency/ownership/state/linkage/eligibility/rollback/race cases. Detailed format/size/pixel/traversal/symlink boundaries remain covered by shared avatar tests. All 44 frontend tests and production build passed. No dependencies, schema or UI changes were needed; PostgreSQL stopped after verification.


## Create a listing in the browser

After verified sign-in, choose **Create listing** or open /listings/new. Categories come from the protected API. Fill title/description, an exact KZT decimal price, category and condition; optionally select up to five JPEG/PNG/WebP photos in the desired order. The first is main; remove unsubmitted selections as needed. A missing valid contact gives a real profile link. Creation saves one Pending listing, then uploads selected photos one at a time. Keep this page open while uploads finish; the confirmed id/counts and selected files stay only in page memory.

If an upload is explicitly rejected, correct/remove remaining selections and use Retry remaining photos; confirmed files and metadata are not repeated. Network/5xx/invalid-success responses are uncertain and block blind retries to avoid duplicates. The page does not claim that nothing was saved, nor invent a saved-listing lookup feature. If uncertain, retain the confirmed id if shown and use the now-available My Listings review link; no automatic mutation reconciliation/retry is performed. Completion means Pending manual admin review, not public publication; the available next action is Profile. Marketplace, buyer detail, My Listings and admin approval screens are documented below.

All 56 frontend interaction tests and production build passed, including twelve new category/validation/exact payload/zero-five-six selection/preview cleanup/pending/ordered multipart/partial retry/contact/network-5xx-invalid-response cases. All 140 backend tests passed against real isolated PostgreSQL/disposable filesystem/controlled SMTP. No backend, dependency or schema changes were needed; PostgreSQL stopped afterward.


## Edit listing price or description

Open /listings/{id}/edit for your known listing id, or use the edit link after confirmed creation. The page loads your current own values through GET /listings/{id}/edit and shows title/status/publication read-only. Change only exact KZT price or trimmed description; unchanged fields are omitted. Pending, Active and Sold permit editing, preserving approval/publication and immutable fields/photos. Rejected requires deletion/recreation and Removed cannot be edited; those states show disabled controls. Listing deletion and a seller dashboard are separate later features.

Save is an explicit authenticated partial PATCH with pending/no-change prevention. Confirmed returned data updates the baseline and feedback; failures preserve edits without claiming success. A stale forbidden-state response disables mutation until you explicitly reload current state. Missing/non-owned records share safe feedback, and stale/ineligible sessions use existing auth handling. No dashboard or full-detail lookup is introduced.

All 148 backend tests passed against actual isolated PostgreSQL/disposable filesystem/controlled SMTP, including eight owner-edit DTO/state/partial-preservation/precision/protected-field/eligibility/commit-rollback/stale-race cases. All 63 frontend tests and build passed, including seven edit loading/retry/read-only/changed-only/validation/pending/error/forbidden-state cases. No dependencies or schema changes were needed; PostgreSQL stopped after verification.


## Review My Listings

Choose **My Listings** at /my-listings after verified sign-in. All or individual Active/Sold/Pending/Rejected/Removed status views load only your own records, newest creation first with descending id ties. Twenty-item Previous/Next controls use bounded owner-only pagination. Empty/load-error states are explicit and errors have retry. Pending waits for manual review; Rejected shows the reason and delete/recreate guidance; Removed has no readable thumbnail or edit link. Pending/Active/Sold link to the real price/description edit screen, and Create listing opens the existing form. Mark-sold, deletion, approval and buyer detail use the separate actions documented below.

Main thumbnails use Bearer-authenticated binary fetch and revoked blob URLs on changes/unmount; Removed images are not fetched or publicly exposed. GET /listings/mine accepts only strict limit/offset/status, defaults twenty/max fifty, and rejects owner spoofing or duplicate/unsupported query keys. Response totals/counts apply to the current owner and filter. See API notes for exact page/DTO/query bounds. The new-listing uncertainty path can now link to this real review screen without guessing whether an ambiguous upload succeeded.

All 154 backend tests passed with actual isolated PostgreSQL/disposable filesystem/controlled SMTP, including six owner/query/status/tie-sort/pagination/private-photo/session/dispatch cases. The route-order test checks the registered router directly and retains actual HTTP assertions, avoiding FastAPI included-router wrapper internals. All 69 frontend tests and build passed, including six dashboard loading/retry/empty/status/page/action/blob-cleanup/session cases. No dependencies or schema changes were required; test PostgreSQL stopped.


## Mark an Active listing Sold

On My Listings, an Active card offers Mark Sold, followed by Confirm Sold or Cancel. Confirmation calls the owner-only endpoint without state/owner fields. Pending controls prevent duplicate clicks; confirmed success reloads actual dashboard data. Failed/uncertain responses make no Sold claim and ask you to review/reload before retrying. Sold is retained privately, absent from Active, and no longer gives buyers photo access; your own photos remain readable. This action has no undo/reactivation and changes no item metadata, timestamps, reports or files.

All 160 backend tests passed with real isolated PostgreSQL/filesystem/SMTP, including six Sold transition/idempotence/concurrency/state/ownership/eligibility/stale-guard/rollback/preservation/privacy cases. All 71 frontend tests and build passed, including confirmation/cancel/pending/contract/success-reload/failure cases. No dependencies/schema changes; PostgreSQL stopped after verification.

## Scoped listing-photo cleanup recovery

A successful listing deletion may report `cleanup_pending: true` after its database commit. With the same configured database and `UPLOAD_DIR` as the application, an operator can retry only that absent listing's generated photo files:

```powershell
.venv/Scripts/python.exe -m backend.listing_cleanup 7 --confirm-listing-id 7
```

Replace both identifiers with the exact deleted listing id. The command refuses mismatched identifiers or a still-existing listing. It checks confinement under the upload root, rejects symlink/junction escapes, and removes only generated JPG/PNG/WebP filenames directly in that listing namespace. Unknown names, directories, other listing files and avatars are preserved; it performs no recursive directory deletion. Missing files count as completed cleanup. Failure prints a sanitized message and exits nonzero; inspect permissions/configuration and retry this same scoped command. This is an explicit operator action, not a background cleanup guarantee.

Protected marketplace browsing is available through `GET /listings` with the current Bearer access token. Its bounded limit/offset pages show only approved Active listings of eligible sellers, ordered by publication date and id descending. See the API notes for exact query/card contracts and sanitized statuses. Optional q keyword search is documented below; filters are documented below; the marketplace screen is documented below; listing details/contact are documented below; manual approval is unchanged.


The protected feed accepts optional q search text (at most 200 decoded characters before trimming, no control characters). Blank text browses normally; nonblank text matches a literal case-insensitive substring in title or description, retaining approved visibility, safe card fields and newest-publication ordering. URL-encode query text, including percent/underscore/escape characters, which match literally. No-result searches return empty pages. Unicode case comparison follows PostgreSQL configuration; there is no relevance ranking, stemming or accent-folding guarantee. React search/filter controls are documented below.

Disable raw request-target access logging with Uvicorn `--no-access-log`, as in the startup command above, and configure any reverse-proxy access logs to omit or redact query strings. Search text must not be recorded by infrastructure access logs; the service does not log or echo q, and SQL driver parameters remain hidden.


GET /listings also accepts category_id (canonical fixed id 1–5), condition (new/used), min_price and max_price. Price strings are exact unsigned decimals from zero to 1,000,000,000 with at most two meaningful fractional digits; no signs, exponents, whitespace, leading zeros or silent rounding. Bounds are inclusive and independently optional, with min_price <= max_price. All filters combine with AND and optional q, preserving approved visibility, publication/id ordering and filtered totals; duplicates/invalid/unknown values receive safe 422. See API notes for the complete contract. React filter controls are documented below.


After signing in, open /marketplace (also the signed-in Home/brand destination). Apply search/category/condition/inclusive KZT price filters with the labeled form, or Reset filters to browse again. Applied filters persist between twenty-item pages and reset to the first page when changed. Real cards show publication/date, category, condition, exact price and protected photo blobs; missing/error photos and empty/loading/retry states are honest. Malformed response/linkage is rejected, stale results cannot overwrite newer searches, and blobs are released on view changes/unmount. The neutral grid and wrapped controls support mobile and keyboard use. Listing titles now link to genuine protected details described below; student reports are documented below; admin controls remain separate tasks.


Click an approved marketplace title or open /listings/<positive-id> while signed in. Buyer details require Active/published/eligible-seller visibility even for the owner; private/missing records return the same unavailable state. The detail screen shows literal description text, exact KZT price, category/condition/publication and an ordered private-photo gallery. Main is selected first; keyboard photo buttons change selection, stale photos are ignored and blob URLs are released. Missing photos/contact or failed requests show honest feedback with retry.

Seller contact fields are revalidated on every detail read. Contact Seller prefers validated Telegram HTTPS, otherwise external HTTPS; valid international phone uses tel:. External new-tab links use noopener/noreferrer. University email/security flags/paths are absent. Arrange negotiation, payment and pickup directly with the seller; no platform chat/checkout action is supplied; student reporting is documented below. Desktop/mobile/keyboard gallery and contact behavior require independent browser QA.


On a visible listing detail page choose Spam, Prohibited items or Misleading information and explicitly Submit report. First/repeat submission returns generic accepted feedback; repeated reports preserve the original reason/time and concurrent repeats cannot create extra rows through the API. Own-listing reports are rejected, and private/ineligible targets are unavailable. Pending controls prevent duplicate clicks; uncertain responses show honest retry guidance without automatic replay. Reports are reason-only and do not automatically remove listings or send messages. Admin review/removal is a later task. The API notes document exact payload/status/identity and locking boundaries.


## Explicit administrator provisioning

First register the intended university account, complete real email verification and ensure it is unsuspended. With the configured application database, run from the repository root:

```powershell
.venv/Scripts/python.exe -m backend.admin --email existing@sdu.edu.kz
```

Supply the exact existing account email; normalization follows normal university-email rules. The command locks and promotes only eligible existing accounts, is idempotent, preserves passwords/profile/sessions and exits nonzero with safe output for refusal/configuration/database failure. It performs no default/automatic provisioning and imports never connect. It does not supply or expose any password.

Sign in or restore the account to receive current /auth/me is_admin capability. Confirmed admins see Admin navigation; /admin makes a fresh protected /admin/me check before rendering access confirmation. Direct ordinary-user access is denied honestly, while demotion takes effect immediately on the server and removes stale navigation after denial. Check errors offer retry without exposing admin content. Existing student auth behavior remains, with strict boolean capability validation in the updated browser. User review/suspension is documented below; listing review/removal is documented below; report review is documented below. Operator role changes and further admin features remain explicitly controlled.


## Admin user review and suspension

After explicit provisioning and sign-in, open Admin then Review users (/admin/users). The real twenty-account pages show only identity/role/verification/suspension/joined information. Current server admin authorization protects every list/read/change; ordinary or stale demoted users see an honest denial and no private rows. Self and admin accounts have no suspension controls.

Choose Suspend student or Unsuspend student, read its effect, then confirm or cancel. PATCH /admin/users/{id}/suspension accepts only a strict suspended boolean; actor/target locks are acquired by ascending id before fresh privilege/target checks. Suspension atomically revokes all target families and hides their buyer-facing listings without changing listing lifecycle/files. Unsuspension changes only the suspension flag, never verifies/promotes/restores sessions, and requires a new eligible login. Repeated calls are safe; self/admin targets are protected as an authorized default. Mutation failure/uncertainty requires explicit review/retry and is not automatically replayed. See API notes for exact paging/DTO/status contracts. Listing review/removal is documented below; report review is documented below.


## Admin listing review and removal

From Admin choose Review listings (/admin/listings). Real status views and bounded pages include Pending/Active/Sold/Rejected/Removed and suspended sellers. Open a listing for full text, necessary seller identity and ordered private photo review. Admin photos use separate /admin/listings/{id}/photos/{photo_id} routes and Bearer blob requests; no buyer/owner permission is widened and there is no public file mount. Missing/failed photos are honest and object URLs are released on gallery/view changes.

Remove listing prompts confirmation or cancellation. POST /admin/listings/{id}/remove accepts no fields, locks/rechecks the acting admin before the listing and changes only status to Removed, idempotently. Existing publication/metadata/files/reports remain intact for review; buyer feed/search/detail/photo visibility stops immediately. Confirmed persistence reloads actual detail state; uncertain responses require explicit review/retry and are never automatically replayed. Removal is separate from seller hard deletion and offers no restore or disk cleanup action; approval/rejection and report review use separate controls. See API notes for exact safe DTO/query/status contracts. Desktop/mobile/keyboard review/gallery/removal require independent browser QA.


## Admin report queue

From Admin choose Review reports (/admin/reports). The protected real queue defaults to Unreviewed, with Reviewed/All views, twenty-item pages and stable newest-created/id ordering. It shows only report reason/times and minimal listing status/review links; no reporter contacts, email or tracking surface. Removed listings stay linked to existing private review. Seller/listing hard deletion cascades reports out of the queue.

Mark reviewed explicitly calls POST /admin/reports/{id}/review without fields. Actor→listing→report locks and fresh server permissions protect a one-time trusted review timestamp; repeated/concurrent calls preserve it and return the same UTC instant. Review never removes/approves listings, and removal does not silently review reports. Pending controls prevent duplicates; confirmed action reloads the active filter and reconciles an emptied last page. Ambiguous failures require explicit reload/retry and never automatically replay or claim reviewed. See API notes for DTO/query/status contracts. Publication approval is documented below; no external admin message or reporter-tracking workflow is added.


## Manual Pending publication review

Provision/sign in as an eligible admin using the commands above, open Admin → Listing review, filter Pending and open a real listing. Approve listing opens confirmation/cancel; Confirm approval sends POST /admin/listings/{id}/approve without fields. Only Pending becomes Active, with its first trusted publication time; Active retries preserve it and other states cannot be revived. Approval requires a verified, unsuspended seller, including on retry. The approved listing appears in eligible student browse/detail/private-photo routes.

Reject listing opens a labeled 1–300 character reason and confirmation/cancel. POST /admin/listings/{id}/reject sends only the trimmed reason. Rejected records remain private and the seller's My Listings shows feedback and delete/recreate guidance. Identical rejection retries preserve feedback; different reasons or incompatible states conflict. Price/description edits of published records retain approval. Removal, report review and seller hard deletion remain distinct actions.

Pending controls prevent duplicate requests. Success reloads the authoritative detail; ambiguous/network/5xx/conflicting results require explicit review reload and never automatically replay a decision or claim publication. Server transactions lock actor/seller accounts in ascending id order before the listing and recheck live permissions/state. See API notes for safe responses, strict inputs, eligibility and retry semantics. Automated coverage includes real Pending creation/photo→approval visibility, rejection privacy, decision races/rollback and frontend confirmation/error/reload interactions; independent desktop/mobile/keyboard browser QA remains required.


## Permanent own-account deletion and scoped cleanup retry

Open Profile after verified sign-in, read Delete account permanently, then Delete my account. Enter the current untrimmed 12–128 character password and explicitly confirm or cancel. This permanently removes identity, contacts, sessions, owned listings/photos/reports and reports authored elsewhere. Admins have the same right; provision another verified admin first if administration must continue. No restore exists.

Confirmed DELETE /users/me success clears the refresh cookie and private browser auth/form state and shows public sign-in guidance. If cleanup_pending is true, account deletion already committed and image cleanup remains for an operator. Network/uncertain failure does not prove either outcome: the form does not repeat the request automatically; review through a fresh sign-in first. Wrong-password and validation errors permit correction without claiming deletion.

Before an operational deletion/recovery workflow, capture only the exact numeric account id and owned listing ids through authorized database review. No deleted personal account record is retained. To retry cleanup for absent account 123 and its previously captured absent listings 456 and 789, run from the configured repository root:

```
.venv/Scripts/python.exe -m backend.account_cleanup 123 --confirm-user-id 123 --listing-id 456 --confirm-listing-id 456 --listing-id 789 --confirm-listing-id 789
```

Use real captured ids, never example ids against arbitrary data. Both ordered listing-id lists must match; existing account/listing records cause refusal before any cleanup. Omit listing pairs only when retrying the absent avatar namespace alone. The helper uses generated direct image names and existing absence-checked listing recovery; it does not recurse/remove directories or touch unrelated files, and rejects junction/symlink escape. A nonzero result means retry is pending or refused; diagnostics are sanitized. Database and filesystem cleanup are not atomic: rows commit first, and disk/response interruption can leave orphan images. Keep configured storage and database available; never reset identity sequences to reuse deleted ids. No global service or scheduler is installed.

Automated coverage uses temporary image directories and dedicated disposable PostgreSQL for cascades/isolation, stale guards, current-password checks, admin self-deletion, rollback, missing files, cleanup failure/recovery, actual junction safety and races with login/refresh/listing/admin actions. Frontend tests cover explicit confirmation, pending prevention, safe failures, auth clearing and cleanup feedback. Independent desktop/mobile/keyboard browser QA remains required.


## Abuse-control and transport verification

Use the backend startup command with --no-proxy-headers and one process. The default limiter tracks at most 10,000 active hashed keys, prunes expiry and fails closed on capacity without dropping live counters. Registration:10/IP/hour; failed login:10/email-IP/15min; recovery:10/IP/hour; shared email requests:5/email/hour; refresh:60/IP/minute; create:10/user/hour; report:10/user/hour; uploads:30/user/hour. These are fixed windows with positive Retry-After, independent of whether an email/account exists. Registration/recovery IP attempts include rejected body validation. Successful login refunds only its own reserved slot. Existing code/cooldown/session protections remain enabled.

Counters are in memory: restarting clears them, workers do not share them, and proxy peers can group clients. Do not trust X-Forwarded-For or add workers while claiming globally enforced limits. Full details, stream limits, concrete regression matrix and remaining operator responsibilities are in [security.md](security.md). JSON writes count actual bytes up to 64 KiB; multipart upload counts five MiB plus framing and closes spools on abort. App buffering limits do not replace server/proxy connection, body and timeout controls.

Run the documented full dedicated PostgreSQL suite and frontend tests/build. tests/test_abuse.py includes low-level asyncio stream tests; Windows asyncio needs a local socketpair, so restricted environments must allow controlled loopback execution. Existing specialized validation tests may inject fresh finite limiter stores to isolate each input case; abuse tests exercise real limits without disabling them. No external email is sent by tests. Real SMTP credentials/inbox delivery and deployed HTTPS/TLS/proxy behavior remain unverified; no dependency scan or all-clear security guarantee is claimed.
