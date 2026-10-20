# Real volatile FastAPI backend (issue #51)

This development/test mode runs the **existing FastAPI API and business services**, backed by one real SQLite `:memory:` SQLAlchemy connection per `Database` instance. It is separate from `VITE_SERVICE_MODE=mock`: use frontend `real` mode to call it. PostgreSQL remains the established persistent configuration. File-backed/default SQLite and its migration stream remain issue #44; published PostgreSQL Alembic revisions are unchanged.

## Start, check, reset and stop

Install `requirements-dev.lock` and frontend dependencies following [local setup](local-setup.md). No database server or new Python dependency is required for memory mode. In a dedicated PowerShell terminal at the repository root, explicitly select:

```powershell
$env:APP_ENV='development'
$env:DATABASE_URL='sqlite+pysqlite:///:memory:'
$env:JWT_SECRET_KEY = .venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
$env:FRONTEND_ORIGINS='["http://127.0.0.1:5173"]'
.venv/Scripts/python.exe -m backend.memory
```

The local operator console starts the normal API at `127.0.0.1:8000`. `check` checks **this same app's** database. `promote your-existing-verified-address@sdu.edu.kz` invokes the existing operator provisioning CLI against this app's injected Database: it only promotes an already verified, unsuspended university account. It does not create an account, activate one, disclose verification codes or expose a public role endpoint. A separate `python -m backend.admin` process cannot access another process's volatile database. The console accepts only these commands; it does not evaluate Python expressions. `stop` or Ctrl+C shuts down the API, disposes the connection and removes its owned temporary images. Start again to reset all records, limiter state and images; five fixed categories are seeded afresh, no users/admins/demo listings are seeded. Never run Alembic/stamp against memory storage.

For an API without the operator console, run the usual factory instead:

```powershell
.venv/Scripts/python.exe -m uvicorn backend.main:create_runtime_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

`python -m backend.database check` also accepts this configuration, but checks a **new separate empty** memory database and exits; it cannot inspect the running API. Production rejects memory configuration, including a factory call with bypassed Settings validation.

In the frontend terminal set `VITE_SERVICE_MODE=real`, `VITE_API_ORIGIN=http://127.0.0.1:8000`, and run `npm run dev` as documented in local setup. Keep the same `127.0.0.1` host for cookies/origins. Do not start a second server on an already occupied port; stop your own frontend with Ctrl+C before changing its mode. Tokens remain in frontend memory and normal cookie/CSRF checks apply.

## Email and temporary files

Normal runtime still requires your configured SMTP provider host/port/username/password/from fields and verified TLS/STARTTLS; the console does not offer a mail bypass or print codes. Existing ignored `.env` settings are read normally, with the explicit environment above taking precedence. Do not overwrite an existing `.env`, copy provider credentials into docs, or use dummy secrets. Missing SMTP permits startup but registration returns safe 503 and rolls back both account and code. Operator credentials and real-inbox delivery are external setup, not verified by controlled tests.

An app which constructs its own memory Database allocates a new `TemporaryDirectory`, uses it instead of caller `UPLOAD_DIR`, and cleans only that directory at shutdown. It never recursively deletes a configured caller directory. Injected databases/files are caller-managed (tests must supply their own isolated root and dispose it). Existing image decoding, confinement and failed-transaction file cleanup apply; abrupt process termination may leave an OS temporary orphan, which is not automatically discovered/deleted on another startup. Normal shutdown must finish pending requests before resource cleanup. No user checkout, persistent PostgreSQL data or source assets are touched.

## Storage and concurrency guarantees

Explicit Database construction imports shared metadata, creates SQLite tables and seeds the five categories once. Imports alone do not read configuration/connect/create files. SQLite foreign keys are enabled for its connection; UUID defaults, regex checks, bounded strings/booleans and fixed categories have SQLite equivalents. Generated bigint IDs use SQLite INTEGER primary keys. Timezone-aware inputs are normalized to UTC on storage and return aware UTC values, including server-created timestamps; naive ORM timestamp inputs are rejected. SQLite stores money as integer cents, converts to exact Decimal at the ORM boundary, and rejects nonfinite/out-of-range/excess-precision values rather than rounding. SQLite search lower() uses Python Unicode lowercasing; PostgreSQL ILIKE retains the database's collation behavior, so no universal cross-collation equivalence is claimed. Native PostgreSQL BIGINT/UUID/timestamptz/NUMERIC and checks are retained; existing PostgreSQL monetary coercion behavior is not rewritten.

`StaticPool` and `check_same_thread=False` share one connection across request threads. A process-local mutex surrounds the **whole** `Database.session()` unit: acquisition precedes reads/rechecks, and release follows commit or rollback and close. Waiting services read current eligibility/credentials and obtain current time after acquisition. This serializes transactions (including SMTP/image work inside them); SQLite `SELECT FOR UPDATE` provides no row-lock guarantee. PostgreSQL keeps its existing row locks/pool behavior. Do not nest memory sessions or bypass this interface with concurrent engine/session_factory access. Separate apps/processes have isolated records, secrets, sessions, rates and files; multiple workers, reload preservation, distributed rate limiting or production use are unsupported.

## Reproduce verification

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_memory_backend.py -v
.venv/Scripts/python.exe -m tools.export_openapi --check
cd frontend
npm run test -- --run --maxWorkers=2
npm run typecheck
cd ..
node tools/check_frontend_build.mjs
```

The memory tests use the real stdlib SMTP/MIME sender with an explicitly injected **loopback-only protocol test transport**; production TLS remains covered separately. They never contact external inboxes, print code/credential evidence, replace API authentication with JS mocks, or disable quotas. Coverage includes register/verify/login/contact/avatar/listing/photos/approval/discovery/report/review/removal/cascades, actual concurrent verification attempts/one-time consumption, refresh rotation/replay revocation, five photo slots, publication/suspension and stale credential/session checks, UTC/decimal/ORM constraints, rollback, app isolation and shutdown/reset. The full guarded real-PostgreSQL suite remains required as in local setup; absence of TEST_DATABASE_URL and skipped integrations is not a full pass. [Verification record](evidence/memory-backend/verification.txt) records the exact checks for this iteration.
