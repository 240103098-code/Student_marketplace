# Local MVP security boundaries — 2026-10-19

This is a focused implementation/regression record for issue 39. It is not a vulnerability scan, production-readiness certification or complete security guarantee. No dependency scanner was run for this change. External SMTP credentials, actual inbox delivery and production TLS/proxy deployment remain operator setup and have not been verified.

## Enforced abuse limits

| Operation | Identity | Fixed window limit |
| --- | --- | --- |
| Registration attempts, including malformed bodies | Actual peer IP | 10/hour |
| Failed login | Normalized email plus actual peer IP | 10/15 minutes |
| Recovery initiation | Actual peer IP | 10/hour |
| Email-send requests across register/resend/recovery, before account lookup | Normalized email | 5/hour |
| Refresh attempts | Actual peer IP | 60/minute |
| Listing creation | Current guarded user | 10/hour |
| Report submissions, including safe repeats | Current guarded user | 10/hour |
| Avatar/listing-photo uploads combined | Current guarded user | 30/hour |

The existing 60-second successful email-issuance cooldown and five wrong code attempts remain separate. Email request quotas apply equally to unknown/ineligible accounts and cooldown requests, without claiming an email was delivered. Each window begins at its first admitted request and resets at expiry; Retry-After is a positive ceiling in seconds. Rejected requests perform no account/code/session/file mutation or SMTP send. Login reserves a slot before credential lookup so concurrent failures cannot exceed ten, then refunds successful/non-credential-error attempts; in-flight reservations can temporarily reject concurrent successful logins conservatively. Failed attempts remain counted. Authenticated quotas run only after the existing guard; service locks still recheck stale eligibility.

The standard-library limiter uses a lock for atomic checks/increments/refunds and a maximum of 10,000 active keys per application instance. Keys are process-salted HMAC digests of quota identities; raw submitted email, peer identifiers, passwords, codes and tokens are not retained in counters/diagnostics. Expired keys are pruned on admission. Capacity exhaustion fails closed with generic 429/Retry-After:60 instead of evicting live counters. Successful login refunds only its own reservation, never other failures or a later window. Response/error diagnostics contain no submitted identities. No persistent or distributed guarantee is implied: process restart clears counters, multiple workers multiply limits, and trusted clock rollback can extend a window. Run this local MVP as one process; distributed/persistent limiting is outside scope.

Client identity is the ASGI connection peer; application code ignores X-Forwarded-For. Start Uvicorn with --no-proxy-headers so a supplied forwarded header cannot rewrite that peer before the application. Do not put this configuration behind a proxy and assume per-browser identity: every client may share its proxy peer. Production proxy trust, TLS termination and a distributed store require separate operator design.

## Transport, caching and concrete fixes

All write/action bodies except actual POST avatar/listing-photo multipart routes are streamed into a buffer capped at 64 KiB before FastAPI parses them. Actual chunk bytes are counted; Content-Length is not trusted. Listing JSON retains its established safe 422 oversize contract; other oversized bodies receive safe 413. A fake multipart Content-Type on a JSON route cannot bypass the cap. An interrupted body returns safe 400 before route mutation. Existing stricter empty-action limits remain in force.

Multipart image routes count actual transport bytes up to one five-MiB image plus 65,536 bytes framing, accept exactly one image and no extra fields, and retain decoded-type/pixel/re-encoding/storage checks. The parser now explicitly closes every allocated spooled file on normal completion, overflow, malformed framing, disconnect and cancellation; Starlette's default cleanup previously covered only its multipart exception path. This concrete abort gap is fixed without changing upload permissions. App limits cannot prevent a server/proxy from prebuffering an entire incoming chunk before ASGI; production body/time/concurrency limits remain operator responsibilities.

Responses passing through the application boundary receive Cache-Control: private, no-store and X-Content-Type-Options: nosniff, including sensitive auth/account/admin/private-image errors and quota responses. Exact credentialed CORS remains outside the boundary so approved-origin errors still expose Retry-After; preflight remains governed by CORS. Tokens remain memory-only on the client and never appear in URLs. Frontend registration/login/recovery/resend/create/report/upload controls show 429 Retry-After guidance without success/delivery claims or automatic mutation replay; confirmed partial photo uploads remain preserved.

## Endpoint/role/state regression matrix

| Boundary | Concrete evidence |
| --- | --- |
| Atomic quotas, exact reset, capacity/no active eviction, hashed key privacy | tests/test_abuse.py LimiterTest |
| Actual streamed JSON overflow/abort, false Content-Length, fake multipart bypass | tests/test_abuse.py StreamingBoundaryTest |
| Multipart overflow/disconnect/truncated form, allocated spool closure | tests/test_abuse.py StreamingBoundaryTest.test_multipart_overflow_abort_and_malformed_close_allocated_spools |
| Email unknown/eligible/cooldown quotas; registration/recovery IP; no SMTP/DB mutation | tests/test_abuse_integration.py email_request_limit and registration_and_recovery cases |
| Concurrent failed login pair, success refunds, exact reset and capacity rejection | tests/test_abuse_integration.py login cases |
| Refresh quota and unchanged sessions; per-user create/report/upload limits and isolation | tests/test_abuse_integration.py refresh/listing/avatar cases |
| Safe caching, private image denial and credentialed CORS on overflow | tests/test_abuse_integration.py sensitive_headers case |
| Unverified/suspended/deleted/revoked users and required JWT claims | tests/test_login_integration.py, test_tokens.py, test_sessions_integration.py |
| Code purpose/exhaustion/replay; password/session revocation; SMTP verified TLS and rollback | tests/test_verification_integration.py, test_recovery_integration.py, test_password_change_integration.py, test_mail.py, test_smtp_integration.py |
| Own profile/listing ownership, immutable fields and stale session rechecks | tests/test_profile_integration.py, test_listing_edit_integration.py, test_listing_creation_integration.py |
| Buyer only Active/published/eligible-seller detail/contact/photo; literal search/filter privacy | tests/test_browse_integration.py, test_detail_integration.py, test_listing_photo_integration.py, test_search_integration.py, test_filters_integration.py |
| Current DB admin role, stale demotion/revocation, protected private review, explicit publication | tests/test_admin_integration.py, test_admin_users_integration.py, test_admin_listings_integration.py, test_admin_reports_integration.py, test_publication_integration.py |
| Account/listing cascades, postcommit cleanup, traversal/junction confinement and scoped recovery | tests/test_account_deletion_integration.py, test_listing_delete_integration.py, test_avatar_integration.py |
| Frontend truthful 429, no acceptance/success/replay and preserved saved content | frontend/src/RateFeedback.test.jsx, ListingReport.test.jsx, NewListingForm.test.jsx, AvatarControl.test.jsx |

Run the whole backend suite with the documented dedicated disposable PostgreSQL contract and controlled loopback SMTP, then frontend tests/build. Independent QA must verify actual rendered desktop/mobile/keyboard behavior. Use real operator-managed HTTPS and secure cookies in production; preserve certificate verification and STARTTLS-before-auth settings. Never replace missing SMTP configuration with a demo code, disable TLS verification, trust arbitrary proxy headers or publish the upload directory as a static mount.


Current SQLite/memory transaction and storage boundaries are documented in [SQLite setup](sqlite-setup.md) and [memory mode](memory-backend.md). They retain shared auth/CSRF/rate/image rules; SQLite uses BEGIN IMMEDIATE before guards with bounded safe503, while PostgreSQL keeps native row locks. Dated security evidence above is preserved; [iterations](iterations.md) links the current independent292-test result and pending #53 matrix.
