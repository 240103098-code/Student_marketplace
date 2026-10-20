# Final frontend integration (#43)

The user-owned Lovable reference has been adapted to the existing React/Vite implementation. The source repository remains read-only; there is **no automatic Lovable synchronization**, source backend, Supabase, Firebase or provider replacement. Published #45/#41/#42 provide the shell, student and admin visuals. This package adds explicit development mocks, a gradual typed boundary and actual-app OpenAPI verification. [Persistent SQLite](sqlite-setup.md) is now the fresh real-development default; [memory](memory-backend.md) and PostgreSQL remain explicit alternatives. The original #43 results below are dated snapshots.

## Select real or synthetic development mode

From a clean checkout, install the prerequisites and pinned dependencies in [local-setup.md](local-setup.md). Real FastAPI is the default. From `frontend` on Windows:

```powershell
# Frontend-only synthetic demo: no PostgreSQL, Python server or SMTP needed.
$env:VITE_SERVICE_MODE = 'mock'
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort
# Ctrl+C stops this development server.
Remove-Item Env:VITE_SERVICE_MODE -ErrorAction SilentlyContinue

# Real mode: run the configured/migrated backend separately as documented.
$env:VITE_SERVICE_MODE = 'real'
$env:VITE_API_ORIGIN = 'http://127.0.0.1:8000'
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort
```

Do not start two servers on the same port. `npm run dev` is the equivalent Vite command when npm is available. No mock fallback follows offline, 401 or403. A production build refuses mock configuration even with `--mode development`; real production output excludes the fixture/control modules. `node tools/check_frontend_build.mjs` from the repository root verifies the actual bundle and both refused build modes.

The persistent yellow **SYNTHETIC DEMO** banner appears on every mock route. It names student-demo@sdu.edu.kz, buyer-demo@sdu.edu.kz and admin-demo@sdu.edu.kz. Any **synthetic** password of12–128 characters signs into these demo accounts; code000000 exercises verification/reset forms. Never enter real passwords, identities, photos or contact information. Uploaded demo bytes are replaced with a fixed generated pixel. The six restored product fixtures use the original user-supplied JPEGs through local bundled-asset reads; no real-backend or external network/email request is made. See [photo provenance and checks](mock-original-photos.md).

Fixtures, simulated session credentials and transitions exist only in module memory. Client-side route changes retain them; full reload resets fixtures and signs out. To review a newly created Pending listing as admin, sign out and sign in as admin in the **same tab without reloading**. Separate tabs do not share data. Reset clears state and reloads the sign-in route. Limits:30 users,50 listings, five images per listing and100 reports. Deleted listing/account images are removed from mock memory.

Controls select normal, slow GETs800ms, empty queues, next network failure, next503, next429/Retry-After60 or persistent admin permission denial. One-shot errors are consumed by the next request; select Normal before repeating. Empty/permission/slow modes last until changed/reset. These controls are development-only and do not claim to reproduce backend concurrency, JWT cryptography, SMTP delivery, image processing or security enforcement.

To reproduce the synthetic browser journey with the mock server running, from the repository root run `node tools/mock_browser.mjs`. It uses the pinned optional Playwright browser from the demo prerequisites. For installed Edge set `$env:MOCK_BROWSER_EXECUTABLE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'`; set MOCK_WEB_URL for a different local port and MOCK_EVIDENCE_DIR to capture into a separate directory. The runner requires the explicit demo banner, signs into synthetic accounts only, and closes its own browser. It does not start or stop the server.

## Canonical boundary and source mapping

`src/transport.js` is the sole service seam under existing `requestJson`; real requests retain credentialed fetch, headers, cookies, CSRF, Bearer tokens, multipart FormData, binary blobs and safe errors. Existing view validators still reject malformed DTOs in either mode. `src/contracts.d.ts`/`api.d.ts` declare consumed DTO/request/result types; `contract-boundary.ts` is a compiler-checked gradual consumer, rather than a broad JSX conversion. Type declarations do not replace runtime validation.

| Source concept | Canonical target boundary |
| --- | --- |
| Arbitrary string/UUID identifiers | Positive integer JSON identifiers (PostgreSQL bigint, SQLite generated INTEGER); UI rejects unsafe/nonpositive JS integers. No UUID substitution. |
| Category labels/slugs | Fixed numeric IDs1–5 plus key/label DTOs. |
| Numeric/demo currency | KZT and exact two-decimal **strings**; real validation rejects excess meaningful precision before persistence. |
| Fixture status/report names | Pending/Active/Sold/Rejected/Removed; reason enums spam, prohibited_items, misleading_information. |
| Client role/localStorage session | Current DB-backed is_admin capability and opaque in-memory client tokens; real refresh is HttpOnly cookie + CSRF. Mock opaque tokens are explicitly synthetic and contain no real JWT claims. |
| Direct public image URL | Authenticated private image GET→blob→revoked object URL; multipart field is **image**, not file. |
| Source sample contacts/accounts | Synthetic target fixtures only in explicit development mode; seller DTO never exposes email. |

New dependency: pinned **TypeScript7.0.2, development-only**, with its platform compiler distribution recorded in package-lock. It checks the small declaration boundary; runtime dependencies are unchanged. No Python or serialization dependency was added.

## Actual OpenAPI and its limits

From the repository root:

```powershell
.venv/Scripts/python.exe -m tools.export_openapi
.venv/Scripts/python.exe -m tools.export_openapi --check
cd frontend
npm run typecheck
npm run test -- --run --maxWorkers=2
npm run build
cd ..
node tools/check_frontend_build.mjs
```

`openapi.yml` is deterministic sorted JSON-compatible YAML from the **actual** FastAPI factory and existing models. Export injects inert dependencies and explicit synthetic settings; it reads no .env or credentials and connects to no database/SMTP. The drift test compares committed bytes. No invented endpoint or security annotation is added to the generated artifact.

At the completed #43 stage, manually parsed Request routes still had incomplete machine schemas. #50 now supplies machine-readable request/result/query/multipart/binary/security/error metadata on the actual app; see [current canonical contract](canonical-api-contract.md). Runtime rules that JSON Schema cannot enforce still require the supplemental contract. The actual supplemental contract is [api.md](api.md):15-minute HS256 access JWTs in Authorization:Bearer, seven-day fixed-family refresh_token cookie (HttpOnly, SameSite=Lax, host-only, Path=/auth, Secure in production), GET/auth/csrf bootstrap, X-CSRF-Token and allowed Origin on refresh/logout, exact credentialed CORS origins and current DB eligibility/admin checks. Login/refresh use cookies; no browser storage token is introduced. Multipart uses image; protected images return image/jpeg/png/webp with private,no-store and nosniff. Safe errors expose detail only, no raw input; status/Retry-After drive client feedback. Consult API/security docs for endpoint-specific400/401/403/404/409/413/422/429/503 behavior. Current #50 annotations describe these interfaces; OpenAPI itself does not enforce dynamic role, state, Origin, duplicate-wire-field or normalization rules.

## Verification and evidence — #43 snapshot (2026-10-20)

- Clean isolated frontend copy: npm ci, typecheck, **155 interaction tests**, production build PASS. An existing user preview held a native Windows module, so clean-ci proof used sibling work/frontend-clean-43; ordinary target packages were restored from the same lock without stopping that preview, and both its page and compiled App returned200. Stop running servers before ordinary clean npm ci.
- Full guarded PostgreSQL backend run:261 tests,260 passed; only the newly written wrong-multipart-field assertion expected422 instead of the established safe400. Corrected test and mock to400; all **eight affected actual-PostgreSQL tests then passed**, including upload and private binary contracts. Existing260 assertions were unchanged. Dedicated PostgreSQL was stopped after each run.
- Schema export/check, shared canonical-example models, actual unauthorized/validation HTTP checks, TypeScript boundary, explicit real-mode no-fallback tests and production bundle/mode-isolation checks PASS. Real and mock catalog DTOs use the same canonical example shape; actual multipart accepts image and rejects file, and both transports return private PNG bytes. Both feed consumers reject malformed price DTOs.
- [Mock browser result](evidence/integration-contracts/mock-browser-result.json): student profile/Pending/photo→admin approval→buyer filter/detail/report→admin review; warning, permission denial,429, mobile overflow and reload reset PASS, **zero real API requests/browser storage writes**. Viewed [student](evidence/integration-contracts/mock-student-desktop.png), [buyer mobile](evidence/integration-contracts/mock-buyer-mobile.png), [reports](evidence/integration-contracts/mock-admin-reports.png), [permission](evidence/integration-contracts/mock-permission.png), [error](evidence/integration-contracts/mock-rate.png) screenshots contain synthetic data only.
- [Final real-mode smoke](evidence/integration-contracts/real-smoke-result.json): **98 real API responses**, real production React/FastAPI/fresh PostgreSQL/controlled loopback SMTP, full student/admin journey PASS and owned-service/data cleanup complete. Actual browser confirms no mock warning/controls. Viewed [desktop](evidence/integration-contracts/real-desktop.png), [mobile](evidence/integration-contracts/real-mobile.png), [admin](evidence/integration-contracts/real-admin-reports.png). Earlier demo/student/admin evidence and history remain intact.

Controlled SMTP protocol success is **not verified internet/university inbox delivery**. Production is not deployed. Mock checks prove UI behavior only; real backend tests/smoke establish the documented local boundaries. Independent QA and exact-commit publication remain required before issue closure.

Current totals are292 backend/157 frontend; the [iteration log](iterations.md) links independent full-run evidence and newer storage/browser results. Earlier counts above retain their original #43 scopes. Final comprehensive cross-mode verification remains #53, not a completed claim of this historical integration report.
