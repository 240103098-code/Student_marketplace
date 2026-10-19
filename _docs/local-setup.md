# Fresh-checkout local setup

## Implemented status and tested prerequisites

The React/FastAPI/PostgreSQL MVP implements student-only verification, session-bound JWT authentication, profile/contact/avatar management, listing/image workflows, search/filter/detail/contact, reports, admin user/listing/report moderation and manual publication decisions, permanent account deletion and finite abuse controls. See [API](api.md) and [security boundaries](security.md) for exact contracts. The [40-task backlog](tasks.md), plan and history retain their original scope.

Tested on Windows with Python **3.13.15**, Node **24.19.0**, npm **12.2.0**, PostgreSQL **18.6**, Playwright **1.62.1** and Edge **155.0.4283.45**. Python 3.11+ and frontend manifest-supported Node versions are supported; use the tested versions for reproduction. Install PostgreSQL binaries including initdb/pg_ctl/createdb, without needing a global service. Browsers are an explicit optional smoke prerequisite below. Loopback sockets and a writable temporary directory are necessary, including for Windows asyncio tests.

## Install pinned dependencies

From a clean checkout of https://github.com/240103098-code/Student_marketplace:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock
New-Item -ItemType Directory -Force .venv/tmp | Out-Null
$env:TEMP = (Resolve-Path .venv/tmp).Path
$env:TMP = $env:TEMP
cd frontend
npm ci
npm run test -- --run
npm run build
cd ..
```

Use `.venv/bin/python` on Linux/macOS. Activation is optional. The resolved Python export and npm package-lock are committed. Playwright is pinned as a development dependency solely for the optional browser smoke, with playwright-core resolved in the lockfile; it is not an application runtime dependency. The environment used for verification had Node on PATH and workspace-local npm invoked as `node ../../npm-runtime/package/bin/npm-cli.js` from frontend; ordinary operators use installed npm as above.

For smoke, either install its pinned Chromium browser (`cd frontend; node node_modules/playwright/cli.js install chromium; cd ..`) or supply an installed compatible Edge/Chrome executable explicitly. Browser downloads/system browser installation are prerequisites, never silently skipped as a passing demo.

## Configure a normal development instance

Do not use a production or shared database for tests. Create a dedicated development database through your own PostgreSQL administration, then copy `.env.example` to ignored `.env`. Refuse to overwrite an existing file; generate the JWT secret locally without printing it:

```powershell
.venv/Scripts/python.exe -c "from pathlib import Path; import secrets; p=Path('.env'); assert not p.exists(), 'Preserve existing .env'; p.write_text(Path('.env.example').read_text().replace('REPLACE_WITH_A_PRIVATE_RANDOM_SECRET_AT_LEAST_32_CHARACTERS',secrets.token_urlsafe(48)))"
```

Edit DATABASE_URL to your own PostgreSQL connection, replace SMTP placeholders only with provider-issued credentials and keep them out of Git/logs. Use **one hostname consistently**: for example backend `http://127.0.0.1:8000`, frontend `http://127.0.0.1:5173`, FRONTEND_ORIGINS=`["http://127.0.0.1:5173"]` and VITE_API_ORIGIN=`http://127.0.0.1:8000`. Set VITE_API_ORIGIN before building/serving React. Environment overrides `.env`, which overrides safe nonsecret defaults; configuration errors redact values. Relative UPLOAD_DIR resolves against the repository root.

APP_ENV=development permits loopback HTTP/non-Secure cookies; HttpOnly and SameSite=Lax remain mandatory. Production requires HTTPS frontend origins and Secure cookies. The SMTP sender requires all host/port/username/password/from fields, verified TLS or STARTTLS before authentication and bounded timeouts. Missing/failed SMTP rolls back issuance. It never falls back to console codes or plaintext production delivery.

```powershell
.venv/Scripts/python.exe -m backend.database check
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn backend.main:create_runtime_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

In a second terminal, `cd frontend`, set `$env:VITE_API_ORIGIN='http://127.0.0.1:8000'`, then `npm run dev`. Open http://127.0.0.1:5173. Stop both foreground services with Ctrl+C. Migrations create account/code/session and fixed five-category/listing/photo/report tables. Never run downgrade against data you want to preserve. OpenAPI is at the backend `/docs`; sensitive HTTP request bodies/tokens must not be logged. Keep one application process for the documented local limiter and disable trusted proxy header rewriting.

Register/verify through your own configured provider before using protected features. To provision an existing verified, unsuspended account locally:

```powershell
.venv/Scripts/python.exe -m backend.admin --email YOUR_EXISTING_VERIFIED_SDU_ADDRESS
```

The CLI grants current DB admin role only; no public role-edit endpoint exists. Sign in/restore the browser to see Admin. Pending listings remain buyer-private until explicit approval; rejection feedback is private to owner/admin. Admins can delete their own accounts, so provision another eligible admin first if continuity is required.

## Complete automated backend verification

The default unittest command skips real PostgreSQL classes when TEST_DATABASE_URL is absent; that is **not** the full verification. For full coverage use a fresh dedicated loopback database whose name begins `student_marketplace_test_` and exactly matches TEST_DATABASE_CONFIRM. The database must contain no application tables at entry; fixtures migrate/clean/downgrade their own test schema. Do not point at your development database.

Example first-time dedicated test cluster on Windows (set the PostgreSQL bin path for your installation). This initializes only a new workspace directory and refuses an existing one:

```powershell
$pgBin = 'C:/path/to/PostgreSQL/18/bin'
$testData = Join-Path (Get-Location) '.venv/pg-test-data'
if (Test-Path -LiteralPath $testData) { throw 'Preserve existing cluster; review its ownership before reuse.' }
& "$pgBin/initdb.exe" -D $testData -U marketplace_test -A trust --encoding=UTF8 --no-locale
& "$pgBin/pg_ctl.exe" -D $testData -l .venv/tmp/postgresql-test.log -o '-h 127.0.0.1 -p 55434' -w -t20 start
& "$pgBin/createdb.exe" -h 127.0.0.1 -p 55434 -U marketplace_test student_marketplace_test_local
$env:TEST_DATABASE_URL = 'postgresql+psycopg://marketplace_test@127.0.0.1:55434/student_marketplace_test_local'
$env:TEST_DATABASE_CONFIRM = 'student_marketplace_test_local'
try { .venv/Scripts/python.exe -m unittest discover -s tests -v; $testExit = $LASTEXITCODE }
finally { & "$pgBin/pg_ctl.exe" -D $testData -w -t15 stop }
if ($testExit -ne 0) { throw 'Backend tests failed' }
```

Choose an unused dedicated loopback port. Local trust applies only to this synthetic isolated test cluster. Keep its path/name and reuse only after verifying ownership and empty application tables; never reset an arbitrary existing cluster. Linux/macOS use the corresponding binaries without `.exe` and their normal non-root PostgreSQL account requirements.

The final complete run passes **261 backend tests** (full run plus corrected targeted contract check; zero skips), including actual PostgreSQL/filesystem and controlled loopback SMTP. Frontend passes **157 tests** and build. Detailed commands/results are recorded in [demo verification](demo.md); controlled SMTP messages are held only in fixture memory, without any external mail. Windows low-level asyncio needs permission for its local socketpair.

## One-command real-stack smoke

After pinned dependencies, PostgreSQL binaries and a browser are installed, run the [documented smoke command](demo.md). It generates a fresh private cluster, runtime secrets, migrations/seeds, uploads and local SMTP fixture; builds React for its actual API origin; drives the real browser and tears down its own services/data. It does not read/overwrite `.env`, attach to a supplied database or install global services. Confirmation is mandatory and missing prerequisites fail rather than skip.

## Scoped cleanup and limitations

Owner listing/account deletion commits DB cascades before confined image removal; success may truthfully report cleanup_pending. Capture only exact numeric account/owned listing ids in an authorized operational workflow before deletion; no personal recovery record is retained. Retry only confirmed absent namespaces:

```powershell
.venv/Scripts/python.exe -m backend.listing_cleanup 456 --confirm-listing-id 456
.venv/Scripts/python.exe -m backend.account_cleanup 123 --confirm-user-id 123 --listing-id 456 --confirm-listing-id 456
```

Replace examples with exact captured ids. Existing records or mismatched confirmations are refused; generated direct filenames only, no recursive directory removal or junction/symlink escape, unrelated files preserved. Do not reset identity sequences to reuse deleted ids. See API notes for filesystem/database atomicity and ambiguity handling.

The process-local limiter tracks at most 10,000 active hashed keys, fails closed at capacity and clears on restart; workers do not share quotas. [Security notes](security.md) enumerate exact limits, request bounds, role/state evidence and production proxy/TLS responsibilities.

**No production deployment or distributed guarantee is claimed. Live external university-inbox delivery remains unverified.** Supply a real provider securely and intentionally register your own university inbox to perform that separate operator check. Local protocol SMTP success does not prove provider/inbox delivery, encrypted transport or production readiness. Backlog/history archives and the established plan remain preserved.

The source/reference and target shell inspection commands for the separate Lovable visual integration are recorded in [lovable-integration.md](lovable-integration.md). Real API mode and the setup above remain the default; no new runtime dependency or provider is needed for the shared shell.

Student route visual coverage and fresh real-stack screenshots are documented in [student-screens.md](student-screens.md). For resource-constrained verification use `npm run test -- --run --maxWorkers=2`; this runs every frontend case without changing assertions/timeouts or skipping cases.

Admin route visual coverage, confirmation focus checks and fresh desktop/mobile real-stack evidence are documented in [admin-screens.md](admin-screens.md).

## Frontend-only demo, contracts and final integration

[Final integration instructions](integration-contracts.md) separate explicit VITE_SERVICE_MODE=mock development from default real FastAPI mode. The mock banner and controls never appear in production builds. Use synthetic credentials only; full reload/reset clears the in-memory demo. Run `npm run typecheck`, `python -m tools.export_openapi --check` and `node tools/check_frontend_build.mjs` for the additional declaration/schema/production-isolation checks. TypeScript7.0.2 is pinned as a development-only compiler.

If npm is missing from PATH in this workspace, from frontend use `node ../../npm-runtime/package/bin/npm-cli.js ci` (or run/test/build/typecheck) **only when that existing workspace-local npm file is present**. It is a local prerequisite, not part of this Git checkout. On another clean machine install the manifest-supported Node version and npm12.2+ first; alternatively invoke your installed npm-cli.js with the full path to node.exe. Python activation is optional: always use `.venv/Scripts/python.exe`. To run frontend without npm after installation, use the direct node/Vite command in the integration guide. Stop Vite/test processes before clean npm ci on Windows to release native-module locks. Ctrl+C stops servers; do not terminate unrelated previews.

Source integration is an adaptation with no automatic Lovable synchronization. No Supabase or SQLite switch was added. Local protocol SMTP remains separate from intentional operator verification of real university-inbox delivery.

The explicit mock catalog now includes the six original user-supplied product photos; see [photo provenance](mock-original-photos.md). These local demo assets do not seed the real PostgreSQL marketplace.
