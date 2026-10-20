# Canonical API contract, iteration50

The actual FastAPI application and committed openapi.yml now share one canonical schema. Existing raw Request parsers remain intact; backend/openapi_contract.py installs a documentation-only enrichment on app.openapi after the actual routers are registered. It enriches supported operations only, adds no storage/mock API and connects to no service. Request validation, response bodies, authentication, transactions and business services are unchanged.

## Audit and resolved gaps

The previous #43 export was reproducible but left manual-action success DTOs, raw JSON bodies, strict query filters, multipart image/binary results, safe422 errors and cookie/CSRF/header security incompletely annotated. The inventory below covers all40 actual API operations. The new schemas include typed request/result fields, required/null/omitted semantics, fixed enums/KZT/canonical prices and bigint limits, no-field action bodies, protected binary media and handled error/header shapes. Existing generated HTTPValidationError definitions no longer misdescribe detail-only safe errors.

The canonical schema adds machine-readable HTTPBearer/RefreshCookie/CsrfHeader schemes, Origin/header/cookie parameters and actual per-operation statuses. Logout does not falsely require a cookie: absent/unknown cookies are idempotent with allowed Origin and syntactically valid CSRF. Refresh/CSRF bootstrap require an eligible cookie family. Login/CSRF reject an invalid supplied Origin; refresh/logout require one. Every protected request rechecks current verified/unsuspended eligibility and live family; admin additionally checks current DB role. OpenAPI documents these rules; it does not grant or enforce authority.

## Boundaries that need runtime enforcement

- Request price accepts canonical decimal strings or exact JSON decimal numbers parsed as Decimal,0..1b with at most two meaningful fractional digits; fractional trailing zeros are allowed. Responses always use two-decimal KZT strings. The frontend intentionally sends strings. No rounding behavior changed.
- Normalized text/email length applies **after** trim/lowercase where the existing validator does so. Schemas use x-normalized-* plus descriptions instead of incorrectly rejecting a valid padded input by raw maxLength. Passwords preserve spaces. Omitted partial fields preserve values; explicit null clears contacts but is rejected for profile name/listing price/description.
- Pagination values have numeric bounds and x-wire-pattern; runtime rejects signs, leading zeros, exponents, duplicate and unknown keys. Search is a literal substring, not SQL wildcard syntax; Unicode control characters are rejected. Inclusive min/max must satisfy min<=max. JSON Schema cannot enforce duplicate serialized keys or these cross-field/wire parsing rules by itself.
- Manual strict JSON parsers retain duplicate/nonfinite/content-type/64KiB rejection. Listing/admin empty actions accept no body or bytes parsing to{}, with no query fields and a1024-byte action cap. Their parser does not inspect Content-Type; optional application/json and wildcard representations document the existing behavior. Refresh/logout instead ignore payload fields after the global64KiB bound; they are not falsely described as strict empty-object actions.
- Exactly one multipart field **image**, no extra files/fields; actual decoded JPEG/PNG/WebP, five MiB,20million pixels, framing bound five MiB+64KiB. File-byte/pixel limits are explicit x-* metadata because JSON Schema maxLength is not a reliable binary byte cap. Input MIME is not trusted. Protected GET media are image/jpeg/png/webp with private,no-store and nosniff; DTOs contain protected URLs, never disk paths.
- Standard security metadata/Set-Cookie descriptions represent HttpOnly host-only Path=/auth SameSite=Lax, Secure in production, fixed-family refresh default7days and HS256 access default900seconds. Backend settings permit other positive durations; the existing frontend boundary uses the documented defaults. No usable credential/token examples are exported.
- Status400/401/403/404/409/413/422/429/500/503 is declared where applicable.500 describes handled sanitized database/storage errors, not an invented guarantee for arbitrary unhandled exceptions. Resend/forgot202 and429 expose Retry-After. Oversized listing-body transport retains422; other mutation transport limits use413. CORS preflight remains existing middleware behavior, not invented API routes.

## Reproduction and dependencies

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-dev.lock
.venv/Scripts/python.exe -m tools.export_openapi
.venv/Scripts/python.exe -m tools.export_openapi --check
.venv/Scripts/python.exe -m unittest discover -s tests -v
cd frontend
npm run typecheck
npm run test -- --run --maxWorkers=2
cd ..
node tools/check_frontend_build.mjs
```

The full backend command requires the existing explicit disposable PostgreSQL guard from local-setup.md; never point it at user persistent data. jsonschema4.26.0 is the minimal new **development-only** dependency for standards-based Draft2020-12 validation, with attrs/jsonschema-specifications/referencing/rpds-py resolved in requirements-dev.lock. It is not imported by runtime code; runtime requirements.lock is unchanged. No frontend dependencies changed.

Export/check uses explicit synthetic settings plus inert database/sender objects, not load_settings/.env/startup. It is deterministic; committed bytes must match. Tests verify all component schemas and local references, actual route coverage, runtime /openapi.json equality and route-change drift. No user checkout/private operations/Gmail data was accessed.

## Actual operation inventory

| Operation | Request representation/schema | Successful result | Query parameters |
| --- | --- | --- | --- |
| GET /admin/me | — | 200: AdminIdentity | — |
| GET /admin/users | — | 200: AdminUsersPage | limit, offset |
| PATCH /admin/users/{target_id}/suspension | application/json → SuspensionRequest | 200: SuspensionResult | — |
| GET /admin/listings | — | 200: AdminListingsPage | limit, offset, status |
| GET /admin/listings/{listing_id} | — | 200: AdminListingDetail | — |
| GET /admin/listings/{listing_id}/photos/{photo_id} | — | 200: binary | — |
| POST /admin/listings/{listing_id}/remove | application/json → EmptyAction, */* → EmptyAction | 200: RemovedResult | — |
| GET /admin/reports | — | 200: AdminReportsPage | limit, offset, state |
| POST /admin/reports/{report_id}/review | application/json → EmptyAction, */* → EmptyAction | 200: ReviewedResult | — |
| POST /admin/listings/{listing_id}/approve | application/json → EmptyAction, */* → EmptyAction | 200: ApprovedResult | — |
| POST /admin/listings/{listing_id}/reject | application/json → ListingRejectionRequest | 200: RejectedResult | — |
| POST /auth/register | application/json → RegistrationRequest | 201: RegistrationResponse | — |
| POST /auth/verify-email | application/json → VerifyEmailRequest | 200: VerifiedResult | — |
| POST /auth/resend-verification | application/json → ResendVerificationRequest | 202: AcceptedMessage | — |
| POST /auth/login | application/json → LoginRequest | 200: AccessTokenResponse | — |
| GET /auth/me | — | 200: AuthMeResponse | — |
| GET /auth/csrf | — | 200: CsrfResult | — |
| POST /auth/refresh | — | 200: AccessTokenResponse | — |
| POST /auth/logout | — | 204: empty | — |
| POST /auth/change-password | application/json → ChangePasswordRequest | 204: empty | — |
| POST /auth/forgot-password | application/json → ForgotPasswordRequest | 202: AcceptedMessage | — |
| POST /auth/reset-password | application/json → ResetPasswordRequest | 204: empty | — |
| GET /users/me | — | 200: ProfileResponse | — |
| DELETE /users/me | application/json → DeleteAccountRequest | 200: AccountDeleted | — |
| PATCH /users/me | application/json → ProfilePatch | 200: ProfileResponse | — |
| GET /users/me/avatar | — | 200: binary | — |
| POST /users/me/avatar | multipart/form-data | 200: AvatarResult | — |
| DELETE /users/me/avatar | — | 200: AvatarResult | — |
| GET /listings | — | 200: BrowseListingsPage | limit, offset, q, category_id, condition, min_price, max_price |
| POST /listings | application/json → ListingCreateRequest | 201: OwnListingResponse | — |
| GET /categories | — | 200: Categories | — |
| GET /listings/mine | — | 200: MineListingsPage | limit, offset, status |
| GET /listings/{listing_id}/edit | — | 200: ListingEditResponse | — |
| PATCH /listings/{listing_id} | application/json → ListingEditRequest | 200: ListingEditResponse | — |
| DELETE /listings/{listing_id} | application/json → EmptyAction, */* → EmptyAction | 200: ListingDeleted | — |
| GET /listings/{listing_id} | — | 200: ListingDetailResponse | — |
| POST /listings/{listing_id}/sold | application/json → EmptyAction, */* → EmptyAction | 200: SoldResult | — |
| POST /listings/{listing_id}/reports | application/json → ListingReportRequest | 202: ReportAccepted | — |
| POST /listings/{listing_id}/photos | multipart/form-data | 201: CreatedPhoto | — |
| GET /listings/{listing_id}/photos/{photo_id} | — | 200: binary | — |

## Forward iterations and verification

The existing explicit frontend mock is the first **demonstrable stage for this forward iteration**; canonical contract50 follows it. Real FastAPI in-memory storage51 is now implemented as an explicit volatile development/test mode; [memory setup](memory-backend.md) describes its storage/locking and lifecycle verification. Persistent SQLite44 is now implemented as the fresh local default with its separate migration stream; [SQLite setup](sqlite-setup.md) records the new dated choice and restart/process evidence. Authentic brainstorm transcript52 and final real frontend cross-mode verification53 remain future packages. This does not rewrite the historical order of earlier PostgreSQL/frontend commits or claim those future stages are already complete. Forty-task history, visual source/provenance/evidence and all real/mock defaults remain intact.

New contract tests compare actual manual listing/edit/upload/binary/decision/report and cookie/CSRF/capability responses with the declared schemas using real guarded PostgreSQL, plus safe validation/error/size/rate/header behavior without services. Original strict JSON/query/image tests remain unchanged. Exact final verification results are recorded in evidence/canonical-api-contract/verification.txt. No UI redesign or provider replacement occurs here.

SQLite writer contention adds a declared safe 503/Retry-After failure to database-backed operations. Existing payload/success/security schemas stay unchanged; failed mutations are never automatically replayed.
