# Offline SQLite в†’ PostgreSQL migration (#58)

`python -m backend.migrate_storage` is an explicitly selected, backup-first offline operation. It never chooses your default `.env`, database or uploads automatically. This is tooling verified on disposable data, **not authorization to migrate a user's private installation or perform hosted cutover**. Keep both applications stopped throughout planning, copying, verification and operator cutover. No external email is sent by this tool.

## Prepare an offline source and empty target

Use absolute paths without symlinks, junctions, relative/dot segments or overlapping source/backup/destination roots. Select a named `.sqlite3`, `.sqlite` or `.db` file at published `sqlite_0001`, and its actual uploads root. Before stopping the source, the operator may explicitly checkpoint their authorized source with `PRAGMA wal_checkpoint(TRUNCATE)`; close **every** application/SQLite connection afterwards. The migration never checkpoints or opens source writable. It refuses any `-wal`, `-shm` or `-journal` sidecar, even empty, instead of silently ignoring WAL rows. Do not delete sidecars to force acceptance: recover/checkpoint through SQLite with the app stopped. Read-only immutable opening is used only after these checks and explicit quiescence; source file hashes are rechecked. No tool can make a source safe while an unauthorized concurrent writer is still changing it.

Create a separate empty PostgreSQL database through your normal administrator process. Privately configure DATABASE_URL/JWT_SECRET_KEY for the existing Alembic command, without placing credentials in command arguments or shell history. Then:

```powershell
.venv/Scripts/python.exe -m alembic -c alembic.ini upgrade head
```

This is preparation, **not part of dry-run**. The tool never drops tables, migrates schema, creates a database or merges/upserts data. It requires actual current_database to match the selected URL database and supported PostgreSQL `0003_listings` schema. Public columns/defaults/PK/FK/unique/check/index definitions are compared with the data-free canonical signature derived from unchanged published migrations on PostgreSQL18.6; unexpected tables/views/materialized views/sequences/user triggers are refused. Only exact five category seeds and PostgreSQL Alembic metadata may exist. Earlier unsupported/custom schemas need a separately reviewed compatibility plan, not editing the signature to bypass refusal.

The destination uploads root and backup root must be **new absent paths**, with existing safe parent directories. They must not overlap source/database/uploads or one another. Use operator-controlled private storage: backups contain account/contact data, hashes and private images. Choose a location outside version-controlled/build-context directories. Restrict filesystem permissions/Windows ACLs, encrypt and retain backups under your policy. POSIX backup directory/file modes are700/600; Windows ACL protection remains an operator responsibility.

## Plan, execute and verify

Set `MIGRATION_TARGET_DATABASE_URL` privately to the explicitly prepared PostgreSQL URL. The tool reads only that environment variable for target credentials; it never prints the URL or passwords. In the examples replace `/absolute/...` with your actual absolute path (Windows: `C:/owned/...`). Do not point at a private/user database without separate authorization.

```powershell
.venv/Scripts/python.exe -m backend.migrate_storage --dry-run --source /absolute/source/marketplace.sqlite3 --source-uploads /absolute/source-uploads --destination-uploads /absolute/new-pg-uploads --backup /absolute/new-private-backup --source-quiesced
```

Dry-run validates a read-only consistent source snapshot/schema/integrity/FKs, exact fixed categories, referenced image ownership/paths/size/hash and an empty supported target. It performs no persistent database/file/data writes, creates no backup/staging/destination and emits only mode/status/table counts/file count. It may build a temporary **in-memory** reference schema for comparison. Reading may update ordinary OS access timestamps; database/image bytes are unchanged. Backup destination does not become a backup until execute succeeds through its verified-backup stage.

```powershell
.venv/Scripts/python.exe -m backend.migrate_storage --execute --source /absolute/source/marketplace.sqlite3 --source-uploads /absolute/source-uploads --destination-uploads /absolute/new-pg-uploads --backup /absolute/new-private-backup --source-quiesced --confirm-source marketplace.sqlite3 --confirm-target prepared_database_name
```

Confirmation repeats the exact selected source filename and target database name; absolute source/target/upload selections remain explicit. No JWT secret is needed by the copy tool: it preserves stored values verbatim. For the migrated application to accept existing code HMACs, CSRF tokens, access JWTs and refresh sessions, retain the **same original JWT/code-digest key**, issuer/audience/lifetimes, origins and cookie settings. Never generate a replacement continuity key, print it, put it in CLI arguments or ask the migration to rewrite hashes. Expiry/revocation/attempt counts remain unchanged and clocks keep running during maintenance.

Read-only acceptance or crash reconciliation:

```powershell
.venv/Scripts/python.exe -m backend.migrate_storage --verify --source /absolute/source/marketplace.sqlite3 --source-uploads /absolute/source-uploads --destination-uploads /absolute/new-pg-uploads --backup /absolute/new-private-backup --source-quiesced
```

Verify uses the selected **private backup** and journal, never guesses from a successful-looking destination directory. It checks backup schema/content/manifest, target schema/row counts/canonical content, exact unconsumed sequence next values and destination marker/file hashes in a read-only PostgreSQL snapshot. Source arguments remain explicit CLI selections but verify reads the retained backup, so original source can remain securely offline. It reports `committed-and-verified`, `target-empty`, or `target-empty-owned-files-retained`; a different/nonempty/partially edited target fails closed. Do not run the target app before acceptance; new records legitimately change the exact migration fingerprint.

## Exact ordering and recovery boundaries

1. Validate the source and manifest. Begin a bounded PostgreSQL transaction, acquire exclusive locks on all seven application tables plus its Alembic metadata **before the first snapshot read**, and revalidate empty target/schema. Statement timeout10s and lock timeout3s fail closed. Database selection is checked on the actual connection. The source stays in one immutable read snapshot.
2. Create the new private backup directory. Use SQLite's backup API to make `source.sqlite3`, reopen it read-only and verify canonical rows/schema; copy only manifest-listed image files to `backup/uploads` and verify hashes. Store a private atomic `recovery.json` journal. Source orphans are preserved in source and are not silently copied as public/private application references.
3. Create an exclusively owned sibling staging directory, marked by a random `.migration-owner`. Copy from verified backup, recheck source/stage bytes, insert preserved IDs/typed values. Refresh rows are first inserted with null self-links, then exact UUID predecessor/successor links restored in the same transaction. Every row is compared using a canonical digest; native FKs/checks/unique constraints remain enabled. Category seeds are verified, not reinserted. Dialect-specific Alembic rows are never copied.
4. Restart the five numeric-ID PostgreSQL sequences at max(id)+1 transactionally with ALTER SEQUENCE (not nontransactional setval), verify last_value/is_called, and reject exhausted BIGINT IDs. Check source bytes again. Persist `publishing-before-db-commit`, rename only this owned staging directory to the previously absent destination, verify all destination hashes, recheck source sidecar absence immediately before commit, then attempt database commit. A newly appeared WAL/journal/SHM file or link causes refusal and is preserved for source recovery. Persist committed state only after commit acknowledgment. File fsync/atomic journal replacement and POSIX directory fsync improve crash durability; this is **not** a global PostgreSQL/filesystem transaction or a guarantee against arbitrary hardware failure.
5. A known failure **before commit attempt** rolls the DB transaction back and deletes only this run's marked files/empty directories; unknown files/links or ownership mismatch instead preserve artifacts and request reconciliation. Backup/source are retained. A crash after publish/before commit can leave owned destination files with an empty target. An exception during/after commit acknowledgment can mean the database already committed: preserve published files and mark `commit-outcome-unknown-reconciliation-required`, never delete possibly live images on a guess.

Keep both apps stopped after any failure. Inspect the **private** journal and run verify. If committed-and-verified, retain files and take normal target backup before cutover. If target-empty with retained staging/destination files, preserve those artifacts for investigation and choose fresh absent backup/destination names for a new explicitly confirmed execute; no automatic resume/cleanup is claimed. The old target must still validate empty. If rows differ or files are missing, stop and reconcile using the verified backup and qualified operator review; never drop/merge/reset the target to make a rerun pass. A journal says which paths/run owns, not that a commit succeeded. Do not use recursive shell delete/move commands against an inferred path.

## Cutover and rollback

After verify reports committed-and-verified, point the stopped application's private DATABASE_URL/UPLOAD_DIR at the confirmed PostgreSQL database/published uploads while retaining the continuity key and auth/origin/cookie configuration. Start it with the existing documented runtime command, check real login/current eligibility/refresh and protected images, and only then reopen writes. This tool does not edit `.env`, start services or perform that cutover.

Before target writes are accepted, rollback is simply leaving target offline and restarting the original unchanged SQLite app with its original uploads/config. To prove a restore, copy `backup/source.sqlite3` and manifest-listed backup images to a **new authorized** location and use that copy; do not overwrite the original source or run a writable app directly on the only backup. After new PostgreSQL writes, reverting to old SQLite would lose them: a separate reviewed data reconciliation/recovery plan is required. No automatic reverse migration is promised.

## Verified scope and limits

[Observed implementation verification](evidence/storage-migration-58/verification.md):307 actual backend tests passed with zero skips, including13 migration/recovery cases. Independent exact-commit QA/publication is recorded in GitHub58.

Every account/code/refresh/category/listing/photo/report row is retained, including expired/revoked/suspended/unverified history, all five listing states, review/rejection/publication details, Unicode text, contacts, exact KZT Decimal cents and UTC microseconds. Public output omits row/content hashes and personal paths; those sensitive details stay only in the private backup journal. File manifests use only generated owner/listing image namespaces, reject traversal/symlink/junction/escape/duplicate/missing/changed bytes, and never mount private images as static files.

Limits are100,000 rows **per table**,128MiB per stored image,1GiB referenced images total. Reads apply the row bound before materialization. Stored canonical image bytes can legitimately exceed the5MiB incoming upload limit, so migration uses a separate stored-file budget and preserves bytes exactly. Larger migrations need a separately reviewed bounded strategy. Quiescence/maintenance time must include backups, full hashing and copying; codes/sessions can naturally expire meanwhile. This is one local migration utility, not cloud/Compose/readiness/fullE2E work. No new dependencies or application/migration-schema behavior changes are required.
