
# Backend API

Current capability: registration of an unverified student account only. No verification email/code, login, token issuance, activation, or marketplace authorization is available yet. The React preview does not call this API.

## POST /auth/register

Accept a JSON object containing exactly `email` and `password`.

- `email`: required string, trimmed and lowercased, syntactically valid, maximum 254 characters, with exactly the ASCII domain `sdu.edu.kz`. Subdomains, suffix lookalikes, Unicode domain aliases/lookalikes, and malformed addresses are rejected. Validation is local and does not make DNS requests.
- `password`: required string of 12–128 characters, with no coercion, trimming, or composition rule. It is stored only as an Argon2id hash.
- Unknown fields, missing fields, wrong types, invalid values, and malformed JSON are rejected before any account is persisted.

HTTP **201** returns only:

```json
{"id": 1, "email": "student@sdu.edu.kz", "verified": false}
```

The persisted account is unverified, unsuspended, and has role student. No email code, refresh session, access token, plaintext password, or password hash is returned. No code/session is created by this endpoint.

| Status | JSON body | Meaning |
| --- | --- | --- |
| 201 | id, normalized email, verified=false | Account created |
| 409 | `{"detail":"University email is already registered."}` | Normalized email already exists |
| 422 | `{"detail":"Invalid registration request."}` | Invalid request, no account created |
| 500 | `{"detail":"Registration is temporarily unavailable."}` | Unexpected database failure |

Uniqueness is enforced by PostgreSQL, including concurrent requests; the transaction rolls back on conflict and later requests can still succeed. Responses and application logs do not echo submitted passwords, validation inputs, hashes, URLs, or database credentials. Database exceptions are converted to a generic response rather than driver details. Abuse controls belong to the later security task.

## Application lifecycle

`backend.app.create_app(settings, database=None)` takes validated injected settings and optionally a borrowed Database. Owned infrastructure is disposed on shutdown; borrowed infrastructure remains the caller's responsibility. Importing app/main modules does not load settings or connect. Uvicorn explicitly calls `backend.main:create_runtime_app` with `--factory`; that runtime factory loads configuration and constructs a lazy engine. Apply migrations before registration requests.

OpenAPI is available at `/openapi.json`, with local interactive documentation at `/docs`. See [local setup](local-setup.md) for the tested startup command and the separately confirmed disposable PostgreSQL test contract.
