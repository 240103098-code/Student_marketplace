
# Backend API

Current capability: registration of an unverified student plus configured SMTP verification-code delivery. One-time verification and cooldown-limited resend are implemented below. Verified-user login, access JWTs, and the database-backed /auth/me guard are available below; refresh sessions and marketplace endpoints remain future work. The React preview does not call this API.

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

SMTP delivery uses configured real transport with verified TLS/STARTTLS before authentication, a ten-second network timeout, and connection cleanup. Delivery failures roll back the caller transaction, including new account/code state and replacement invalidation. Duplicate registration does not send another message. Code issuance can be reused internally for replacement and password-reset purpose; resend is available below, while password-reset endpoints remain future work.

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

Unknown email, incorrect password, unverified account, and suspended account all return 401 `{"detail":"Invalid credentials or account unavailable."}` with `WWW-Authenticate: Bearer`. A successful eligible login returns 200 with only access_token, token_type=bearer, and expires_in=900 by default (JWT_ACCESS_MINUTES times sixty). No refresh record, cookie, verification code, or email is created. The response token is sensitive: do not print or log it; future browser handling keeps it in memory.

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

Tokens contain no email, password/hash, code, profile/contact data, role, or eligibility flags. Validation uses an explicit HS256 allowlist, required issuer/audience/claims, strict canonical claim types and subject/id bounds, and the same configured duration. It rejects extra claims, malformed/incorrect signatures or algorithms, missing claims, wrong issuer/audience/purpose, expiry at its exact boundary, and future issued-at time. Signature/issuer/audience validation stays in PyJWT; explicit UTC-clock time checks allow deterministic tests without bypassing those checks.

## GET /auth/me

Send `Authorization: Bearer <access token>`; no cookie authentication is available yet. The shared require_verified_user dependency validates the token and reloads current account state from PostgreSQL on every request. Deleted/missing, unverified, or suspended accounts are rejected even while a signed token is unexpired. Success returns only id, normalized email, and verified=true; no profile editing or listing data is implemented here.

Missing/malformed Bearer credentials, invalid/expired tokens, and current ineligibility return 401 `{"detail":"Authentication required."}` with `WWW-Authenticate: Bearer`. Unexpected database errors on login/me return generic 500 `{"detail":"Authentication is temporarily unavailable."}`. Error responses and application logs do not echo credentials, tokens, raw validation input, or driver details.

Current authentication is access-only: refresh rotation/cookies/logout/session-based revocation are the next task. Account suspension, unverification, and deletion already take effect through the database-backed guard. React login/protected navigation and full profile workflows remain future work.
