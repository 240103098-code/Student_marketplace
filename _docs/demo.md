# Real-stack local MVP demonstration

## Prerequisites and one command

Complete [pinned installation](local-setup.md), including Playwright 1.62.1, PostgreSQL binaries and either its installed Chromium or an explicit compatible browser executable. Python 3.13.15, Node 24.19.0, npm 12.2.0, PostgreSQL 18.6 and Edge 155.0.4283.45 were tested on Windows. PostgreSQL must be allowed to initialize a fresh user-owned cluster and loopback services/browser must be permitted. No global database service is required.

From the repository root, after `.venv` and `frontend/node_modules` installation:

```powershell
.venv/Scripts/python.exe -m tools.local_demo --postgres-bin C:/path/to/PostgreSQL/18/bin --confirm-disposable-demo student-marketplace-local-demo --browser-executable 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
```

With Playwright Chromium installed, omit `--browser-executable`. `--node` can specify a Node executable if it is not on PATH. On other platforms use `.venv/bin/python`, their PostgreSQL bin directory and browser path; the same harness uses argument arrays, not shell-built commands. It was actually verified on the Windows versions above; other platforms have not been exercised by this change.

The exact verified workspace invocation used `--postgres-bin ../pg-runtime/pgsql/bin` and the Edge path above. This provider-specific path is not required on a fresh checkout. Ordinary dependency prerequisites are explicit: `pip install -r requirements.lock`, `npm ci` in frontend, then optionally `node node_modules/playwright/cli.js install chromium`. The harness builds React itself with its generated actual API origin, so a preexisting Vite server/build is neither required nor reused.

Missing prerequisites/assertions return nonzero FAIL; they are never treated as a skipped PASS. Successful output ends **PASS real-stack local MVP smoke; owned services stopped and disposable data cleaned.** Sanitized progress uses fixed stage names. Detailed backend boundary tests remain a separate full command, not silently substituted by this smoke.

## Isolation and shutdown

The mandatory confirmation authorizes only a newly generated direct child `.venv/tmp/local-demo-<random>` with an ownership marker. The harness starts its own fresh PostgreSQL cluster on an available loopback port, creates only `student_marketplace_test_demo`, applies fresh Alembic migrations/category seeds and uses a private upload/build directory. It never accepts an existing database URL, reads/writes `.env`, resets a supplied database, attaches to a running app or installs a global service.

JWT/session/application password and SMTP test credentials are generated in memory. Three synthetic university identities are used only in the new cluster. SMTP is an actual memory-only loopback protocol server, with an explicitly injected test transport from the existing test fixture. Production sender/TLS defaults are untouched. Captured six-digit codes move to the browser over private child-process stdin; they are not printed, persisted or exposed over HTTP. Browser traces/video/private account screenshots are not captured. External example.invalid contact links are inspected, never followed.

The harness stops only its owned Node/browser/frontend/API/PostgreSQL services in `finally`, on success or failure. Subprocess and service readiness waits are bounded; browser journey has an overall deadline. Temporary data is removed only after stopped services and exact generated-path/marker checks; unrelated data/services are untouched. If shutdown/cleanup cannot complete, it reports nonzero FAIL/pending and preserves its own artifacts for operator review. Stop an interrupted own run only with its exact generated cluster path and captured process ownership, never broad process-name termination or directory wildcards.

Sanitized evidence is written only to fixed `_docs/evidence/demo-*.png` and `demo-result.json` outputs. The result is marked RUNNING at start and finalized PASS/FAIL with cleanup status, runtime versions and timestamp, avoiding a stale previous PASS. Re-running replaces these generated evidence files and creates another independent fresh cluster; it does not reuse accounts or bypass quotas.

## Actual walkthrough and requirement map

| Established requirement / tasks | Real smoke proof and complementary checks |
| --- | --- |
| Empty scaffold, chosen stack/config/database/React (1–5) | Fresh PostgreSQL cluster, migrations/seeds, real FastAPI and production React build; package/config/database tests |
| Student-only university verification (6–9,12) | Seller/buyer/admin register through UI, receive real controlled SMTP MIME and enter six-digit code; exact-domain/purpose/expiry/exhaustion cases in backend tests |
| JWT login, restoration, refresh/logout/password recovery/change (10–15) | Real UI sign-in, separate browser contexts and reload restoration; detailed family rotation/replay/CSRF/password/recovery tests in the full suite |
| Profile/contact/avatar (16–18) | UI name/external-contact save, real avatar upload and account cleanup; decoding/path/ownership boundaries in focused tests |
| Listings/photos/create/edit/My Listings/Sold/deletion (19–26) | UI Pending listing plus real image, owner rejection feedback, real Sold/hard-delete checks; full edit/ownership/order/cascade tests |
| Search/filter/details/external contact (27–31) | Buyer UI literal query, fixed category/condition/inclusive price filters, real private gallery and inspected safe contact href; Pending invisibility and removed denial |
| Reports/admin/current roles/moderation/manual publication (32–37) | Buyer UI report, supported admin CLI promotion, admin UI approve/report queue/review/remove; rejection and suspension/session denial through real APIs plus owner/student UI checks |
| Permanent deletion (38) | Destructive seller UI confirmation, real cascade/credential denial, postcommit cleanup=false, DB absence and zero owned image files; unrelated buyer/admin identities preserved |
| Security/abuse (39) | Security remains enabled throughout smoke; full quota/stream/role-state matrix in security.md and guarded real PostgreSQL tests |
| Final demo (40) | Actual browser desktop/mobile screenshots, keyboard gallery activation, responsive overflow assertion, real API response count, owned shutdown/cleanup and reproducible command |

The principal path is browser UI: register/verify/login → seller contact → create Pending/photo → buyer cannot see Pending → local CLI admin promotion → admin approve → buyer search/filter/details/gallery/contact/report → admin queue/review/remove → buyer hidden/admin private gallery retained. Representative rejection/suspension/Sold/deletion use real HTTP APIs and browser assertions, then seller account deletion uses its actual destructive UI. No API route is mocked. Detailed validation/concurrency/error cases are not redundantly duplicated here; the full suite supplies them.

## Verification record

Final commands from the repository root (Windows):

```powershell
# With dedicated, confirmed loopback TEST_DATABASE_URL/TEST_DATABASE_CONFIRM and owned PG lifecycle from local-setup.md:
.venv/Scripts/python.exe -m unittest discover -s tests -v
cd frontend
npm run test -- --run
npm run build
cd ..
.venv/Scripts/python.exe -m tools.local_demo --postgres-bin ../pg-runtime/pgsql/bin --confirm-disposable-demo student-marketplace-local-demo --browser-executable 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
git diff --check
```

Exact command/results and expected failure-cleanup evidence are preserved in [verification.txt](evidence/verification.txt).

Complete backend: **257 passed, zero skips** with actual PostgreSQL and controlled loopback SMTP. Frontend: **142 passed**; production build passed. Real-stack smoke: **PASS**, with real response count/runtime versions in [demo-result.json](evidence/demo-result.json), [desktop marketplace](evidence/demo-desktop.png), [mobile detail/keyboard focus](evidence/demo-mobile.png) and [admin report queue](evidence/demo-admin-reports.png). Evidence has been visually inspected for responsive layout and absence of credentials/private identities. Backlog remains exactly forty tasks; history/plan are preserved.

Playwright 1.62.1 and its pinned resolved playwright-core are the only added development dependency. The npm install command's automatic audit summary is preserved in [npm-install-summary.txt](evidence/npm-install-summary.txt); it reported zero findings in its 91-package audit on 2026-10-19. That is not an independent comprehensive vulnerability assessment or a production-security certification.

## Remaining limits

This proves a **local** MVP on the recorded runtime. No production deployment, distributed limiter, trusted reverse-proxy/TLS setup or real university-inbox delivery is claimed. The loopback fixture intentionally substitutes plaintext test transport while exercising SMTP/MIME; separate unit checks retain verified TLS/STARTTLS ordering in production code. Live provider credentials and an intentional operator-controlled university-inbox check remain outstanding. No real people were contacted and no external contact link was opened.
