
# Backend API

## Registration and verification screens

React /register and /verify now call the registration, verification, and resend contracts below. The shared HTTP helper sends credentialed JSON with exactly the required fields, displays safe status-based feedback, and never echoes arbitrary response text or network exceptions. VITE_API_ORIGIN selects the API origin; its local default matches localhost or 127.0.0.1 with port 8000. Configure matching FRONTEND_ORIGINS and use one hostname consistently.

Registration holds the returned normalized email and a sixty-second resend deadline only in React memory, then navigates to /verify. A direct/reloaded verification route has an editable email input. Passwords/codes are never URL parameters or local/session-storage values. Successful verification shows a sign-in link without logging in. Generic failures explain ten-minute codes and replacement after five wrong attempts without inventing remaining counts or claiming a specific error reason.

Resend treats 202 as the same generic eligible-address response and uses Retry-After (sixty seconds by contract) for a readable disabled-button countdown. Failed network/503 requests do not start a new cooldown and remain retryable. Pending controls prevent duplicate/overlapping submissions. Login/session React integration is still the next task, and live university-inbox delivery remains unverified without external SMTP setup.

Current capability: registration of an unverified student plus configured SMTP verification-code delivery. One-time verification and cooldown-limited resend are implemented below. Verified-user login, access JWTs, and the database-backed /auth/me guard are available below; secure refresh rotation/logout are available below; marketplace endpoints remain future work. React registration/verification screens call their three public endpoints; login/session React integration remains future work.

## POST /auth/register

Accept a JSON object containing exactly `email` and `password`.

- `email`: required string, trimmed and lowercased, syntactically valid, maximum 254 characters, with exactly the ASCII domain `sdu.edu.kz`. Subdomains, suffix lookalikes, Unicode domain aliases/lookalikes, and malformed addresses are rejected. Validation is local and does not make DNS requests.
- `password`: required string of 12–128 characters, with no coercion, trimming, or composition rule. It is stored only as an Argon2id hash.
- Unknown fields, missing fields, wrong types, invalid values, and malformed JSON are rejected before any account is persisted.

HTTP **201** returns only:

```json
{"id": 1, "email": "student@sdu.edu.kz", "verified": false}
```

The persisted account is unverified, unsuspended, and has role student. A six-digit registration code is generated and emailed to the normalized address, with ten-minute validity. Only a keyed, user/purpose-bound digest is stored; no code, refresh session, access token, plaintext password, or password hash is returned. No refresh session is created.

| Status | JSON body | Meaning |
| --- | --- | --- |
| 201 | id, normalized email, verified=false | Account created |
| 409 | `{"detail":"University email is already registered."}` | Normalized email already exists |
| 422 | `{"detail":"Invalid registration request."}` | Invalid request, no account created |
| 500 | `{"detail":"Registration is temporarily unavailable."}` | Unexpected database failure |
| 503 | `{"detail":"Verification email is temporarily unavailable."}` | Missing SMTP settings or delivery failure; new account/code rolled back |

SMTP delivery uses configured real transport with verified TLS/STARTTLS before authentication, a ten-second network timeout, and connection cleanup. Delivery failures roll back the caller transaction, including new account/code state and replacement invalidation. Duplicate registration does not send another message. Code issuance can be reused internally for replacement and password-reset purpose; resend and password-reset endpoints are documented below.

Uniqueness is enforced by PostgreSQL, including concurrent requests; the transaction rolls back on conflict and later requests can still succeed. Responses and application logs do not echo submitted passwords, validation inputs, hashes, URLs, or database credentials. Database exceptions are converted to a generic response rather than driver details. Abuse controls belong to the later security task.

## Application lifecycle

`backend.app.create_app(settings, database=None)` takes validated injected settings and optionally a borrowed Database. Owned infrastructure is disposed on shutdown; borrowed infrastructure remains the caller's responsibility. Importing app/main modules does not load settings or connect. Uvicorn explicitly calls `backend.main:create_runtime_app` with `--factory`; that runtime factory loads configuration and constructs a lazy engine. Apply migrations before registration requests.

OpenAPI is available at `/openapi.json`, with local interactive documentation at `/docs`. See [local setup](local-setup.md) for the tested startup command and the separately confirmed disposable PostgreSQL test contract.

## POST /auth/verify-email

Accept exactly `email` (the same strict normalized university-email contract) and `code` (a required string of exactly six ASCII digits, without coercion or trimming). Unknown fields, wrong types, Unicode digits, malformed emails, and invalid JSON receive 422 `{"detail":"Invalid verification request."}` without echoing submitted values.

A correct usable registration-purpose code returns 200 `{"verified":true}` and atomically marks the user verified and the code consumed. It returns no code, JWT, or session. Unknown, verified, suspended, expired, consumed, invalidated, exhausted, wrong-purpose, and incorrect submissions receive 400 `{"detail":"Verification code is invalid or unavailable."}`. Expiry is inclusive at creation plus ten minutes.

Each well-formed wrong submission against the current usable code increments its persisted wrong_attempts. The fifth invalidates it; later correct values fail until replacement. State commits before the router raises 400, so errors do not erase attempts. User/code row locks serialize verification; constant-time digest comparison is registration-purpose scoped. Time is sampled after acquiring the locks. Unexpected database failure returns generic 500 `{"detail":"Verification is temporarily unavailable."}`.

## POST /auth/resend-verification

Accept exactly the strict `email` field. Eligible unverified, unsuspended users may receive a replacement after sixty seconds since their latest registration-code issuance; the exact sixty-second boundary is allowed. A replacement resets attempts, lasts ten minutes, invalidates earlier usable registration codes, and leaves password-reset codes unchanged. Bounded fresh-code generation avoids reusing an earlier unconsumed value.

Successful issuance, cooldown suppression, unknown addresses, and ineligible accounts all return 202 with `Retry-After: 60` and the same body:

```json
{"detail":"If this address is eligible, a verification email may arrive. Retry after 60 seconds."}
```

Suppression sends no email and stores no code. User-row locking and a post-lock clock reading serialize concurrent requests, so at most one replacement is issued within the window. SMTP failure returns 503 `{"detail":"Verification email is temporarily unavailable."}` and rolls back replacement/invalidation, preserving the earlier usable code. Invalid input receives the same sanitized 422 verification error; unexpected database failure receives the generic verification 500 error above. Broader hourly/IP abuse controls remain future work.

## Verification delivery status

Local verification used actual SMTP protocol/MIME on an isolated loopback fixture, with an explicit test-only plaintext transport substitute. Production certificate verification remains enabled; TLS/auth ordering and failure cleanup were separately tested. No external people were emailed. Provider host/port/sender/credentials remain external operational configuration, and live internet university-inbox delivery has not been verified. See local setup for the credential-dependent operator check.

## POST /auth/login

Accept exactly `email` and `password`, using the same strict normalized university-email and untrimmed 12–128-character SecretStr password contract as registration. Unknown fields (including caller-supplied duration/claims), missing fields, wrong types, and malformed input return 422 `{"detail":"Invalid login request."}`. Argon2 verifies the stored password hash.

Unknown email, incorrect password, unverified account, and suspended account all return 401 `{"detail":"Invalid credentials or account unavailable."}` with `WWW-Authenticate: Bearer`. A successful eligible login returns 200 with only access_token, token_type=bearer, and expires_in=900 by default (JWT_ACCESS_MINUTES times sixty). A digest-only refresh session and secure cookie are also created as described below; no verification code or email is sent. The response token is sensitive: do not print or log it; future browser handling keeps it in memory.

The access JWT uses only HS256 with the configured JWT_SECRET_KEY and these exact required claims:

| Claim | Value |
| --- | --- |
| iss | student-marketplace |
| aud | student-marketplace-students |
| sub | Canonical positive user id as a string |
| type | access |
| iat | Issuance time, integer UTC seconds |
| exp | iat plus configured access minutes times sixty |
| jti | Random UUID hex identifier |
| sid | Session-family UUID hex identifier |

Tokens contain no email, password/hash, code, profile/contact data, role, or eligibility flags. Validation uses an explicit HS256 allowlist, required issuer/audience/claims, strict canonical claim types and subject/id bounds, and the same configured duration. It rejects extra claims, malformed/incorrect signatures or algorithms, missing claims, wrong issuer/audience/purpose, expiry at its exact boundary, and future issued-at time. Signature/issuer/audience validation stays in PyJWT; explicit UTC-clock time checks allow deterministic tests without bypassing those checks.

## GET /auth/me

Send `Authorization: Bearer <access token>`; access authorization uses Bearer; refresh/logout use their protected cookie contract below. The shared require_verified_user dependency validates the token and reloads current account and active session-family state from PostgreSQL on every request. Deleted/missing, unverified, or suspended accounts are rejected even while a signed token is unexpired. Success returns only id, normalized email, and verified=true; no profile editing or listing data is implemented here.

Missing/malformed Bearer credentials, invalid/expired tokens, and current ineligibility return 401 `{"detail":"Authentication required."}` with `WWW-Authenticate: Bearer`. Unexpected database errors on login/me return generic 500 `{"detail":"Authentication is temporarily unavailable."}`. Error responses and application logs do not echo credentials, tokens, raw validation input, or driver details.

Current access tokens are session-family bound. Old access-only tokens lacking sid no longer authorize requests. Account suspension, unverification, deletion, family revocation, and fixed family expiry take effect through the database-backed guard. React login and protected student navigation are implemented; full profile workflows remain future work.

## Refresh cookie, CSRF bootstrap, and CORS

Login creates a random opaque refresh credential, stores only its digest, and sets the host-only `refresh_token` cookie with Path=/auth, HttpOnly, SameSite=Lax, and Secure in production. Development/test may use the documented non-Secure local HTTP exception. Refresh credentials are never JSON fields or logged/stored plaintext. The family's expiry is seven days from login (REFRESH_SESSION_DAYS); rotation preserves it.

Access JWTs now require sid, a UUID-family hex identifier, in addition to all previously required claims. The guard reloads both current account eligibility and an active, unexpired session in that user's family. Valid within-family access survives rotation, but logout/replay/family expiry denies even an unexpired access JWT. No profile/credential data is added to claims.

After login or a page reload, credentialed GET /auth/csrf reads the cookie and returns only `{"csrf_token":"<session-bound HMAC>"}` with Cache-Control:no-store. This helper is read-only: it never rotates, creates, extends, or revokes a session. Missing/invalid/revoked/expired/ineligible cookie state receives safe 401. A supplied disallowed Origin receives safe 403. The CSRF value is bound to user and family; it remains stable across rotation within that family.

POST /auth/refresh and /auth/logout require an exact configured Origin and X-CSRF-Token. Known session cookies require a constant-time family-bound match before any state change; missing/disallowed Origin or missing/malformed/mismatched CSRF returns 403 `{"detail":"Request origin or CSRF token is invalid."}`. Use browser credentials:include for cookie-bearing requests. Login rejects a supplied disallowed Origin while API clients may omit Origin on password login.

Credentialed CORS allows only FRONTEND_ORIGINS, GET/POST/PATCH/DELETE, and Authorization/Content-Type/X-CSRF-Token; it exposes Retry-After and never uses a wildcard origin. Use the same hostname for local frontend and API so SameSite=Lax works: for the default origin, open frontend at http://localhost:5173 and API at http://localhost:8000. Alternatively configure http://127.0.0.1:5173 and use 127.0.0.1 consistently. Both services bind loopback.

## POST /auth/refresh

The refresh credential is read only from the cookie, never a JSON token field. With valid Origin/CSRF and eligible active session state, return the same access_token/token_type/expires_in JSON contract as login and set a replacement cookie. The predecessor is revoked and linked to its successor in one transaction; the successor preserves the family and original expiry. Account row locks serialize rotation, with refreshed row state after waiting.

Consumed-predecessor reuse revokes the whole user-scoped family and commits before returning 401 `{"detail":"Authentication required."}`. Concurrent use produces at most one successful rotation; the replay request then revokes that family, including the winner. Revoked, expired, malformed, unknown, or missing refresh cookies never create a session. Unexpected database failures return the existing generic authentication 500 contract. Responses/errors/logs contain no refresh credential or digest.

## POST /auth/logout

With valid Origin and CSRF, revoke only the presented cookie's user-scoped family and return 204. Clear the cookie with matching name, host-only domain behavior, path, HttpOnly/SameSite/Secure attributes. Repeated, expired, or already-revoked known cookies remain idempotent with their family-bound CSRF.

Absent, malformed, or unknown cookies identify no family and cause no database mutation; for this state-free idempotent case an allowed Origin and well-formed CSRF header are still required, but there is no known session to bind against. Clear the cookie and return 204 without affecting any other user's/family's state. Missing/invalid Origin or CSRF shape still returns 403.

User-wide transactional revocation is exposed for later password/reset/deletion/admin workflows; those endpoints remain out of scope here. No schema/dependency change was needed for rotation/logout. Prior access-only tests/contracts were migrated to require sid, one login session, and the secure refresh cookie while retaining signature/claim/eligibility checks.


## Browser session client

The React provider restores each page load using credentialed GET /auth/csrf, POST /auth/refresh with X-CSRF-Token, then Bearer GET /auth/me. Protected placeholders stay hidden during confirmation. Login sends the normalized university email and untrimmed password, then confirms /auth/me and bootstraps CSRF before showing authenticated navigation. Access/CSRF values remain in provider memory; refresh cookies are managed by the browser. No credentials are stored in browser storage, URLs, logs, or debug markup.

Shared authenticated **GET** requests include credentials and Bearer authorization. Simultaneous 401 responses share one refresh; each original GET retries at most once. Already-renewed credentials are reused instead of replaying rotation. Failed refresh, repeated rejection, and 403 stop recovery and remove protected access with session-expired/unavailable feedback. Unsafe mutations, refresh, login, and logout are never automatically replayed.

Only exact /marketplace, /profile, /my-listings, and /account/password are valid internal return destinations, held in memory. Unknown paths and /admin remain unavailable even for verified students. Sign-out waits for server 204 before clearing client state; network/server failure retains access and explicitly asks for retry without claiming revocation. Marketplace/My Listings remain placeholders until their own issues implement content; the password screen is available below.


## POST /auth/change-password

Requires the same verified, active session-bound Bearer guard. Accept exactly `current_password` and `new_password`, strict secret strings of 12–128 characters with spaces preserved. There is no caller-supplied account identifier. This Bearer-authenticated mutation is submitted explicitly and never automatically retried by the browser client; ambient cookies alone cannot authorize it.

| Status | Response | Meaning |
| --- | --- | --- |
| 204 | Empty body; matching refresh-cookie deletion | Password changed and every account session revoked |
| 400 | `{"detail":"Current password is incorrect."}` | Current password proof failed; hash/sessions unchanged |
| 401 | `{"detail":"Authentication required."}` | Missing/expired/revoked access or current account/session ineligibility |
| 422 | `{"detail":"Invalid password-change request."}` | Missing/extra fields, wrong types, or length violation |
| 500 | `{"detail":"Authentication is temporarily unavailable."}` | Database failure; transaction rolled back |

The service locks the acting account, rechecks access/family eligibility after waiting, verifies the current Argon2id hash, writes a new Argon2id hash, and revokes all refresh families in one transaction. Login rechecks its previously verified hash under the same account lock before session creation; rotation also uses that lock. A pre-change credential cannot leave an active session after the change. Other accounts, email/flags/role, and profile fields are untouched. Responses and logs do not expose passwords, hashes, or credentials.

The protected /account/password screen has current/new/confirmation inputs; confirmation is client-only. Confirmed 204 clears password inputs and in-memory authentication and explains that all sessions were revoked before returning to sign-in. Wrong-current/network/server failures preserve an honest retry state and make no success claim; access failures hide protected content. Forgotten-password recovery is not implemented by this endpoint.


## POST /auth/forgot-password

Public endpoint accepting exactly the strict normalized university `email`. Only verified, unsuspended existing accounts can receive a six-digit password_reset-purpose code. Unknown/deleted/unverified/suspended accounts remain unchanged. Reset issuance takes the account lock, has a sixty-second cooldown from the latest reset issuance, and stores only the user/purpose-bound keyed digest with ten-minute expiry. Successful replacement invalidates earlier usable reset codes independently of registration codes.

Every valid request receives 202 with Retry-After:60 and `{"detail":"If this address is eligible, a password-reset email may arrive. Retry after 60 seconds."}`. This is identical for eligible issuance, cooldown suppression, unknown/ineligible accounts, and SMTP failure, including missing provider settings. Delivery failure rolls back the attempted new code and earlier-code invalidation. The response never guarantees delivery. Invalid request fields/types/email receive sanitized 422 `{"detail":"Invalid recovery request."}`; unexpected database failure uses generic 500 authentication-unavailable feedback.

## POST /auth/reset-password

Public endpoint accepting exactly strict `email`, a secret `code` of six ASCII digits without trimming/coercion, and strict secret `new_password` of 12–128 characters with spaces preserved. Invalid inputs receive sanitized 422 `{"detail":"Invalid password-reset request."}`. Unknown/ineligible users, incorrect/expired/consumed/invalidated/exhausted/purpose-mismatched codes share 400 `{"detail":"Password-reset code is invalid or unavailable."}`.

Wrong well-formed attempts against the current usable reset code commit even when the router returns 400; the fifth invalidates it. Account/code locks serialize attempts, issuance and consumption. Time is sampled after locking; expiry is inclusive at ten minutes. A successful code is consumed once, a new Argon2id password hash is written, and every refresh family is revoked in one transaction. Any transaction failure rolls back all three changes and returns sanitized 500. Verification/identity/profile and other accounts are preserved. Login's under-lock verified-hash check and refresh's account lock prevent pre-reset credentials from creating an active old session after reset.

Success returns 204 with matching refresh-cookie deletion and no JWT/automatic login. Old passwords and previous access/refresh credentials fail immediately; the new password signs in normally. Plaintext reset codes, passwords, hashes and tokens are never returned or logged.

The public /forgot-password and /reset-password forms are reachable from sign-in. The first gives generic eligible-address feedback and a sixty-second cooldown; only email/cooldown remain in React memory across navigation. Direct reset allows email re-entry. Code/password/confirmation stay in form memory, and only email/code/new_password are submitted. Confirmed success clears secrets/auth state and returns to sign-in with all-session revocation guidance. Failures give safe recovery guidance without revealing status or claiming success. Mutations are never automatically replayed.


## Own-profile endpoints: GET /users/me and PATCH /users/me

Both endpoints use the existing current verified, unsuspended, session-bound Bearer guard; cookie possession alone is insufficient. No caller-supplied identifier selects an account. GET returns exactly id, email, verified, name, phone, telegram_username, and external_contact_url. Existing unset personal/contact fields are null, without fabricated defaults. /auth/me retains its original id/email/verified-only contract. Avatar paths and all security fields are excluded; private own-photo access is available through the separate endpoint below.

PATCH accepts a nonempty object containing only name, phone, telegram_username, and external_contact_url. Omitted fields remain unchanged; explicit contact null clears that field. Supplied name cannot be null: it is trimmed, nonblank, and 1–100 characters. Phone is `+` followed by 7–15 ASCII digits; Telegram username is 5–32 ASCII letters/digits/underscores. Blank non-null contact strings and wrong types are invalid. External contact URL is at most 2048 characters, HTTPS with a syntactically valid DNS/IP hostname and valid optional port, no credentials, whitespace or control characters. Unsafe schemes are rejected.

Profile editing can leave every contact empty; at least one valid contact is required only by future listing submission. Email/id/role/verified/suspended/password/hash/avatar/session fields and all other unknown keys are forbidden. No partial write occurs on invalid input. The acting account is locked/reloaded and access/family eligibility is rechecked after waiting; a stale guard cannot update an account that became ineligible or revoked. Email, eligibility, role, password, avatar, sessions, and all other accounts remain unchanged.

Successful GET/PATCH returns 200 with the same public own-profile shape. Missing/expired/revoked/ineligible authentication returns the existing sanitized 401 authentication-required contract. Invalid PATCH returns 422 `{"detail":"Invalid profile request."}`; database failure returns 500 `{"detail":"Profile is temporarily unavailable."}` and rolls back the whole update. Credentialed CORS explicitly permits PATCH only for configured frontend origins. These endpoints support the React editing screen described below; private avatar controls are documented below.


## React own-profile screen

Protected /profile now loads GET /users/me with the shared authenticated client, shows loading feedback, and offers retry on an unconfirmed load. Verified university email is read-only; initial null name/contacts appear empty. Name and contact inputs mirror the API rules with labeled format hints. All contacts may be empty.

Saving submits only changed permitted fields through explicit authenticated PATCH, without automatic mutation replay. Name changes are trimmed; untouched initially null name is omitted, and empty contact edits send null. Empty/duplicate pending saves are blocked. Confirmed returned profile values become the new authoritative form baseline and show save confirmation. Validation/network/server failure preserves edits without claiming success; authorization failures remove protected content through the shared client. No personal fields are written to URLs/storage/logs/debug output. Private profile photos are documented below; seller-contact display remains a separate feature.


## Private own-profile photo: /users/me/avatar

All operations require current verified, unsuspended session-bound Bearer access and take the acting account lock with an eligibility recheck. No id/filename selects another account. POST accepts exactly one multipart file field named image, no additional files/fields. Browser requests use FormData with the browser-generated multipart boundary; do not manually set Content-Type. DELETE is idempotent. GET streams only the acting user's canonical image, returns the decoded format's image/jpeg, image/png or image/webp type, and uses Cache-Control:private,no-store plus nosniff. Missing photo/file returns sanitized 404. No public uploads mount or token query URL exists.

Input is limited to five MiB (5 × 1024 × 1024 bytes), with one overflow byte check; multipart body parsing also has a bounded 64 KiB overhead allowance. Actual decoded content must be JPEG/PNG/WebP and at most 20,000,000 pixels. MIME/extension cannot authorize content; malformed/truncated/unsupported/SVG/decompression-bomb input is rejected. Images are re-encoded from fresh pixels with embedded metadata/EXIF removed. Original filenames never become paths or response fields.

POST/DELETE return 200 with a safe detail and cleanup_pending boolean. POST detail is Profile photo updated.; DELETE detail is Profile photo removed. Invalid form/image content returns sanitized 400; excessive input bytes return 413. Missing/ineligible/revoked credentials return 401; storage/database failure returns sanitized 500. There are no filesystem paths, original names, hashes or credentials in these responses.

Generated owner-specific relative paths are stored only in User.avatar_path beneath configured UPLOAD_DIR. Storage verifies canonical confinement and rejects traversal, symlink/junction escape, and paths belonging to another owner before reading/writing/deleting. Replacement/removal updates the path under the account lock; failed database writes/commit remove the new file and preserve the previous avatar. After commit, superseded-file removal is best effort. cleanup_pending:true honestly reports committed success with unfinished old-file cleanup. If filesystem removal also fails during rollback, an unreferenced generated file may remain: database and filesystem are not one atomic transaction. Operators must reconcile only verified unreferenced generated paths inside UPLOAD_DIR; never broadly delete a directory or unrelated paths.

/profile now includes optional upload/replace/remove controls and format/size guidance. Current images are fetched with Bearer+credentials as binary blobs; local object URLs are revoked on replacement/unmount. Tokens never enter img src. Pending duplicates are blocked; failures retain the previous preview and show safe retry guidance. Seller-photo display remains future; listing-photo operations are documented separately below.


## Listing/report representation

Revision 0003_listings follows 0002_accounts and adds exactly categories, listings, listing_photos, and listing_reports. Fixed category ids/keys/names are 1/electronics/Electronics, 2/clothing/Clothing, 3/books/Books, 4/furniture/Furniture, and 5/other/Other. Keys/names are unique and the fixed mapping is constrained; referenced category deletion is restricted.

Listing owner FK cascades from users; category FK is required. Title is trimmed and 3–120 characters, description 10–2000. Price is PostgreSQL NUMERIC(12,2), 0 through 1,000,000,000 inclusive, with currency constrained to KZT. This is exact decimal storage, but PostgreSQL coerces excess input scale (1.005 becomes 1.01); the future creation API must explicitly reject more than two decimal places before insertion. Condition tokens are new/used. Creation/publication timestamps are timezone-aware.

State tokens are pending, active, sold, rejected and removed. New rows default pending with null publication; pending cannot carry publication. Active/sold require publication, rejected requires a nonblank rejection_reason of at most 300 characters, and administrative removed is representable. No hidden/pause/expiration state exists. These are persistence rules; manual approval/rejection services and seller hard-delete behavior are later issues.

Photos contain only listing FK, generated relative storage_path and position 1–5 (plus row id). Paths use listings/<listing_id>/<32 lowercase hex>.(jpg|png|webp), are globally unique, and cannot contain traversal/absolute/external paths. Unique listing/position gives at most five slots; the lowest stored position is the derived main image without a separate flag. This metadata does not create, expose, validate or clean disk files.

Reports reference reporter/listing, with reasons spam, prohibited_items or misleading_information and timezone-aware created_at/nullable reviewed_at. Review cannot predate creation. There is no evidence text, reporter tracking or user-targeted report workflow. Owner deletion cascades listing/photo/report rows; reporter deletion cascades their reports. Indexes cover owner/status, active publication discovery, ordered photo slots, reporter/listing and unreviewed report lookup. Submission authorization is implemented below; disk cleanup and browsing are documented below; report endpoints and admin controls remain future work.


## POST /listings

Protected submission accepts exactly title, description, price, category_id, and condition in application/json. Title and description are strict strings trimmed before validation, with 3–120 and 10–2000 characters respectively; NUL text is rejected before database insertion. Category id is a strict integer 1–5 matching the fixed seeded categories; condition is exactly new or used. Missing/null/coerced/extra fields are rejected, including owner/id/status/currency/publication/rejection/photo input. JSON parsing rejects duplicate keys, malformed/nonfinite constants, and oversized request bodies (64 KiB).

Price accepts a finite standard JSON number (including standard JSON exponent notation) or an unsigned canonical decimal string matching `(0|[1-9][0-9]*)(.[0-9]+)?`, where the period is literal. Strings cannot use signs, exponent notation, whitespace, leading-zero integers, incomplete decimals, commas or hexadecimal. Boolean/null/container values are invalid. JSON decimal numbers are parsed directly as Decimal rather than binary float. Amounts must be 0 through 1,000,000,000 and have at most two meaningful fractional digits; trailing zeroes are insignificant, so 12.3400 is valid while 1.005 is rejected. Validation occurs before Numeric coercion, with no silent rounding; output always uses a canonical two-decimal string and zero is 0.00.

Creation locks/reloads the guard-established account, revalidates current token/family and verified/unsuspended eligibility after waiting, and requires at least one currently valid phone/Telegram/HTTPS contact from the existing profile formats. Invalid legacy contacts do not satisfy the prerequisite; any one valid contact is enough. A name is not an additional creation prerequisite. Missing contact returns safe profile guidance without a row. Identity/status/publication fields are server-controlled, and new listings are pending with no publication date under mandatory manual approval.

201 returns exactly id (server-generated bigint), title, description, price, currency=KZT, category_id, condition, status=pending, timezone-aware created_at and published_at=null. No owner/contact data, credentials, paths or photos are returned. Invalid request returns 422 `{"detail":"Invalid listing request."}`; missing valid contact returns 400 `{"detail":"Add a valid contact method to your profile before creating a listing."}`; missing/currently ineligible access returns existing sanitized 401; database/service failure returns 500 `{"detail":"Listings are temporarily unavailable."}` and rolls back. Photo upload is a separate operation documented below; the creation UI is documented below; browsing/detail endpoints and approval controls remain future work.

## GET /categories

Protected by the same current verified session-bound guard. Return an array in stable id order, each with exactly id, key and label: Electronics, Clothing, Books, Furniture, Other (1–5). Invalid/ineligible access returns sanitized 401; database failure returns the same safe listing-unavailable 500 contract. No category mutation endpoint exists.


## Private listing photos

POST /listings/{listing_id}/photos accepts exactly one multipart file field named image and returns 201 with exactly id, listing_id, position, is_main and url. The url is /listings/{listing_id}/photos/{photo_id}, a protected binary route without query credentials or a raw storage path. Bigint path identifiers must be positive and within their database range. Only the current authenticated owner of a pending listing can append; missing/non-owned listings share safe 404. Active/sold/rejected/removed listings reject edits with 409. Five photos is the maximum; a sixth returns 409 with no new metadata/file.

The acting account is locked first, current eligibility/family checked, then the listing is locked and ownership/state reread. Append assigns the next one-based position; concurrent attempts at the fifth slot yield only one success. Position one is the first-uploaded main image. There is no replacement/removal/reordering endpoint here; published/rejected photos are immutable. Shared bounded multipart and decoded-image helpers retain five-MiB/twenty-million-pixel JPEG/PNG/WebP validation, metadata-free re-encoding and generated confined paths in the listings namespace, independently of avatars. Invalid content/overflow returns safe 400/413; database/storage failure rolls back metadata and attempts new-file cleanup without touching prior/unrelated photos. As with avatars, an unrecoverable rollback cleanup failure can leave an unreferenced generated file; no cross-resource atomicity is claimed.

GET /listings/{listing_id}/photos/{photo_id} verifies exact linkage and current verified session eligibility. Owners can read their pending/active/sold/rejected photos. Other verified buyers can read only active listings with a currently verified, unsuspended seller. Removed listings, missing/mismatched images and forbidden states share 404. No admin privilege is inferred from verification. Invalid/revoked/ineligible viewers receive 401. Successful binary responses use the canonical image type, private/no-store cache and nosniff. No public uploads mount, token URL or raw filesystem path is exposed. Storage and database exceptions are sanitized; malformed identifier input returns safe 422. The React selection/upload UI is documented below; admin unpublished review belongs to later issues.


## React new-listing form

Protected /listings/new loads fixed categories with loading/error/retry and offers labeled title/description/KZT-price/category/condition fields. Client validation uses the exact creation limits and canonical decimal-string arithmetic, including excess meaningful fractional precision rejection; POST contains only the five allowed fields. Missing contact guidance links to the real /profile screen. Optional selection is zero through five JPEG/PNG/WebP files up to five MiB each, with ordered object-URL previews and first-as-main labeling. Unsubmitted selections can be removed/replaced and object URLs are revoked on change/unmount.

The form preserves one confirmed metadata id in memory and uploads photos sequentially with only image multipart fields. Each valid confirmed response advances the saved count/order. Pending duplicate mutations are blocked; retries never recreate metadata after its confirmed boundary. Explicit 4xx rejection permits correction/removal and retry of only remaining files. Network errors, every 5xx, or invalid/missing success payload are uncertain: the form blocks blind retries because the mutation may already have committed. This applies independently to metadata and each photo; no listing/photo lookup endpoint is fabricated. Counts distinguish confirmed photos from unconfirmed selections and partial failure never claims full completion/publication.

Completed creation reports the id and Pending manual admin review, with an available profile action. Draft fields/files/confirmed boundaries stay only in this mounted form's memory, not URLs/storage/logs/debug output; reloading/leaving discards them, so keep the page open while completing photos. My Listings review is now available below; it does not automatically reconcile uncertain creation/upload mutations. Protected navigation includes this exact internal route; no external return paths are accepted.


## Owner price/description editing

Protected GET /listings/{id}/edit returns exactly id, title, canonical two-decimal price, description, status and published_at for the authenticated owner. Missing/non-owned ids share 404 without contact/gallery/security/path data. Positive bigint identifiers are bounded to the database range. The read can represent all persisted statuses so the form can explain unavailable editing; it is not a discovery/dashboard endpoint.

Protected PATCH /listings/{id} accepts a nonempty partial object containing only price and/or description. Omitted fields are preserved; supplied null, empty body, unknown/coerced/immutable fields are rejected. Description is trimmed to 10–2000 characters, and price uses the same exact Decimal JSON/canonical-string/range/meaningful-precision rules as creation, before Numeric coercion. Duplicate/malformed/nonfinite JSON is rejected. Creation's Pending-only DTO remains separate and unchanged.

The acting account is locked/rechecked before the listing, followed by current ownership and state checks. Only pending, active and sold permit price/description updates. Rejected requires deletion/recreation and removed cannot be edited. State, title, owner, category, condition, photos/order and creation/publication timestamps are preserved; Pending is never automatically published, and published changes retain approval without renewed review. Successful PATCH returns the same authoritative six-field editing DTO.

GET/PATCH use existing sanitized 401 for stale/ineligible access, 404 `{"detail":"Listing is unavailable."}` for missing/non-owned records, and 500 listing-unavailable feedback with transaction rollback. Invalid PATCH returns 422 `{"detail":"Invalid listing-edit request."}`; forbidden mutation returns 409 `{"detail":"This listing cannot be edited. Rejected listings must be deleted and recreated."}`. No account/contact/gallery/credential/driver data is exposed.

The exact protected /listings/{id}/edit browser route loads current values with retry, displays title/status/publication read-only, and edits only price/description. Changed-only PATCH, no-change/pending prevention, exact price strings and returned-baseline confirmation preserve the contract. Failure retains edits and never claims an unconfirmed save; stale forbidden-state response blocks saving until explicit state reload. Current Rejected/Removed records are read-only. The confirmed new-listing result offers an edit link to its known id; no dashboard/discovery feature is fabricated. Mutations are never automatically replayed, and dynamic return destinations require exact positive bounded id paths.


## GET /listings/mine and seller dashboard

The fixed mine route is registered before dynamic listing-id routes. Current verified, unsuspended session-bound ownership is derived only from the authenticated account, rechecked under its account lock. Only limit, offset and status query keys are permitted; duplicate/unknown/owner/user keys are rejected. Pagination defaults to limit=20, offset=0; limit is 1–50 and offset is a canonical unsigned integer 0–9,223,372,036,854,775,807. Optional status is exactly pending/active/sold/rejected/removed. Invalid queries receive 422 `{"detail":"Invalid My Listings query."}`; authentication and database errors use existing sanitized 401/500 contracts.

Return an object with items, total, count, limit, offset and status (null for all states). total applies to this owner and status filter; count is this page length. Sort by created_at descending, then id descending for stable ties. Each own item contains id/title/description/canonical two-decimal KZT price/currency/category_id/condition/status/created_at/published_at/rejection_reason/photos. Rejection reason is supplied only for rejected records. Photo summaries are ordered by position and include id/position/is_main/protected binary url without raw paths. Lowest position is main. Removed records return no photo URLs (photos=[]). Other owners/contacts/security fields are never exposed.

Protected /my-listings has All/Active/Sold/Pending/Rejected/Removed filters, loading/error/retry/empty states and twenty-item page controls. Cards show title/price/status and private authenticated main-image blobs (or a useful no-photo state), revoking object URLs on view changes/unmount. Pending guidance and rejection reasons remain private and honest; Removed images are not fetched. Only Pending/Active/Sold offer the working edit form, and Create listing links to the existing form. The Sold action is documented below; approval/detail actions remain unavailable. Creation's confirmed/uncertain boundary now has a real My Listings review link; it still never auto-retries or guesses uncertain mutation success.


## POST /listings/{id}/sold

Current verified owner access is required, with positive bounded bigint ids. Accept no query parameters or fields: body may be absent or an empty JSON object only (bounded one KiB). Invalid input returns safe 422, missing/non-owned records share 404, ineligible/revoked access uses 401. Account then listing locks recheck current eligibility/ownership/state. Active becomes sold; already sold returns success idempotently. Pending/rejected/removed return 409 `Only Active listings can be marked Sold.` without mutation.

200 returns authoritative id/status=sold/published_at. Only status changes: title/description/price/category/condition/owner, creation/publication times, photos/files/order and reports are preserved. Database failure uses sanitized listing-unavailable 500 with rollback. Sold remains in the owner Sold view, leaves Active and denies ordinary buyer photo access; the owner retains private photos. There is no undo/reactivation endpoint.

Active dashboard cards offer inline Confirm Sold/Cancel, explain irreversible buyer access loss, block duplicate pending clicks and reload authoritative owner data only after confirmed success. Failure shows retry/review guidance without claiming Sold or automatically replaying the request. Other statuses have no Sold action.

## DELETE /listings/{id}

Current verified, unsuspended owner access is rechecked under account then listing locks. Positive bounded bigint ids and an absent body or empty object only are accepted; query parameters and fields receive sanitized 422. Missing and non-owned records share 404. Every owned listing state can be permanently deleted. Database deletion cascades photo/report rows while preserving accounts, other listings and their data. Generated photo paths are checked before mutation; failed commit preserves records and files. Only after successful commit are the captured, confined photo files removed. Missing files are harmless; cleanup failure still returns 200 `{ "id": 7, "deleted": true, "cleanup_pending": true }`. Completed cleanup returns false. No storage paths or driver details are exposed.

Every dashboard state offers permanent deletion confirmation and cancellation. Pending clicks cannot duplicate requests. Confirmed deletion reloads authoritative data, moving an empty last page to the nearest valid page. An uncertain response never claims deletion or automatically retries; a review button reloads My Listings. Photo cleanup pending is shown separately from confirmed record deletion. Operator recovery is documented in local setup.

## GET /listings — protected marketplace feed

Only currently verified, unsuspended viewers with an active, unexpired session family can browse; authentication failures return safe 401. The read-only feed includes only Active listings with publication timestamps and existing, verified, unsuspended sellers, even when the viewer owns a private listing. Sort is publication date descending, then id descending. My Listings remains a separate owner view.

Only limit, offset, q, category_id, condition, min_price and max_price query parameters are accepted, without duplicates. Defaults are twenty/zero; limit is 1–50 and offset is a canonical unsigned integer 0–9,223,372,036,854,775,807. Unknown keys, invalid values, sorting/status/owner overrides receive 422 `{"detail":"Invalid marketplace query."}`. Parameterized SQLAlchemy queries share the same visibility predicates for rows and totals. Database errors return sanitized listing-unavailable 500.

200 returns items/total/count/limit/offset. Empty and beyond-end pages are valid. Each card contains only id/title/canonical two-decimal KZT price/currency/category_id/condition/published_at/main_photo. main_photo is null without photos, otherwise id/position/is_main=true/protected binary url for the lowest ordered photo. No descriptions, seller contact/profile/email/security data, rejection reasons, paths or tokens are returned. The existing authenticated photo endpoint still checks current visibility and linkage; there is no public image mount or token URL. Keyword search is documented below; filters are documented below; the working marketplace screen is documented below; details/contact are documented below.


## GET /listings keyword search

Optional q is at most 200 decoded characters before trimming. Outer whitespace is trimmed; absent/empty/whitespace-only text means ordinary browsing. Unicode control characters (including C0/C1 controls) are rejected, as are duplicate q and unknown keys, using the same sanitized marketplace-query 422 without echoing search text.

Nonblank q performs a parameterized, case-insensitive literal substring match against title OR description. Percent, underscore and the chosen escape character (!) are escaped as literal text; quotes and SQL-looking strings cannot change the query. Unicode comparison follows PostgreSQL's configured case-insensitive text comparison. This is simple substring search: no stemming, relevance ranking, accent folding or search engine is promised.

The same keyword and visibility predicates determine items and total; publication date/id descending order, bounded paging, safe card fields and authenticated main-photo access remain unchanged. No matches return an ordinary empty page. Matching description content does not expose full descriptions in cards. The working search/filter UI is documented below; listing details are documented below.


## GET /listings category, condition and price filters

Optional category_id is a canonical positive integer matching fixed ids 1–5; condition is exactly new or used. Optional min_price/max_price use creation's unsigned decimal-string syntax: zero or a nonzero-leading integer, optionally followed by a decimal point and digits. No signs, exponent, whitespace, bool-like/nonfinite values, empty values or leading zeros are accepted. Values are exact Decimal, finite and between zero and 1,000,000,000, with at most two meaningful fractional digits; trailing fractional zeros are allowed without rounding. min_price must not exceed max_price.

Each supplied filter combines with AND, including keyword search and existing Active/published/eligible-seller predicates. Minimum and maximum are independently optional and inclusive; equal bounds select an exact price. Omitted filters do not narrow the feed. Duplicates, unknown keys and invalid/overflow values use the existing sanitized 422. Items/totals use identical predicates, retain publication/id descending order, bounded pagination, safe cards and protected main-photo URLs. No matches are valid empty pages. The working UI is documented below; details are documented below.


## Protected marketplace screen

/marketplace uses the authenticated feed/category client and private binary photo routes. Signed-in Home/brand navigation leads here; anonymous users receive sign-in guidance without listing/image requests. Labeled search, category, condition and KZT min/max controls apply together on form submission (including Enter) or reset explicitly. Client validation mirrors decoded search/control and exact decimal/range rules; supported query keys are URL-encoded. Twenty-item page controls preserve applied filters, resetting offset on apply/reset, with server totals/counts and newest-publication order.

Responsive neutral cards show title, canonical KZT price, real category/condition/publication date and authenticated blob main photos or honest no-photo/error states. Loading categories/feed, empty results and safe retry errors are distinct. Page/card/photo linkage is checked before rendering or fetching; malformed data cannot become fabricated empty results. Effect generation guards prevent stale results/photos from replacing current queries, and object URLs are revoked on changes/unmount. Tokens stay in the existing memory-only auth client. Cards now link to genuine protected details described below; student reporting is documented below; admin actions remain later tasks without fabricated controls.


## GET /listings/{id} and listing details

The protected buyer endpoint accepts positive bounded bigint ids and rechecks current session eligibility. Only Active/published listings of verified, unsuspended existing sellers are returned. Missing/nonvisible rows share 404 `Listing is unavailable.`, including an owner's private states; owner edit/dashboard contracts are unchanged. Invalid ids receive sanitized 422, authentication 401 and database failure sanitized listing-unavailable 500.

200 detail fields are id/title/description/canonical two-decimal KZT price/currency/category_id/condition/published_at/photos/seller. Photos are position-ordered id/position/is_main/protected url summaries, with the lowest position main. Seller contains only name/phone/telegram_username/external_contact_url, revalidated under profile rules; invalid legacy or missing values become null. No university email, eligibility/role/security fields, rejection metadata or raw paths are returned. Contacts are current, not copied from submission.

Marketplace titles link to protected /listings/{id}. The screen validates id/photo linkage and contacts, displays title/description as literal text and has loading/retry/unavailable feedback. The accessible gallery starts on main and fetches selected images via authenticated blob routes, preserving order, guarding stale responses and revoking object URLs. Missing/error photos and missing contacts are honest. Fixed category ids map to the established category labels.

Contact Seller deterministically prefers https://t.me/<validated_username>, then a validated external HTTPS URL. A valid international phone gets a tel: link; when Telegram is preferred, the other valid external contact remains available separately. No WhatsApp action is fabricated. New-tab external links use noopener/noreferrer. No credentials, arbitrary schemes or access tokens are added to image/contact URLs. Negotiation, payment and pickup happen directly between users; chat and checkout remain outside the platform; student reporting is documented below.


## POST /listings/{id}/reports

Current verified, unsuspended session identity supplies the reporter. The exact JSON body is reason=spam/prohibited_items/misleading_information; missing/coerced/unknown reasons, duplicate/protected/extra fields (including comments/evidence) and query parameters receive safe 422. Bounded positive ids are required. Account then listing locks recheck current session and Active/published/eligible-seller visibility before writing. Missing/private/Sold/Removed/ineligible targets share 404. Own-listing reporting returns safe 400 `You cannot report your own listing.` without invalidating the account session. These own/duplicate rules are authorized simple defaults.

First and repeat success both return 202 `{ "accepted": true }`, with no ids, reporter/queue/review/contact data. Server id/time and reviewed_at=null are stored only on the first same-reporter/listing report. Repeated or concurrent submissions are serialized accepted no-ops preserving that original reason/time, even when a different reason is supplied. Different reporters retain independent reports. Commit failure rolls back and returns sanitized listing-unavailable 500. Reporting never automatically removes a listing or contacts admins externally; admin review/removal remains later work.

Visible detail pages have a labeled reason selector and explicit report submission, pending duplicate prevention, confirmed acceptance and safe failure feedback. Ambiguous failure never claims success/failure or automatically replays; explicit retry is safe through duplicate semantics. No free-text comment/evidence/reporter tracking is introduced.
