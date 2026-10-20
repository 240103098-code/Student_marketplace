# Final runtime verification — 2026-10-20, issue #53

Source base: `316b26db95c6077da62dc203fea49ae156ea1343`; tested tool hashes are in [verification.json](verification.json). Exact candidate implementation SHA is posted in issue53 after commit; independent QA verifies that same SHA before root publication/QA closure. This record does not prematurely claim those later gates.

Versions: Python 3.13.15, SQLite 3.50.4, SQLAlchemy 2.1.4, FastAPI 0.143.0, Node24.19.0, npm12.2.0, Playwright1.62.1, Edge 155.0.4283.45; actual PostgreSQL version is in [its result](postgresql/demo-result.json).

## Actual checks

- PASS complete backend: **292 tests, zero skips,98.111s**, real guarded PostgreSQL plus memory and persistent-file SQLite suites. Dedicated loopback test cluster started only for this command and stopped in finally.
- PASS frontend: **157 tests in23 files**, `--maxWorkers=2`; typecheck and production real-build/mock-exclusion/refused-mock-build checks PASS. No assertions weakened; no application/backend/frontend dependency changes.
- PASS actual-app `tools.export_openapi --check` without services/secrets. Existing 40-route contracts and strict request/error/CSRF/image/role invariants remain enforced.
- PASS explicit mock: **0 backend API /0 external requests**,32 local asset reads; all6 original JPEGs decoded >1px and SHA256 matched, current six card/detail prices verified, warning/controls/development isolation and reload/reset tested.
- PASS real memory: **138 real API requests** (110 browser +28 direct API),0 external,2 owned API instances. Core student/admin journey uses live FastAPI/SMTP protocol. Before final restart:2 users,2 codes,13 refresh rows,1 Pending listing/photo and2 private image files. After shutdown/recreate: all personal/content/session rows zero,5 fixed categories, no images; old private root removed, old bearer/refresh/login denied, actual browser returns to sign-in. Fresh root also disposed on final shutdown.
- PASS real persistent SQLite: **131 real API requests** (113 browser +18 direct API),0 external,3 API instances. First restart preserves approved2500.00KZT listing/photo/user/session rows and exact image bytes; second preserves the reviewed report and approval. Snapshots before/after match; actual buyer/admin browser refresh restoration returns200 and authoritative reads continue.
- PASS separate PostgreSQL browser smoke: **116 real API requests** (98 browser +18 direct API),0 external; fresh owned cluster and full real React/SMTP journey, no substitute SQLite/ASGI-only browser claim.
- PASS expected prerequisite failure: nonexistent explicit browser after owned memory API/frontend startup returns1 and cleans owned services/disposable directory; [negative result](failure-cleanup/expected-failure.json) labels this as failure-cleanup proof, not a successful browser journey.

Desktop/mobile artifacts are newly captured under this folder, not reused old screenshots. Viewed memory post-reset sign-in, SQLite reviewed-report after restart, all6-product mock mobile catalog and PostgreSQL desktop feed. Synthetic content only; no secrets, raw private paths, SMTP/code/token bodies or personal database dumps. Original dated evidence is untouched. Existing user's checkout/data/preview and source repository are untouched.

## Commands actually run

From repository root (frontend commands from `frontend`):

```powershell
# Full backend: dedicated confirmed loopback TEST_DATABASE_URL/TEST_DATABASE_CONFIRM,
# private TEMP/TMP and owned PostgreSQL start/stop as documented in local-setup.md.
.venv/Scripts/python.exe -m unittest discover -s tests -v
# Workspace npm12.2 invoked via node ../../npm-runtime/package/bin/npm-cli.js;
# equivalent installed npm commands used by ordinary fresh-checkout operators:
cd frontend
npm run test -- --run --maxWorkers=2
npm run typecheck
cd ..
node tools/check_frontend_build.mjs
.venv/Scripts/python.exe -m tools.export_openapi --check
.venv/Scripts/python.exe -m tools.mock_demo --confirm-disposable-demo student-marketplace-mock-demo --evidence-dir _docs/evidence/final-compliance/mock --browser-executable "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
.venv/Scripts/python.exe -m tools.sqlite_demo --storage memory --confirm-disposable-demo student-marketplace-sqlite-demo --evidence-dir _docs/evidence/final-compliance/memory --browser-executable "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
.venv/Scripts/python.exe -m tools.sqlite_demo --storage sqlite --confirm-disposable-demo student-marketplace-sqlite-demo --evidence-dir _docs/evidence/final-compliance/sqlite --browser-executable "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
.venv/Scripts/python.exe -m tools.local_demo --postgres-bin ../pg-runtime/pgsql/bin --confirm-disposable-demo student-marketplace-local-demo --evidence-dir _docs/evidence/final-compliance/postgresql --browser-executable "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
```

Use a **new** evidence directory (for example `.venv/tmp/qa-memory`) for independent reruns rather than overwriting these committed snapshots. All runners use unused owned loopback ports, generated runtime secrets, controlled protocol SMTP, no browser route/API mocks in real modes and no public admin/code endpoint. Memory promotion invokes the existing eligible-account CLI in the same process; persistent modes invoke it separately. All owned successful-run services stopped and disposable data removed. Original files/backups are never targets.

## Findings and lifecycle

One new memory-proof harness wait initially looked for desktop Sign out while buyer viewport was still390px/mobile; actual login had succeeded and the mobile drawer was closed. The harness now explicitly uses its desktop viewport for that assertion and still verifies mobile after reset. This was a test-navigation mistake, not an application defect; no fictitious bug issue was created. Existing real bug tickets and regression evidence are mapped in [compliance](../../compliance.md).

[Label definitions](labels.json) were read back publicly after root's authorized update; no dummy issues. [Issue snapshot](pre-publication-issues.json) truthfully shows only53 open with mvp and no open user-test-bug **before** QA/publication. Root must publish exact independent-PASS commit; QA verifies it and closes; root then audits zero-open counts. Controlled SMTP does not prove live inbox delivery, local testing does not certify production/distributed operation, original full interview is unavailable, and no deadline was supplied. Candidate `git diff --check` is scoped to changed files; old published SQLite DDL cosmetic whitespace is not rewritten or presented as a new bug.
