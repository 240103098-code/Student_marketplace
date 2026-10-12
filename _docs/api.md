
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

/profile now includes optional upload/replace/remove controls and format/size guidance. Current images are fetched with Bearer+credentials as binary blobs; local object URLs are revoked on replacement/unmount. Tokens never enter img src. Pending duplicates are blocked; failures retain the previous preview and show safe retry guidance. No seller-photo/listing-photo feature is implemented here.


## Listing/report representation (no listing API yet)

Revision 0003_listings follows 0002_accounts and adds exactly categories, listings, listing_photos, and listing_reports. Fixed category ids/keys/names are 1/electronics/Electronics, 2/clothing/Clothing, 3/books/Books, 4/furniture/Furniture, and 5/other/Other. Keys/names are unique and the fixed mapping is constrained; referenced category deletion is restricted.

Listing owner FK cascades from users; category FK is required. Title is trimmed and 3–120 characters, description 10–2000. Price is PostgreSQL NUMERIC(12,2), 0 through 1,000,000,000 inclusive, with currency constrained to KZT. This is exact decimal storage, but PostgreSQL coerces excess input scale (1.005 becomes 1.01); the future creation API must explicitly reject more than two decimal places before insertion. Condition tokens are new/used. Creation/publication timestamps are timezone-aware.

State tokens are pending, active, sold, rejected and removed. New rows default pending with null publication; pending cannot carry publication. Active/sold require publication, rejected requires a nonblank rejection_reason of at most 300 characters, and administrative removed is representable. No hidden/pause/expiration state exists. These are persistence rules; manual approval/rejection services and seller hard-delete behavior are later issues.

Photos contain only listing FK, generated relative storage_path and position 1–5 (plus row id). Paths use listings/<listing_id>/<32 lowercase hex>.(jpg|png|webp), are globally unique, and cannot contain traversal/absolute/external paths. Unique listing/position gives at most five slots; the lowest stored position is the derived main image without a separate flag. This metadata does not create, expose, validate or clean disk files.

Reports reference reporter/listing, with reasons spam, prohibited_items or misleading_information and timezone-aware created_at/nullable reviewed_at. Review cannot predate creation. There is no evidence text, reporter tracking or user-targeted report workflow. Owner deletion cascades listing/photo/report rows; reporter deletion cascades their reports. Indexes cover owner/status, active publication discovery, ordered photo slots, reporter/listing and unreviewed report lookup. Authorization, disk cleanup, listing/report endpoints and admin controls remain future work.
