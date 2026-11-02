# SQLite -> PostgreSQL implementation verification (2026-11-03)

**PASS:307 backend tests, zero skips,148.390s**, including13 new actual migration scenarios. [Machine record](verification.json) contains exact versions, scenario names and tested-code SHA256 values (CRLF normalized to LF, matching Git text canonicalization). The final exact implementation/QA SHA is recorded in [issue58](https://github.com/240103098-code/Student_marketplace/issues/58); this is implementation evidence, not self-certified independent QA/publication.

Python3.13.15, SQLite3.50.4, SQLAlchemy2.1.4, Alembic1.20.0 and actual PostgreSQL18.6 were used. PostgreSQL ran only on dedicated loopback test port55434 with the existing guarded disposable test database; it was stopped in finally. Each fixture owned a new SQLite file, source uploads, backup and destination in a temporary directory and removed them at completion. No user private checkout/database/SMTP/preview or original source repo was accessed.

Reproduce from repository root after [guarded PostgreSQL test prerequisites](../../local-setup.md), with TEST_DATABASE_URL and exactly matching TEST_DATABASE_CONFIRM set privately to a **disposable** loopback database permitted by `tests/postgresql_support.py`:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_storage_migration.py -v
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m tools.export_openapi --check
.venv/Scripts/python.exe -m backend.migrate_storage --help
```

The complete final run used the second command; standalone actual-app OpenAPI drift also passed. Earlier full304/305/306 runs passed before the final acceptance refinements; the final307 result supersedes them for this candidate. No frontend/Docker checks were repeated because those inputs/behavior did not change; their prior scoped artifacts remain intact.

The populated fixture migrated all seven application tables (five categories, five users spanning eligibility/admin states, two code histories, two linked refresh records, five listing states, private photo and reviewed/unreviewed reports) with exact primary/foreign keys, canonical typed content, UTC microseconds,0.01/1,000,000,000.00KZT boundaries and transactional sequence restart. Tests verified preserved old access/current refresh, known-password login, active verification code, eligibility denial, protected avatar/listing bytes and anonymous/foreign-avatar denial through the **real migrated API**. The verified backup was copied to a fresh SQLite location and successfully reopened through the real API; source bytes remained unchanged.

Failure/refusal proofs cover no-write dry-run, missing quiescence, sidecars left intact (including a new sidecar injected after publish immediately before commit, with rollback and preservation), malformed schema, missing/changed/traversal files, an actual Windows junction, nonempty/unexpected target and existing unowned destination. A real pre-lock target insertion is detected instead of hidden by an old transaction snapshot. Injected driver and partial-file failures rollback target rows and clean only owned artifacts while preserving backup/source. A deliberately simulated lost acknowledgment **after an actual successful PostgreSQL commit** preserves published files and records uncertainty; read-only verification confirms actual committed content. Corrupting a target sequence makes verification refuse without deleting data/files. A deterministic legitimate image whose re-encoded stored bytes exceed the incoming5MiB limit is copied byte-for-byte under the separately bounded migration budget.

The new data-free target-schema signature was derived from the existing published PostgreSQL migrations, not application data. Existing migrations/models/SQLite adapters/runtime/frontend/container inputs were not edited. No dependency changes or external email were needed. [Operator commands, maintenance assumptions and crash/cutover/rollback limits](../../storage-migration.md) explicitly avoid any global filesystem/database atomicity or automatic merge/resume/reverse-migration claim. Private row hashes, image manifests, URLs, credentials and personal paths are intentionally absent from this public evidence.
