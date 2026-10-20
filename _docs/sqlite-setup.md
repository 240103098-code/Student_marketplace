# Durable local SQLite — current default (2026-10-20, issue #44)

Fresh development uses the real FastAPI backend and a repository-relative SQLite file. This new choice supersedes the earlier PostgreSQL-only/deferred-SQLite assessment. Explicit PostgreSQL remains supported, with its original migration history; explicit volatile memory remains available. Existing `.env`/DATABASE_URL, databases, images and provider credentials are never converted/reset automatically. This is separate from frontend synthetic mock mode.

## Fresh start without PostgreSQL

Install Python/frontend dependencies from [local setup](local-setup.md). From the repository root, create `.env` only if absent, using the existing placeholder-replacement command in that guide; never overwrite an existing file. The current `.env.example` selects `sqlite+pysqlite:///backend/data/marketplace.sqlite3`. If DATABASE_URL is absent in development/test, the same ignored default is used. JWT_SECRET_KEY remains mandatory and must be independently generated; SMTP credentials remain private operator setup. Existing explicit PostgreSQL `.env` continues to use PostgreSQL.

```powershell
.venv/Scripts/python.exe -m alembic -c alembic-sqlite.ini upgrade head
.venv/Scripts/python.exe -m alembic -c alembic-sqlite.ini current
.venv/Scripts/python.exe -m backend.database check
.venv/Scripts/python.exe -m uvicorn backend.main:create_runtime_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

No server/SQLite CLI/extra driver is needed. Metadata `create_all` is **not** the persistent migration strategy: use the separate Alembic `sqlite_0001` head and `alembic_version_sqlite`. Running `upgrade head` again preserves existing rows/files and the five categories. The PostgreSQL `alembic.ini`/0001–0003 stream rejects SQLite; the SQLite stream rejects PostgreSQL/memory. Do not stamp incompatible versions or point migrations/downgrade at data you need to preserve. Future SQLite changes require new revisions rather than editing the initial snapshot.

In another terminal, `cd frontend`, set `$env:VITE_SERVICE_MODE='real'` and `$env:VITE_API_ORIGIN='http://127.0.0.1:8000'`, then `npm run dev`. Keep FRONTEND_ORIGINS=`["http://127.0.0.1:5173"]` and use the same host consistently. Stop your own services with Ctrl+C; do not terminate an already running user's preview. On restart the same file/root preserve users, verification records, refresh families/revocations, listings, prices, photos, moderation and reports. JWT signing secret must also remain stable to retain sessions. No users/admins/demo listings/fake codes are seeded. Register/verify via configured SMTP, then promote an existing verified eligible account locally:

```powershell
.venv/Scripts/python.exe -m backend.admin --email YOUR_EXISTING_VERIFIED_SDU_ADDRESS
```

Normal SMTP still requires verified TLS/STARTTLS and complete host/port/username/password/from fields. Missing/failed SMTP gives safe 503 and rolls back issuance. No console code fallback or public admin-role endpoint exists. Controlled protocol tests do not prove delivery to a live university inbox.

## File URLs, uploads and transaction limits

Only `sqlite+pysqlite` local file URLs are supported, plus exact `sqlite+pysqlite:///:memory:`. Relative file paths resolve against the repository, independent of current directory. Windows absolute example: `sqlite+pysqlite:///C:/your-local-folder/marketplace.sqlite3`; spaces are supported. Host/credentials, UNC/network shares, URI/query parameters, fragments and drive-relative `C:...` paths are rejected. Parent directories may be created, but startup/check never overwrites a file or silently creates application schema. A wrong/incompatible existing schema fails migrations with rollback; it is never stamped/reset. The ignored default `backend/data/` includes its `-wal`/`-shm` companions; keep any custom path out of Git too.

Persistent UPLOAD_DIR defaults to `backend/uploads` and survives shutdown; it is never passed to memory temporary-directory cleanup. Keep the database and corresponding upload root together in backups/restores. Existing scoped postcommit image deletion and partial-file rollback cleanup continue to apply. Do not point a disposable test/demo at user files.

Every file connection enables foreign keys, WAL and a 1500 ms busy timeout. Driver autocommit is disabled and SQLAlchemy transaction begin sends **BEGIN IMMEDIATE before caller guard reads/time checks**. This coordinates independent connections/processes; a process mutex alone or SQLite SELECT FOR UPDATE would not. Current account/role/session/state/UTC are rechecked after waiting. Complete transactions include SMTP/Argon2/image work where existing services require it, so writes are serialized and even guarded reads reserve the writer. Expect bounded contention under load: exhausted BUSY/LOCKED returns sanitized 503 with Retry-After: 1, rollback and no automatic mutation replay. Confirm current state before any explicit retry. SQLite WAL permits independent raw readers, but this application's guarded transactions intentionally reserve a writer early. Local single-writer storage, OS-file access and the process-local limiter are not a distributed production architecture; SQLite production requires explicit configuration and existing HTTPS/cookie/JWT safety. Memory remains forbidden in production.

Shared SQLite types retain integer generated ids, UUID lineage, UTC-aware values and exact integer-cent KZT conversion/checks. Native PostgreSQL types/checks/row locks and reconnect-after-dispose behavior remain. File disposal closes connections and can reopen preserved schema; memory disposal stays terminal. Search/collation limitations from [memory storage](memory-backend.md) apply; no universal cross-collation identity is claimed.

## Backup and safe reset

Stop only your own backend/writers before a manual maintenance backup. Do not copy only the main file while a WAL writer is running. Python's standard-library backup API makes a coherent copy; the following example refuses an existing destination and closes both connections:

```python
from contextlib import closing
from pathlib import Path
import sqlite3
from sqlalchemy.engine import make_url
from backend.config import load_settings
settings = load_settings()
url = make_url(settings.database_url.get_secret_value())
assert url.drivername == 'sqlite+pysqlite' and url.database != ':memory:'
source = Path(url.database)
assert source.is_file()
destination = source.with_suffix('.backup.sqlite3')
assert not destination.exists(), 'Preserve existing backup'
with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as source_db:
    with closing(sqlite3.connect(destination)) as backup_db:
        source_db.backup(backup_db)
```

Also back up the configured upload root and private configuration securely. To start a clean development dataset, keep the backup/old data, explicitly select a **new unused** local DATABASE_URL and a separate new UPLOAD_DIR in your own terminal, then upgrade the SQLite stream. No automatic/destructive reset helper is provided. Downgrade/re-upgrade is tested only on newly owned disposable files; it deletes application tables and is not a routine update/backup step.

## Reproduce tests and real frontend restart flow

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_sqlite_persistence.py -v
.venv/Scripts/python.exe -m tools.sqlite_demo --confirm-disposable-demo student-marketplace-sqlite-demo --browser-executable "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
.venv/Scripts/python.exe -m tools.export_openapi --check
```

Use your installed compatible browser path or omit the argument only when pinned Playwright Chromium is installed, as in the demo prerequisites. The confirmed SQLite smoke always creates its own temporary file/uploads/build, selects unused loopback ports, and uses real React production build/FastAPI services plus loopback SMTP protocol transport. It stops the owned Uvicorn server, creates a new app/Database against the same file, and reloads the existing buyer page to verify persisted detail, image and contact; separate-process tests independently verify stored records and operator CLI. It never contacts external inboxes or attaches to an existing user's database/server/preview. Only its owned disposable directory is removed after owned services stop. [Evidence](evidence/sqlite-persistence/demo-result.json) records stages and request counts; [verification](evidence/sqlite-persistence/verification.txt) records backend/frontend results. The complete guarded PostgreSQL + memory + file-SQLite suite still requires the PostgreSQL setup in local setup; skipping PostgreSQL is not a complete pass. The broader cross-mode matrix remains issue #53.
