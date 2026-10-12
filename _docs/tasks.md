# Student Marketplace — canonical MVP backlog

The university-only React + FastAPI + PostgreSQL marketplace retains its full MVP scope: verified students buy and sell items, while payments and pickup happen outside the platform. This consolidation groups related backend, frontend, and verification work into cohesive packages; a package may require several focused commits.

**Consolidation target:** 103 original issues become 39 canonical records: five completed historical issues and 34 open implementation packages. The 98 previously open issues become 34 open issues, a 65.3% reduction. The 64 superseded issues close administratively as `not_planned`; their scope moves into surviving issues. Those closures do not mean the work was implemented or passed QA.

Completed #1–#5 history remains unchanged. Issue #6 stays open; its paused uncommitted frontend work is preserved and is not counted as completed. GitHub survivor bodies carry every original acceptance criterion. The summaries below retain source scope and traceability; completing a summary alone does not replace satisfying the full linked criteria.

## Product decisions and delivery rules

Do not invent pending choices: publication policy (automatic/manual/hybrid), exact university domain, final categories, SMTP provider and TLS settings, verification code length/expiry/cooldown/request limits, JWT lifetimes/transport, currency and field-requiredness/input limits, upload formats/size/multipart limits, admin provisioning/permissions, controlled report reasons, and deletion/security/audit retention. Record explicit owner decisions in _docs/plan.md before affected behavior; configurable test values are not product approval.

Work on one canonical package at a time, following PM grooming → engineer implementation → independent QA. Resolve its listed prerequisites before implementation; within a combined package, build shared/backend behavior before connected UI and verify both success and rejection cases. A blocked package does not permit inventing product policy.

Use `uv run python -m pytest` for backend tests; use `npm test` and `npm run build` after frontend testing is established. Integration tests use dedicated databases, fake email delivery, and temporary upload storage rather than shared developer data or live credentials. Every source acceptance criterion remains required before implementation closure with QA PASS.

The standing dependency authorization in AGENTS.md covers minimal dependencies for approved backlog scope; report additions and update manifests and lockfiles. No unattended or endless implementation run is promised.

Publication package #52 is required for every selected policy. Source #97 contributes approval UI only when manual/hybrid review is chosen; automatic publication removes that conditional UI branch, not #52 or its publication-safety verification.

## Completed history

| Issue | Completed work |
| --- | --- |
| [#1](https://github.com/240103098-code/student-marketplace/issues/1) | Create an empty project with a passing test; independently verified and closed |
| [#2](https://github.com/240103098-code/student-marketplace/issues/2) | Document local prerequisites and startup commands; independently verified and closed |
| [#3](https://github.com/240103098-code/student-marketplace/issues/3) | Initialize the FastAPI application; independently verified and closed |
| [#4](https://github.com/240103098-code/student-marketplace/issues/4) | Set up backend test fixtures; independently verified and closed |
| [#5](https://github.com/240103098-code/student-marketplace/issues/5) | Initialize the React application; independently verified and closed |

## Open packages in dependency order

Dependencies below are canonical GitHub issue IDs. Completed prerequisites remain listed for traceability. Detailed scope, acceptance criteria, and exclusions are in each linked survivor.

### [#6](https://github.com/240103098-code/student-marketplace/issues/6) — Set up frontend automated tests

**Prerequisites:** [#5](https://github.com/240103098-code/student-marketplace/issues/5). **Original scope:** [#6](https://github.com/240103098-code/student-marketplace/issues/6).

- **[#6](https://github.com/240103098-code/student-marketplace/issues/6): Set up frontend automated tests.** Configure a React-compatible test runner and testing utilities. Add one simple rendering test and document the command for running frontend tests.

**Goal:** Allow reliable component tests.

The component test must render the actual page, query its visible level-one heading, run once without services, demonstrate a temporary wrong assertion exits nonzero, then restore it. Preserve shell/build and backend regressions.

### [#7](https://github.com/240103098-code/student-marketplace/issues/7) — Add backend environment configuration

**Prerequisites:** [#3](https://github.com/240103098-code/student-marketplace/issues/3). **Original scope:** [#7](https://github.com/240103098-code/student-marketplace/issues/7).

- **[#7](https://github.com/240103098-code/student-marketplace/issues/7): Add backend environment configuration.** Define typed settings for database URL, approved email domain, SMTP credentials, token secrets, frontend origin, and upload directory. Provide a placeholder `.env.example`, ignore real `.env` files, and test missing required settings.

**Goal:** Load runtime settings without committing secrets.

### [#8](https://github.com/240103098-code/student-marketplace/issues/8) — PostgreSQL sessions and Alembic migrations

**Prerequisites:** [#7](https://github.com/240103098-code/student-marketplace/issues/7). **Original scope:** [#8](https://github.com/240103098-code/student-marketplace/issues/8), [#9](https://github.com/240103098-code/student-marketplace/issues/9).

- **[#8](https://github.com/240103098-code/student-marketplace/issues/8): Connect FastAPI to PostgreSQL.** Configure SQLAlchemy's engine, session factory, and FastAPI database dependency for a local PostgreSQL instance. Add an isolated connection or integration test that checks a simple database operation.
- **[#9](https://github.com/240103098-code/student-marketplace/issues/9): Initialize Alembic migrations.** Configure Alembic to use the project's SQLAlchemy metadata and environment settings. Create and test a baseline migration, including a clean upgrade path for a local database.

**Goal:** Establish reusable database sessions. Track database schema changes predictably.

### [#10](https://github.com/240103098-code/student-marketplace/issues/10) — Account, verification-code, and refresh-session data models

**Prerequisites:** [#8](https://github.com/240103098-code/student-marketplace/issues/8). **Original scope:** [#10](https://github.com/240103098-code/student-marketplace/issues/10), [#11](https://github.com/240103098-code/student-marketplace/issues/11), [#12](https://github.com/240103098-code/student-marketplace/issues/12).

- **[#10](https://github.com/240103098-code/student-marketplace/issues/10): Define the user database model.** Add a SQLAlchemy user table with unique university email, password hash, verification state, name, optional avatar path, optional contact fields, role, and suspension state. Include a migration and tests for required fields and uniqueness.
- **[#11](https://github.com/240103098-code/student-marketplace/issues/11): Define verification-code storage.** Model hashed verification codes with their owner, purpose, expiry, failed-attempt count, and used state. Add a migration and tests demonstrating that verification can enforce five incorrect attempts per issued code.
- **[#12](https://github.com/240103098-code/student-marketplace/issues/12): Define refresh-session storage.** Add a database-backed refresh-session or refresh-token record tied to a user, with expiry and revocation state. Include a migration and tests for revoking an existing session and rejecting an expired one.

**Goal:** Store verified student accounts and basic profiles. Persist one-time email verification challenges safely. Support revocable and rotating refresh tokens.

### [#13](https://github.com/240103098-code/student-marketplace/issues/13) — Listing, photo, category, and report data models

**Prerequisites:** [#8](https://github.com/240103098-code/student-marketplace/issues/8), [#10](https://github.com/240103098-code/student-marketplace/issues/10). **Original scope:** [#13](https://github.com/240103098-code/student-marketplace/issues/13), [#14](https://github.com/240103098-code/student-marketplace/issues/14), [#15](https://github.com/240103098-code/student-marketplace/issues/15).

- **[#13](https://github.com/240103098-code/student-marketplace/issues/13): Define categories and listing schema.** Create database structures for listings with owner, title, description, price, predefined category, condition (`new` or `used`), publication date, and active/sold status. Keep the category set configurable until the university's final predefined list is agreed, and test valid versus invalid values.
- **[#14](https://github.com/240103098-code/student-marketplace/issues/14): Define listing-photo records.** Add a listing-photo model containing the owning listing, stored relative file path, and display order. Include a migration and model/service tests showing the first photo can be identified as the cover image.
- **[#15](https://github.com/240103098-code/student-marketplace/issues/15): Define listing-report records.** Create a report table linking reporter and listing, a reason selected from a small controlled set, and an admin-review state. Include a migration and tests for valid reasons and associations.

**Goal:** Store items with a fixed category and New/Used condition. Associate up to five ordered photos with each listing. Store reasons users submit for inappropriate listings.

### [#16](https://github.com/240103098-code/student-marketplace/issues/16) — Agree on remaining MVP configuration values

**Prerequisites:** None. **Original scope:** [#16](https://github.com/240103098-code/student-marketplace/issues/16).

- **[#16](https://github.com/240103098-code/student-marketplace/issues/16): Agree on remaining MVP configuration values.** Confirm the approved university email domain, final category list, verification-code duration and resend rules, photo file types/limits, and whether listings require approval. Record the chosen values in the requirements file; do not silently treat earlier recommendations as decisions.

**Goal:** Record unresolved choices before behavior depends on them.

Completion requires explicit owner decisions in `_docs/plan.md` with exact configured values and affected-issue links. Unanswered choices remain visibly unresolved.

### [#17](https://github.com/240103098-code/student-marketplace/issues/17) — University registration validation and password hashing

**Prerequisites:** [#7](https://github.com/240103098-code/student-marketplace/issues/7), [#10](https://github.com/240103098-code/student-marketplace/issues/10), [#16](https://github.com/240103098-code/student-marketplace/issues/16). **Original scope:** [#17](https://github.com/240103098-code/student-marketplace/issues/17), [#18](https://github.com/240103098-code/student-marketplace/issues/18), [#19](https://github.com/240103098-code/student-marketplace/issues/19).

- **[#17](https://github.com/240103098-code/student-marketplace/issues/17): Validate university email addresses.** Implement server-side email normalization and exact-domain matching against the one configured university domain. Test allowed addresses, addresses from other domains, and lookalike suffixes.
- **[#18](https://github.com/240103098-code/student-marketplace/issues/18): Implement password hashing utilities.** Add a maintained password-hashing algorithm/library and utilities for hashing and comparing passwords without storing plaintext values. Test successful verification, mismatched passwords, and distinct salts.
- **[#19](https://github.com/240103098-code/student-marketplace/issues/19): Implement account registration API.** Add an endpoint that validates the approved email domain, hashes the password, and creates an unverified user account. Return safe errors for invalid input or duplicate addresses and test the endpoint without sending an email yet.

**Goal:** Reject registration from unapproved email domains. Store and verify passwords securely. Let students start registration with university email and password.

### [#20](https://github.com/240103098-code/student-marketplace/issues/20) — SMTP delivery and registration verification lifecycle

**Prerequisites:** [#7](https://github.com/240103098-code/student-marketplace/issues/7), [#10](https://github.com/240103098-code/student-marketplace/issues/10), [#17](https://github.com/240103098-code/student-marketplace/issues/17). **Original scope:** [#20](https://github.com/240103098-code/student-marketplace/issues/20), [#21](https://github.com/240103098-code/student-marketplace/issues/21), [#22](https://github.com/240103098-code/student-marketplace/issues/22), [#23](https://github.com/240103098-code/student-marketplace/issues/23).

- **[#20](https://github.com/240103098-code/student-marketplace/issues/20): Build the SMTP email sender.** Add a small email service that sends a message using environment-provided server credentials, TLS configuration, and sender address. Mock delivery in automated tests and document how to configure a real SMTP account locally.
- **[#21](https://github.com/240103098-code/student-marketplace/issues/21): Issue registration verification codes.** Generate a secure code, store only its hash and metadata, and send the code using the SMTP service. Use the agreed expiry setting and test that the emailed code corresponds to the stored challenge without persisting plaintext.
- **[#22](https://github.com/240103098-code/student-marketplace/issues/22): Verify student email addresses.** Add an API that checks code validity, expiry, and failed-attempt count, then marks the account verified on success. After five incorrect attempts, invalidate that code and require a newly issued code; test boundary cases.
- **[#23](https://github.com/240103098-code/student-marketplace/issues/23): Resend a registration verification code.** Add an endpoint that issues a replacement code for an unverified account, invalidating the prior code. Apply the agreed resend cooldown and request limits, and test that an old code no longer works.

**Goal:** Send real transactional emails through configured SMTP settings. Email a one-time code when a student registers. Activate accounts only after a correct verification code. Recover when a student loses or does not receive a code.

### [#24](https://github.com/240103098-code/student-marketplace/issues/24) — Create JWT access tokens

**Prerequisites:** [#7](https://github.com/240103098-code/student-marketplace/issues/7). **Original scope:** [#24](https://github.com/240103098-code/student-marketplace/issues/24).

- **[#24](https://github.com/240103098-code/student-marketplace/issues/24): Create JWT access tokens.** Implement signed JWT issuance and validation, including user identity and token expiry. Add tests for valid, expired, malformed, and incorrectly signed tokens.

**Goal:** Authenticate requests using short-lived access tokens.

### [#25](https://github.com/240103098-code/student-marketplace/issues/25) — Login and verified-user authorization

**Prerequisites:** [#17](https://github.com/240103098-code/student-marketplace/issues/17), [#20](https://github.com/240103098-code/student-marketplace/issues/20), [#24](https://github.com/240103098-code/student-marketplace/issues/24). **Original scope:** [#25](https://github.com/240103098-code/student-marketplace/issues/25), [#28](https://github.com/240103098-code/student-marketplace/issues/28).

- **[#25](https://github.com/240103098-code/student-marketplace/issues/25): Implement login API.** Add an endpoint that validates credentials, requires a verified and unsuspended account, and returns or sets the established session credentials. Test valid login and rejection of incorrect passwords, unverified users, and suspended users.
- **[#28](https://github.com/240103098-code/student-marketplace/issues/28): Protect verified-user endpoints.** Add reusable FastAPI dependencies that require an authenticated, verified, non-suspended user for listings, profiles, searches, and reports. Test anonymous, unverified, and suspended requests against at least one protected endpoint.

**Goal:** Let verified students sign in with email and password. Keep all marketplace data private to verified students.

### [#26](https://github.com/240103098-code/student-marketplace/issues/26) — Refresh rotation, logout, and session revocation

**Prerequisites:** [#10](https://github.com/240103098-code/student-marketplace/issues/10), [#24](https://github.com/240103098-code/student-marketplace/issues/24), [#25](https://github.com/240103098-code/student-marketplace/issues/25). **Original scope:** [#26](https://github.com/240103098-code/student-marketplace/issues/26), [#27](https://github.com/240103098-code/student-marketplace/issues/27).

- **[#26](https://github.com/240103098-code/student-marketplace/issues/26): Implement refresh-token rotation API.** Build an endpoint that accepts a valid stored refresh token, revokes or rotates it, and issues a new access/refresh token pair. Test replay rejection, expired tokens, and revoked sessions.
- **[#27](https://github.com/240103098-code/student-marketplace/issues/27): Implement logout and session revocation.** Add a logout endpoint that invalidates the active refresh session and clears any refresh-token cookie used by the app. Test that logout prevents future refreshes from that session.

**Goal:** Renew sessions without reusing old refresh tokens. Let users explicitly end a session.

### [#29](https://github.com/240103098-code/student-marketplace/issues/29) — Configure browser session security

**Prerequisites:** [#26](https://github.com/240103098-code/student-marketplace/issues/26). **Original scope:** [#29](https://github.com/240103098-code/student-marketplace/issues/29).

- **[#29](https://github.com/240103098-code/student-marketplace/issues/29): Configure browser session security.** Define the token transport and storage strategy, including refresh-cookie attributes if cookies are chosen, CORS origin restrictions, and CSRF safeguards where necessary. Test browser-facing auth behavior so credentials are not exposed to unrelated origins.

**Goal:** Use access and refresh tokens safely from React.

### [#30](https://github.com/240103098-code/student-marketplace/issues/30) — Current-user profile read and restricted editing APIs

**Prerequisites:** [#25](https://github.com/240103098-code/student-marketplace/issues/25). **Original scope:** [#30](https://github.com/240103098-code/student-marketplace/issues/30), [#31](https://github.com/240103098-code/student-marketplace/issues/31).

- **[#30](https://github.com/240103098-code/student-marketplace/issues/30): Add current-user profile API.** Create a protected `GET /users/me` endpoint exposing name, verified email, optional profile photo, and contact details without password hashes or tokens. Add response-schema tests verifying private account fields are omitted.
- **[#31](https://github.com/240103098-code/student-marketplace/issues/31): Add profile editing API.** Create a protected profile update endpoint with validated fields for name and seller contact details. Reject attempts to change the verified university email, role, or verification state, and test both allowed and forbidden updates.

**Goal:** Return a student's own basic profile. Allow changes to name, photo path, and contact methods only.

### [#32](https://github.com/240103098-code/student-marketplace/issues/32) — Safe image validation, storage, and avatar uploads

**Prerequisites:** [#16](https://github.com/240103098-code/student-marketplace/issues/16), [#30](https://github.com/240103098-code/student-marketplace/issues/30). **Original scope:** [#32](https://github.com/240103098-code/student-marketplace/issues/32), [#38](https://github.com/240103098-code/student-marketplace/issues/38), [#39](https://github.com/240103098-code/student-marketplace/issues/39).

- **[#32](https://github.com/240103098-code/student-marketplace/issues/32): Add a profile-photo upload endpoint.** Validate image type and size using agreed upload limits, store the file under the backend uploads directory, and persist its relative path. Test unauthorized uploads, invalid files, and replacement handling.
- **[#38](https://github.com/240103098-code/student-marketplace/issues/38): Implement listing image-file validation.** Validate actual image content, approved formats, file size, and limits on multipart requests before writing to `uploads/`. Add tests for non-images, oversized uploads, path traversal attempts, and allowed formats.
- **[#39](https://github.com/240103098-code/student-marketplace/issues/39): Implement listing-photo storage service.** Build helpers to write images under the backend `uploads/` directory with generated safe filenames and ordered metadata. Add tests for storing, retrieving the generated path, and deleting files when a listing is removed.

**Goal:** Let students add or replace an optional avatar. Accept safe uploads without allowing arbitrary files. Save and clean up local listing images consistently.

### [#62](https://github.com/240103098-code/student-marketplace/issues/62) — Set up React routes and shared page layout

**Prerequisites:** [#5](https://github.com/240103098-code/student-marketplace/issues/5), [#6](https://github.com/240103098-code/student-marketplace/issues/6). **Original scope:** [#62](https://github.com/240103098-code/student-marketplace/issues/62).

- **[#62](https://github.com/240103098-code/student-marketplace/issues/62): Set up React routes and shared page layout.** Add a shared header and route placeholders for sign-in, registration, verification, home, listing details, new listing, My Listings, profile, and admin. Add a simple navigation test without implementing those pages' business logic.

**Goal:** Provide navigation for the student marketplace pages.

### [#63](https://github.com/240103098-code/student-marketplace/issues/63) — Frontend API client, route guards, and logout

**Prerequisites:** [#26](https://github.com/240103098-code/student-marketplace/issues/26), [#29](https://github.com/240103098-code/student-marketplace/issues/29), [#62](https://github.com/240103098-code/student-marketplace/issues/62). **Original scope:** [#63](https://github.com/240103098-code/student-marketplace/issues/63), [#67](https://github.com/240103098-code/student-marketplace/issues/67), [#68](https://github.com/240103098-code/student-marketplace/issues/68).

- **[#63](https://github.com/240103098-code/student-marketplace/issues/63): Add frontend API client and auth handling.** Create a centralized HTTP client that uses the backend base URL, attaches credentials or access tokens appropriately, and handles unauthorized responses. Test the request configuration and one simulated expired-session response.
- **[#67](https://github.com/240103098-code/student-marketplace/issues/67): Protect frontend marketplace routes.** Add a reusable auth guard for home, listings, My Listings, profile, and admin routes, using backend verification as the final authority. Test redirects for unauthenticated users and the admin-route guard for ordinary students.
- **[#68](https://github.com/240103098-code/student-marketplace/issues/68): Add logout UI.** Connect a visible logout action to the backend revocation endpoint and clear client-side session state. Test that signing out returns the user to the login screen and prevents reopening protected pages without signing in.

**Goal:** Connect React to FastAPI with consistent session behavior. Prevent anonymous or unverified users from opening private app pages. Let users sign out from the application header or profile.

### [#66](https://github.com/240103098-code/student-marketplace/issues/66) — Build login form

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#25](https://github.com/240103098-code/student-marketplace/issues/25), [#62](https://github.com/240103098-code/student-marketplace/issues/62), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#66](https://github.com/240103098-code/student-marketplace/issues/66).

- **[#66](https://github.com/240103098-code/student-marketplace/issues/66): Build login form.** Build an email/password form connected to the login endpoint and route successful users to the marketplace. Show clear errors for bad credentials and unverified accounts without leaking sensitive technical details.

**Goal:** Let verified students sign in through the browser.

### [#33](https://github.com/240103098-code/student-marketplace/issues/33) — Password change and email recovery APIs and screens

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#17](https://github.com/240103098-code/student-marketplace/issues/17), [#20](https://github.com/240103098-code/student-marketplace/issues/20), [#25](https://github.com/240103098-code/student-marketplace/issues/25), [#62](https://github.com/240103098-code/student-marketplace/issues/62), [#63](https://github.com/240103098-code/student-marketplace/issues/63), [#66](https://github.com/240103098-code/student-marketplace/issues/66). **Original scope:** [#33](https://github.com/240103098-code/student-marketplace/issues/33), [#34](https://github.com/240103098-code/student-marketplace/issues/34), [#35](https://github.com/240103098-code/student-marketplace/issues/35), [#69](https://github.com/240103098-code/student-marketplace/issues/69), [#70](https://github.com/240103098-code/student-marketplace/issues/70), [#71](https://github.com/240103098-code/student-marketplace/issues/71).

- **[#33](https://github.com/240103098-code/student-marketplace/issues/33): Add authenticated password change.** Build an endpoint requiring the current password and a valid new password, then replace the stored hash. Test a correct change and rejection when the existing password is wrong.
- **[#34](https://github.com/240103098-code/student-marketplace/issues/34): Request a forgotten-password reset code.** Add a reset-request endpoint that creates a purpose-specific, expiring code and sends it through SMTP. Use a non-enumerating response for unknown addresses and test request limits and code issuance.
- **[#35](https://github.com/240103098-code/student-marketplace/issues/35): Reset a forgotten password.** Validate the reset code, enforce its attempt and expiry rules, replace the account's password hash, and invalidate the used code. Revoke existing refresh sessions after a successful reset and test that stale sessions cannot refresh.
- **[#69](https://github.com/240103098-code/student-marketplace/issues/69): Build password-change form.** Add a profile/settings form for current password, new password, and confirmation, then call the password-change endpoint. Display validation and success/error states without echoing entered passwords.
- **[#70](https://github.com/240103098-code/student-marketplace/issues/70): Build forgotten-password request screen.** Provide a university-email input that calls the reset-request endpoint and explains the next step. Display the same generic success message for known and unknown addresses.
- **[#71](https://github.com/240103098-code/student-marketplace/issues/71): Build password-reset confirmation screen.** Create inputs for verification code, new password, and confirmation, then call the reset API. Handle expired/invalid codes and show a route back to login after success.

**Goal:** Let logged-in students change passwords. Send password recovery codes to registered university email addresses. Let users set a new password after email-code verification. Let signed-in students update their password. Let students request a reset code by email. Let students set a new password with a reset code.

### [#37](https://github.com/240103098-code/student-marketplace/issues/37) — Listing validation, creation API, form, and photo uploader

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#13](https://github.com/240103098-code/student-marketplace/issues/13), [#16](https://github.com/240103098-code/student-marketplace/issues/16), [#25](https://github.com/240103098-code/student-marketplace/issues/25), [#32](https://github.com/240103098-code/student-marketplace/issues/32), [#62](https://github.com/240103098-code/student-marketplace/issues/62), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#37](https://github.com/240103098-code/student-marketplace/issues/37), [#40](https://github.com/240103098-code/student-marketplace/issues/40), [#81](https://github.com/240103098-code/student-marketplace/issues/81), [#82](https://github.com/240103098-code/student-marketplace/issues/82).

- **[#37](https://github.com/240103098-code/student-marketplace/issues/37): Validate listing input fields.** Create input validation for title, description, nonnegative price in the project's agreed currency, predefined category, and `new`/`used` condition. Keep any not-yet-decided length or price limits configurable, and add valid/invalid schema tests.
- **[#40](https://github.com/240103098-code/student-marketplace/issues/40): Create a listing API.** Add a protected endpoint that saves a listing owned by the authenticated user and attaches zero to five validated images, with the first image as cover. Enforce the publication policy selected in Task 16 and test ownership, field validation, and the six-photo rejection case.
- **[#81](https://github.com/240103098-code/student-marketplace/issues/81): Build new-listing form.** Add inputs for title, description, price, predefined category, and New/Used condition, connected to the create-listing API. Show validation errors and a success state consistent with the selected publication-approval policy.
- **[#82](https://github.com/240103098-code/student-marketplace/issues/82): Build listing photo uploader.** Add an image picker with previews, removal before submission, and a clear five-photo limit. Submit the photos using the backend upload contract and display errors for unsupported or oversized files.

**Goal:** Enforce consistent listing data before saving. Let verified students publish a listing with up to five photos. Let verified students submit an item for sale. Attach up to five ordered images while creating a listing.

### [#48](https://github.com/240103098-code/student-marketplace/issues/48) — Seller listing management APIs and My Listings actions

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#32](https://github.com/240103098-code/student-marketplace/issues/32), [#37](https://github.com/240103098-code/student-marketplace/issues/37), [#62](https://github.com/240103098-code/student-marketplace/issues/62), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#48](https://github.com/240103098-code/student-marketplace/issues/48), [#49](https://github.com/240103098-code/student-marketplace/issues/49), [#50](https://github.com/240103098-code/student-marketplace/issues/50), [#51](https://github.com/240103098-code/student-marketplace/issues/51), [#83](https://github.com/240103098-code/student-marketplace/issues/83), [#84](https://github.com/240103098-code/student-marketplace/issues/84), [#85](https://github.com/240103098-code/student-marketplace/issues/85), [#86](https://github.com/240103098-code/student-marketplace/issues/86).

- **[#48](https://github.com/240103098-code/student-marketplace/issues/48): List the seller's own listings API.** Add a protected endpoint returning only listings owned by the signed-in user, including their active or sold status. Test that another student's listings are never included and that sold listings remain in the owner's results.
- **[#49](https://github.com/240103098-code/student-marketplace/issues/49): Edit permitted listing fields API.** Add an owner-only update endpoint accepting exactly price and description, using the same validation rules as listing creation. Reject attempted changes to title, photos, category, condition, ownership, or status through this endpoint and test those restrictions.
- **[#50](https://github.com/240103098-code/student-marketplace/issues/50): Mark a listing as sold API.** Add an owner-only action that transitions an active listing to sold. Test that the item disappears from browse/search results but remains visible in My Listings.
- **[#51](https://github.com/240103098-code/student-marketplace/issues/51): Delete an owned listing API.** Add an owner-only deletion endpoint that removes its database records and locally stored photos safely. Test authorization, nonexistent IDs, and successful image cleanup.
- **[#83](https://github.com/240103098-code/student-marketplace/issues/83): Build My Listings dashboard.** Create a protected page that loads only the signed-in user's listings and groups or filters them by Active and Sold. Include clear empty states and actions for editing, marking sold, and deleting each applicable item.
- **[#84](https://github.com/240103098-code/student-marketplace/issues/84): Build restricted listing-edit form.** Provide a form populated from an owned listing with just those two editable fields. Do not include controls for editing title, photos, category, or condition, and test that submitted data contains only permitted properties.
- **[#85](https://github.com/240103098-code/student-marketplace/issues/85): Add Mark as Sold interaction.** Connect a confirmation action to the mark-sold API, then update the listing's status in the dashboard. Ensure sold items no longer offer a misleading action to publish or hide them.
- **[#86](https://github.com/240103098-code/student-marketplace/issues/86): Add Delete Listing interaction.** Add a confirmation dialog and connect it to the owner-only listing delete API. Update the dashboard after success and handle failed or unauthorized deletions visibly.

**Goal:** Show active and sold items in My Listings. Let owners change price and description after publishing. Remove sold items from marketplace search but keep seller history. Allow sellers to permanently remove a listing. Show a seller's active and sold items separately. Let owners change only price and description. Let sellers close a listing from My Listings. Let sellers remove a listing deliberately.

### [#87](https://github.com/240103098-code/student-marketplace/issues/87) — Profile details and editing screens

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#30](https://github.com/240103098-code/student-marketplace/issues/30), [#32](https://github.com/240103098-code/student-marketplace/issues/32), [#62](https://github.com/240103098-code/student-marketplace/issues/62), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#87](https://github.com/240103098-code/student-marketplace/issues/87), [#88](https://github.com/240103098-code/student-marketplace/issues/88).

- **[#87](https://github.com/240103098-code/student-marketplace/issues/87): Build profile details page.** Create a protected profile screen showing name, fixed university email, optional avatar, and contact methods. Make it clear that the verified email cannot be edited.
- **[#88](https://github.com/240103098-code/student-marketplace/issues/88): Build profile-edit form.** Connect editable profile fields and optional avatar upload to the relevant backend endpoints. Validate contact details and present save success or failure without exposing administrative account fields.

**Goal:** Show a student's verified identity and contact information. Let students update name, avatar, and contact details.

### [#36](https://github.com/240103098-code/student-marketplace/issues/36) — Permanent account deletion API and confirmation screen

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#25](https://github.com/240103098-code/student-marketplace/issues/25), [#48](https://github.com/240103098-code/student-marketplace/issues/48), [#63](https://github.com/240103098-code/student-marketplace/issues/63), [#87](https://github.com/240103098-code/student-marketplace/issues/87). **Original scope:** [#36](https://github.com/240103098-code/student-marketplace/issues/36), [#89](https://github.com/240103098-code/student-marketplace/issues/89).

- **[#36](https://github.com/240103098-code/student-marketplace/issues/36): Permanently delete a user account.** Add a protected endpoint that requires an appropriate confirmation and deletes or anonymizes the user's profile, listings, associated photos, and contact information. Document and test any narrowly scoped security/legal retention exceptions instead of inventing a general retention policy.
- **[#89](https://github.com/240103098-code/student-marketplace/issues/89): Add account deletion UI.** Provide a clearly worded confirmation step connected to the delete-account API, explaining that listings and profile information are removed. Clear the local session and return the user to an unauthenticated screen after deletion.

**Goal:** Support self-service deletion of an account and its data. Let students permanently remove their own account.

### [#41](https://github.com/240103098-code/student-marketplace/issues/41) — Marketplace browsing, search, filters, cards, and homepage

**Prerequisites:** [#5](https://github.com/240103098-code/student-marketplace/issues/5), [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#37](https://github.com/240103098-code/student-marketplace/issues/37), [#62](https://github.com/240103098-code/student-marketplace/issues/62), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#41](https://github.com/240103098-code/student-marketplace/issues/41), [#42](https://github.com/240103098-code/student-marketplace/issues/42), [#43](https://github.com/240103098-code/student-marketplace/issues/43), [#44](https://github.com/240103098-code/student-marketplace/issues/44), [#45](https://github.com/240103098-code/student-marketplace/issues/45), [#72](https://github.com/240103098-code/student-marketplace/issues/72), [#73](https://github.com/240103098-code/student-marketplace/issues/73), [#74](https://github.com/240103098-code/student-marketplace/issues/74), [#75](https://github.com/240103098-code/student-marketplace/issues/75), [#76](https://github.com/240103098-code/student-marketplace/issues/76), [#77](https://github.com/240103098-code/student-marketplace/issues/77).

- **[#41](https://github.com/240103098-code/student-marketplace/issues/41): List active marketplace items API.** Add a paginated endpoint returning listing cards with title, price, cover image, category, condition, and publication date ordered newest first. Exclude sold, deleted, and any not-yet-approved listings under the selected publication policy, and test ordering and visibility.
- **[#42](https://github.com/240103098-code/student-marketplace/issues/42): Search listings by keyword API.** Extend the listing-browse endpoint with a case-insensitive keyword query matching suitable title and description fields. Keep newest-first ordering and test empty queries, matching terms, and hidden/sold exclusions.
- **[#43](https://github.com/240103098-code/student-marketplace/issues/43): Filter listings by category API.** Add a category query parameter to the protected listing-browse endpoint and validate it against the configured categories. Test results inside and outside the category while preserving newest-first ordering.
- **[#44](https://github.com/240103098-code/student-marketplace/issues/44): Filter listings by price range API.** Add minimum and maximum price parameters to the listing-browse endpoint, including validation that minimum does not exceed maximum. Test inclusive boundaries and combination with keyword searches.
- **[#45](https://github.com/240103098-code/student-marketplace/issues/45): Filter listings by condition API.** Add an optional `new`/`used` condition query parameter to the protected listing-browse endpoint. Test that it composes with price, category, and keyword filters without altering newest-first sort order.
- **[#72](https://github.com/240103098-code/student-marketplace/issues/72): Build marketplace home page.** Implement a modern minimal React page with a white/neutral design, category navigation, and a responsive card grid showing photo and price. Load the newest visible listings from the protected browse API and include loading, empty, and error states.
- **[#73](https://github.com/240103098-code/student-marketplace/issues/73): Build reusable listing card component.** Create a card component for cover photo, title, price, condition, and optional status on owner pages. Test behavior when a listing has no photo and when titles are long.
- **[#74](https://github.com/240103098-code/student-marketplace/issues/74): Connect keyword search in React.** Wire a search field to the backend keyword query and render matching results on the browse page. Include a clear-search action, loading feedback, and a no-results message.
- **[#75](https://github.com/240103098-code/student-marketplace/issues/75): Build category filter UI.** Render the configured category options and pass the selection to the browse API. Keep the selected category visible and test that clearing it restores the unfiltered list.
- **[#76](https://github.com/240103098-code/student-marketplace/issues/76): Build price-range filter UI.** Create minimum and maximum price inputs and send valid ranges to the browse API. Show validation when minimum exceeds maximum and keep results ordered newest first.
- **[#77](https://github.com/240103098-code/student-marketplace/issues/77): Build New/Used condition filter UI.** Add New, Used, and All filter choices to the browse interface. Connect the selected value to the API and test its interaction with active category and price filters.

**Goal:** Show verified users only publicly visible active listings. Find active items from text entered by a buyer. Restrict results to one predefined category. Return items within the requested price bounds. Find only New or Used items. Display the search bar, categories, and newest listing cards. Present consistent item previews across marketplace pages. Let students find listings by typing search terms. Let students browse one predefined category. Let students restrict results to affordable listings. Let students filter items by condition.

### [#46](https://github.com/240103098-code/student-marketplace/issues/46) — Listing details, photo gallery, and safe seller contact

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#30](https://github.com/240103098-code/student-marketplace/issues/30), [#41](https://github.com/240103098-code/student-marketplace/issues/41), [#62](https://github.com/240103098-code/student-marketplace/issues/62), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#46](https://github.com/240103098-code/student-marketplace/issues/46), [#47](https://github.com/240103098-code/student-marketplace/issues/47), [#78](https://github.com/240103098-code/student-marketplace/issues/78), [#79](https://github.com/240103098-code/student-marketplace/issues/79), [#80](https://github.com/240103098-code/student-marketplace/issues/80).

- **[#46](https://github.com/240103098-code/student-marketplace/issues/46): Retrieve listing details API.** Add a protected endpoint returning the description, price, category, condition, ordered photos, seller name, and available seller contact methods for an active listing. Reject access to listings that are sold, removed, or unapproved except where the owner/admin is explicitly authorized.
- **[#47](https://github.com/240103098-code/student-marketplace/issues/47): Generate safe external seller-contact links.** Validate stored contact identifiers and generate allowed Telegram or WhatsApp links without permitting arbitrary script or unsafe URL schemes. Test supported contacts, missing contacts, and invalid identifiers.
- **[#78](https://github.com/240103098-code/student-marketplace/issues/78): Build listing details page.** Display title, description, price, category, condition, seller name, and ordered photos from the listing-details API. Handle inaccessible or sold listings gracefully rather than exposing seller information through an error state.
- **[#79](https://github.com/240103098-code/student-marketplace/issues/79): Build listing photo gallery.** Create a reusable gallery with the first image as the main photo and controls to switch between images. Include an accessible single-image/empty-image state and test gallery navigation.
- **[#80](https://github.com/240103098-code/student-marketplace/issues/80): Build seller contact panel.** Display available seller contact details and a Contact Seller button that opens a validated Telegram or WhatsApp URL when one exists. Do not add in-app chat, payment, or purchase workflows.

**Goal:** Show full information for one visible listing. Support opening the seller's preferred messaging app. Show one active listing's complete information. Let buyers view up to five images of an item. Help buyers contact a seller outside the platform.

### [#54](https://github.com/240103098-code/student-marketplace/issues/54) — Admin authorization, controlled provisioning, and navigation

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#25](https://github.com/240103098-code/student-marketplace/issues/25), [#62](https://github.com/240103098-code/student-marketplace/issues/62), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#54](https://github.com/240103098-code/student-marketplace/issues/54), [#55](https://github.com/240103098-code/student-marketplace/issues/55), [#91](https://github.com/240103098-code/student-marketplace/issues/91).

- **[#54](https://github.com/240103098-code/student-marketplace/issues/54): Add an administrator authorization guard.** Create a reusable backend dependency that checks a signed-in verified user's admin role and active account state. Test that ordinary users cannot access admin routes even if they change client-side requests.
- **[#55](https://github.com/240103098-code/student-marketplace/issues/55): Define how the first admin is created.** Document and implement a controlled local admin-provisioning method that does not allow public self-registration as an admin. Test that registration cannot set the admin role and that the bootstrap procedure is deliberate.
- **[#91](https://github.com/240103098-code/student-marketplace/issues/91): Build admin navigation and access screen.** Create an admin layout with links to users, listings, and reports. Hide it from ordinary users for convenience while relying on backend admin checks for actual security.

**Goal:** Restrict management endpoints to admin users. Safely bootstrap administrator access in local development. Give authorized admins a separate moderation workspace.

### [#52](https://github.com/240103098-code/student-marketplace/issues/52) — Chosen publication policy and conditional admin approval UI

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#16](https://github.com/240103098-code/student-marketplace/issues/16), [#37](https://github.com/240103098-code/student-marketplace/issues/37), [#54](https://github.com/240103098-code/student-marketplace/issues/54), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#52](https://github.com/240103098-code/student-marketplace/issues/52), [#97](https://github.com/240103098-code/student-marketplace/issues/97).

- **[#52](https://github.com/240103098-code/student-marketplace/issues/52): Decide and implement listing publication approval.** After the product owner selects a policy, implement the smallest additional listing state and admin action needed to enforce it. Test that a listing becomes browse-visible at the right point and that unapproved items never leak into public results.
- **[#97](https://github.com/240103098-code/student-marketplace/issues/97): Build approval UI if required by the chosen policy.** If the owner selects manual or hybrid listing review, add a small admin queue and the corresponding approve/reject actions. If automatic publishing is selected, mark this task unnecessary rather than inventing an approval feature.

**Goal:** Apply the chosen automatic, manual, or hybrid review workflow. Support manual approval or hybrid review only if selected.

Verify browse visibility under the chosen automatic/manual/hybrid policy and rejection of unapproved content. Only the absorbed approval-UI branch can become unnecessary.

### [#53](https://github.com/240103098-code/student-marketplace/issues/53) — Listing reporting API and student interaction

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#13](https://github.com/240103098-code/student-marketplace/issues/13), [#25](https://github.com/240103098-code/student-marketplace/issues/25), [#46](https://github.com/240103098-code/student-marketplace/issues/46), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#53](https://github.com/240103098-code/student-marketplace/issues/53), [#90](https://github.com/240103098-code/student-marketplace/issues/90).

- **[#53](https://github.com/240103098-code/student-marketplace/issues/53): Submit a listing report API.** Add a protected endpoint that creates a report for a visible listing with a controlled reason such as spam, prohibited item, or misleading information. Validate the reason and listing visibility, and test malformed or unauthorized reports.
- **[#90](https://github.com/240103098-code/student-marketplace/issues/90): Build listing-report interaction.** Add a Report action to visible listing details with a fixed reason selector and a submit button. Connect it to the report API and show a simple confirmation without advanced reporter-side status tracking.

**Goal:** Let verified users flag an active listing using a reason. Let students report an inappropriate listing.

### [#56](https://github.com/240103098-code/student-marketplace/issues/56) — Admin user listing and suspension APIs and controls

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#10](https://github.com/240103098-code/student-marketplace/issues/10), [#25](https://github.com/240103098-code/student-marketplace/issues/25), [#54](https://github.com/240103098-code/student-marketplace/issues/54), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#56](https://github.com/240103098-code/student-marketplace/issues/56), [#61](https://github.com/240103098-code/student-marketplace/issues/61), [#92](https://github.com/240103098-code/student-marketplace/issues/92), [#93](https://github.com/240103098-code/student-marketplace/issues/93).

- **[#56](https://github.com/240103098-code/student-marketplace/issues/56): List users in the admin API.** Create a protected admin endpoint returning paginated users with email, name, verified state, and suspension state. Exclude password hashes, reset codes, refresh tokens, and other secrets from responses and tests.
- **[#61](https://github.com/240103098-code/student-marketplace/issues/61): Suspend and unsuspend accounts as admin.** Create admin actions to update a user's suspension state and test both suspension and reversal. Ensure suspended users cannot log in or use protected marketplace APIs, including when previously issued tokens remain unexpired.
- **[#92](https://github.com/240103098-code/student-marketplace/issues/92): Build admin user list.** Load the admin users endpoint into a simple table with email, name, verification, and suspension columns. Include pagination or another lightweight way to navigate large result sets.
- **[#93](https://github.com/240103098-code/student-marketplace/issues/93): Add admin suspend/unsuspend controls.** Connect confirmation actions in the admin users table to suspend and unsuspend endpoints. Refresh user state after changes and display errors without assuming the operation succeeded.

**Goal:** Give admins a read-only overview of registered accounts. Block accounts that violate marketplace rules. Let admins find accounts and view suspension status. Let admins moderate user access from the UI.

### [#57](https://github.com/240103098-code/student-marketplace/issues/57) — Admin listing overview and removal APIs and controls

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#54](https://github.com/240103098-code/student-marketplace/issues/54), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#57](https://github.com/240103098-code/student-marketplace/issues/57), [#60](https://github.com/240103098-code/student-marketplace/issues/60), [#94](https://github.com/240103098-code/student-marketplace/issues/94), [#95](https://github.com/240103098-code/student-marketplace/issues/95).

- **[#57](https://github.com/240103098-code/student-marketplace/issues/57): List listings in the admin API.** Add an admin endpoint with listing owner, status, publication date, and basic details. Ensure it can review items not visible in normal marketplace search, subject to the chosen publication policy.
- **[#60](https://github.com/240103098-code/student-marketplace/issues/60): Remove an inappropriate listing as admin.** Add an admin endpoint for removing a listing, separate from seller-initiated deletion, while preserving any minimum record necessary to understand report actions. Test that removed items disappear from browse results and that owners cannot restore them through edit requests.
- **[#94](https://github.com/240103098-code/student-marketplace/issues/94): Build admin listing list.** Load the admin listing endpoint into a table showing title, owner, status, and publication date. Provide a way to open details and handle listings unavailable to ordinary students.
- **[#95](https://github.com/240103098-code/student-marketplace/issues/95): Add admin remove-listing control.** Add a confirmation action on admin listing rows that calls the moderation removal API. Refresh the list and verify the removed listing is not available through normal search.

**Goal:** Let admins inspect active, sold, and removed-status listings as appropriate. Let moderators take reported listings out of public view. Let admins inspect listed items and their publication states. Let admins remove inappropriate content from the UI.

### [#58](https://github.com/240103098-code/student-marketplace/issues/58) — Admin report queue and review APIs and UI

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#13](https://github.com/240103098-code/student-marketplace/issues/13), [#54](https://github.com/240103098-code/student-marketplace/issues/54), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#58](https://github.com/240103098-code/student-marketplace/issues/58), [#59](https://github.com/240103098-code/student-marketplace/issues/59), [#96](https://github.com/240103098-code/student-marketplace/issues/96).

- **[#58](https://github.com/240103098-code/student-marketplace/issues/58): Review listing reports in the admin API.** Add an admin endpoint listing reports with listing reference, reporter reference, reason, creation date, and review status. Test role protection and filtering by pending versus reviewed reports.
- **[#59](https://github.com/240103098-code/student-marketplace/issues/59): Mark a report reviewed.** Add an admin action to update a report's review state after inspection. Test that only admins may use it and that it does not automatically remove a listing.
- **[#96](https://github.com/240103098-code/student-marketplace/issues/96): Build admin report queue.** Create a report list showing reason, item reference, reporter reference, time, and pending/reviewed state. Connect a Mark Reviewed control to the admin API and let the admin open the reported listing for investigation.

**Goal:** Show admins submitted reports and their review state. Prevent admins from repeatedly processing the same report. Let admins review reasons for listing reports.

### [#64](https://github.com/240103098-code/student-marketplace/issues/64) — Registration and verification screens

**Prerequisites:** [#6](https://github.com/240103098-code/student-marketplace/issues/6), [#17](https://github.com/240103098-code/student-marketplace/issues/17), [#20](https://github.com/240103098-code/student-marketplace/issues/20), [#62](https://github.com/240103098-code/student-marketplace/issues/62), [#63](https://github.com/240103098-code/student-marketplace/issues/63). **Original scope:** [#64](https://github.com/240103098-code/student-marketplace/issues/64), [#65](https://github.com/240103098-code/student-marketplace/issues/65).

- **[#64](https://github.com/240103098-code/student-marketplace/issues/64): Build registration form.** Create a responsive registration form that validates basic input, calls the registration API, and navigates to email verification on success. Show understandable error messages for invalid domains and duplicate registrations.
- **[#65](https://github.com/240103098-code/student-marketplace/issues/65): Build email verification screen.** Create a code-entry form and resend-code control connected to the verification APIs. Display incorrect-attempt feedback and make the five-attempt limit and code replacement understandable.

**Goal:** Let students enter university email and password in React. Let newly registered students activate their accounts.

### [#98](https://github.com/240103098-code/student-marketplace/issues/98) — End-to-end authentication, selling, and moderation journeys

**Prerequisites:** [#20](https://github.com/240103098-code/student-marketplace/issues/20), [#25](https://github.com/240103098-code/student-marketplace/issues/25), [#26](https://github.com/240103098-code/student-marketplace/issues/26), [#37](https://github.com/240103098-code/student-marketplace/issues/37), [#41](https://github.com/240103098-code/student-marketplace/issues/41), [#48](https://github.com/240103098-code/student-marketplace/issues/48), [#52](https://github.com/240103098-code/student-marketplace/issues/52), [#53](https://github.com/240103098-code/student-marketplace/issues/53), [#56](https://github.com/240103098-code/student-marketplace/issues/56), [#57](https://github.com/240103098-code/student-marketplace/issues/57), [#58](https://github.com/240103098-code/student-marketplace/issues/58), [#64](https://github.com/240103098-code/student-marketplace/issues/64), [#66](https://github.com/240103098-code/student-marketplace/issues/66). **Original scope:** [#98](https://github.com/240103098-code/student-marketplace/issues/98), [#99](https://github.com/240103098-code/student-marketplace/issues/99), [#100](https://github.com/240103098-code/student-marketplace/issues/100).

- **[#98](https://github.com/240103098-code/student-marketplace/issues/98): Test end-to-end registration and sign-in.** Add an automated browser/API flow covering university registration, mocked SMTP delivery, verification, login, refresh, and logout. Assert that unverified or signed-out users cannot browse private listings.
- **[#99](https://github.com/240103098-code/student-marketplace/issues/99): Test end-to-end selling and discovery.** Add a flow in which one verified student creates a listing with photos and another searches, filters, opens it, and follows an external contact link. Then mark the item sold and assert it disappears from public results but stays in the seller's dashboard.
- **[#100](https://github.com/240103098-code/student-marketplace/issues/100): Test end-to-end moderation and account controls.** Add a flow for submitting a listing report, reviewing it as an admin, removing the item, and suspending its owner. Confirm the owner cannot access protected endpoints and that a separate user can still use the marketplace.

**Goal:** Prove a new student can enter the marketplace securely. Prove the primary buy/sell browsing flow works. Prove reporting and security controls work together.

### [#101](https://github.com/240103098-code/student-marketplace/issues/101) — Responsive accessibility and deletion/upload safety verification

**Prerequisites:** [#32](https://github.com/240103098-code/student-marketplace/issues/32), [#36](https://github.com/240103098-code/student-marketplace/issues/36), [#41](https://github.com/240103098-code/student-marketplace/issues/41), [#46](https://github.com/240103098-code/student-marketplace/issues/46), [#48](https://github.com/240103098-code/student-marketplace/issues/48), [#54](https://github.com/240103098-code/student-marketplace/issues/54), [#57](https://github.com/240103098-code/student-marketplace/issues/57), [#62](https://github.com/240103098-code/student-marketplace/issues/62). **Original scope:** [#101](https://github.com/240103098-code/student-marketplace/issues/101), [#102](https://github.com/240103098-code/student-marketplace/issues/102).

- **[#101](https://github.com/240103098-code/student-marketplace/issues/101): Check keyboard access and responsive layouts.** Review forms, dialogs, listing cards, image gallery, and navigation at narrow and wide widths. Fix missing labels, focus behavior, keyboard interactions, and obvious contrast problems, and add targeted tests where practical.
- **[#102](https://github.com/240103098-code/student-marketplace/issues/102): Verify upload cleanup and deletion rules.** Test deleting listings, replacing avatars, deleting accounts, and removing listings as admin against the uploads directory and database references. Document any deliberate moderation/audit retention exception and verify that ordinary users cannot retrieve retained private records.

**Goal:** Make core student and admin screens usable on phones and with keyboards. Avoid orphaned images and unexpected data exposure.

### [#103](https://github.com/240103098-code/student-marketplace/issues/103) — Prepare a repeatable local demo

**Prerequisites:** [#98](https://github.com/240103098-code/student-marketplace/issues/98), [#101](https://github.com/240103098-code/student-marketplace/issues/101). **Original scope:** [#103](https://github.com/240103098-code/student-marketplace/issues/103).

- **[#103](https://github.com/240103098-code/student-marketplace/issues/103): Prepare a repeatable local demo.** Write a concise checklist to start PostgreSQL, FastAPI, and React, configure SMTP securely, apply migrations, and create a test admin and verified student accounts. Test the instructions from a clean setup and include a manual walkthrough of registration, listing, discovery, reporting, and moderation.

**Goal:** Run the complete MVP locally from documented steps.

The final demo depends on both end-to-end journeys #98 and responsive/deletion/upload verification #101; document real SMTP separately from fake test delivery and keep credentials local.

## Complete original-to-canonical mapping

Each original ID from 1 through 103 appears exactly once below. Every source ID maps to the canonical issue in its row. Rows #1–#5 are completed history; all other rows remain open packages. Noncanonical IDs are superseded records, retained on GitHub with replacement links and `not_planned` closure reasons.

| Canonical issue | Original issue IDs mapped here | Record |
| --- | --- | --- |
| [#1](https://github.com/240103098-code/student-marketplace/issues/1) | [#1](https://github.com/240103098-code/student-marketplace/issues/1) | Completed history |
| [#2](https://github.com/240103098-code/student-marketplace/issues/2) | [#2](https://github.com/240103098-code/student-marketplace/issues/2) | Completed history |
| [#3](https://github.com/240103098-code/student-marketplace/issues/3) | [#3](https://github.com/240103098-code/student-marketplace/issues/3) | Completed history |
| [#4](https://github.com/240103098-code/student-marketplace/issues/4) | [#4](https://github.com/240103098-code/student-marketplace/issues/4) | Completed history |
| [#5](https://github.com/240103098-code/student-marketplace/issues/5) | [#5](https://github.com/240103098-code/student-marketplace/issues/5) | Completed history |
| [#6](https://github.com/240103098-code/student-marketplace/issues/6) | [#6](https://github.com/240103098-code/student-marketplace/issues/6) | Open package |
| [#7](https://github.com/240103098-code/student-marketplace/issues/7) | [#7](https://github.com/240103098-code/student-marketplace/issues/7) | Open package |
| [#8](https://github.com/240103098-code/student-marketplace/issues/8) | [#8](https://github.com/240103098-code/student-marketplace/issues/8), [#9](https://github.com/240103098-code/student-marketplace/issues/9) | Open package |
| [#10](https://github.com/240103098-code/student-marketplace/issues/10) | [#10](https://github.com/240103098-code/student-marketplace/issues/10), [#11](https://github.com/240103098-code/student-marketplace/issues/11), [#12](https://github.com/240103098-code/student-marketplace/issues/12) | Open package |
| [#13](https://github.com/240103098-code/student-marketplace/issues/13) | [#13](https://github.com/240103098-code/student-marketplace/issues/13), [#14](https://github.com/240103098-code/student-marketplace/issues/14), [#15](https://github.com/240103098-code/student-marketplace/issues/15) | Open package |
| [#16](https://github.com/240103098-code/student-marketplace/issues/16) | [#16](https://github.com/240103098-code/student-marketplace/issues/16) | Open package |
| [#17](https://github.com/240103098-code/student-marketplace/issues/17) | [#17](https://github.com/240103098-code/student-marketplace/issues/17), [#18](https://github.com/240103098-code/student-marketplace/issues/18), [#19](https://github.com/240103098-code/student-marketplace/issues/19) | Open package |
| [#20](https://github.com/240103098-code/student-marketplace/issues/20) | [#20](https://github.com/240103098-code/student-marketplace/issues/20), [#21](https://github.com/240103098-code/student-marketplace/issues/21), [#22](https://github.com/240103098-code/student-marketplace/issues/22), [#23](https://github.com/240103098-code/student-marketplace/issues/23) | Open package |
| [#24](https://github.com/240103098-code/student-marketplace/issues/24) | [#24](https://github.com/240103098-code/student-marketplace/issues/24) | Open package |
| [#25](https://github.com/240103098-code/student-marketplace/issues/25) | [#25](https://github.com/240103098-code/student-marketplace/issues/25), [#28](https://github.com/240103098-code/student-marketplace/issues/28) | Open package |
| [#26](https://github.com/240103098-code/student-marketplace/issues/26) | [#26](https://github.com/240103098-code/student-marketplace/issues/26), [#27](https://github.com/240103098-code/student-marketplace/issues/27) | Open package |
| [#29](https://github.com/240103098-code/student-marketplace/issues/29) | [#29](https://github.com/240103098-code/student-marketplace/issues/29) | Open package |
| [#30](https://github.com/240103098-code/student-marketplace/issues/30) | [#30](https://github.com/240103098-code/student-marketplace/issues/30), [#31](https://github.com/240103098-code/student-marketplace/issues/31) | Open package |
| [#32](https://github.com/240103098-code/student-marketplace/issues/32) | [#32](https://github.com/240103098-code/student-marketplace/issues/32), [#38](https://github.com/240103098-code/student-marketplace/issues/38), [#39](https://github.com/240103098-code/student-marketplace/issues/39) | Open package |
| [#62](https://github.com/240103098-code/student-marketplace/issues/62) | [#62](https://github.com/240103098-code/student-marketplace/issues/62) | Open package |
| [#63](https://github.com/240103098-code/student-marketplace/issues/63) | [#63](https://github.com/240103098-code/student-marketplace/issues/63), [#67](https://github.com/240103098-code/student-marketplace/issues/67), [#68](https://github.com/240103098-code/student-marketplace/issues/68) | Open package |
| [#66](https://github.com/240103098-code/student-marketplace/issues/66) | [#66](https://github.com/240103098-code/student-marketplace/issues/66) | Open package |
| [#33](https://github.com/240103098-code/student-marketplace/issues/33) | [#33](https://github.com/240103098-code/student-marketplace/issues/33), [#34](https://github.com/240103098-code/student-marketplace/issues/34), [#35](https://github.com/240103098-code/student-marketplace/issues/35), [#69](https://github.com/240103098-code/student-marketplace/issues/69), [#70](https://github.com/240103098-code/student-marketplace/issues/70), [#71](https://github.com/240103098-code/student-marketplace/issues/71) | Open package |
| [#37](https://github.com/240103098-code/student-marketplace/issues/37) | [#37](https://github.com/240103098-code/student-marketplace/issues/37), [#40](https://github.com/240103098-code/student-marketplace/issues/40), [#81](https://github.com/240103098-code/student-marketplace/issues/81), [#82](https://github.com/240103098-code/student-marketplace/issues/82) | Open package |
| [#48](https://github.com/240103098-code/student-marketplace/issues/48) | [#48](https://github.com/240103098-code/student-marketplace/issues/48), [#49](https://github.com/240103098-code/student-marketplace/issues/49), [#50](https://github.com/240103098-code/student-marketplace/issues/50), [#51](https://github.com/240103098-code/student-marketplace/issues/51), [#83](https://github.com/240103098-code/student-marketplace/issues/83), [#84](https://github.com/240103098-code/student-marketplace/issues/84), [#85](https://github.com/240103098-code/student-marketplace/issues/85), [#86](https://github.com/240103098-code/student-marketplace/issues/86) | Open package |
| [#87](https://github.com/240103098-code/student-marketplace/issues/87) | [#87](https://github.com/240103098-code/student-marketplace/issues/87), [#88](https://github.com/240103098-code/student-marketplace/issues/88) | Open package |
| [#36](https://github.com/240103098-code/student-marketplace/issues/36) | [#36](https://github.com/240103098-code/student-marketplace/issues/36), [#89](https://github.com/240103098-code/student-marketplace/issues/89) | Open package |
| [#41](https://github.com/240103098-code/student-marketplace/issues/41) | [#41](https://github.com/240103098-code/student-marketplace/issues/41), [#42](https://github.com/240103098-code/student-marketplace/issues/42), [#43](https://github.com/240103098-code/student-marketplace/issues/43), [#44](https://github.com/240103098-code/student-marketplace/issues/44), [#45](https://github.com/240103098-code/student-marketplace/issues/45), [#72](https://github.com/240103098-code/student-marketplace/issues/72), [#73](https://github.com/240103098-code/student-marketplace/issues/73), [#74](https://github.com/240103098-code/student-marketplace/issues/74), [#75](https://github.com/240103098-code/student-marketplace/issues/75), [#76](https://github.com/240103098-code/student-marketplace/issues/76), [#77](https://github.com/240103098-code/student-marketplace/issues/77) | Open package |
| [#46](https://github.com/240103098-code/student-marketplace/issues/46) | [#46](https://github.com/240103098-code/student-marketplace/issues/46), [#47](https://github.com/240103098-code/student-marketplace/issues/47), [#78](https://github.com/240103098-code/student-marketplace/issues/78), [#79](https://github.com/240103098-code/student-marketplace/issues/79), [#80](https://github.com/240103098-code/student-marketplace/issues/80) | Open package |
| [#54](https://github.com/240103098-code/student-marketplace/issues/54) | [#54](https://github.com/240103098-code/student-marketplace/issues/54), [#55](https://github.com/240103098-code/student-marketplace/issues/55), [#91](https://github.com/240103098-code/student-marketplace/issues/91) | Open package |
| [#52](https://github.com/240103098-code/student-marketplace/issues/52) | [#52](https://github.com/240103098-code/student-marketplace/issues/52), [#97](https://github.com/240103098-code/student-marketplace/issues/97) | Open package |
| [#53](https://github.com/240103098-code/student-marketplace/issues/53) | [#53](https://github.com/240103098-code/student-marketplace/issues/53), [#90](https://github.com/240103098-code/student-marketplace/issues/90) | Open package |
| [#56](https://github.com/240103098-code/student-marketplace/issues/56) | [#56](https://github.com/240103098-code/student-marketplace/issues/56), [#61](https://github.com/240103098-code/student-marketplace/issues/61), [#92](https://github.com/240103098-code/student-marketplace/issues/92), [#93](https://github.com/240103098-code/student-marketplace/issues/93) | Open package |
| [#57](https://github.com/240103098-code/student-marketplace/issues/57) | [#57](https://github.com/240103098-code/student-marketplace/issues/57), [#60](https://github.com/240103098-code/student-marketplace/issues/60), [#94](https://github.com/240103098-code/student-marketplace/issues/94), [#95](https://github.com/240103098-code/student-marketplace/issues/95) | Open package |
| [#58](https://github.com/240103098-code/student-marketplace/issues/58) | [#58](https://github.com/240103098-code/student-marketplace/issues/58), [#59](https://github.com/240103098-code/student-marketplace/issues/59), [#96](https://github.com/240103098-code/student-marketplace/issues/96) | Open package |
| [#64](https://github.com/240103098-code/student-marketplace/issues/64) | [#64](https://github.com/240103098-code/student-marketplace/issues/64), [#65](https://github.com/240103098-code/student-marketplace/issues/65) | Open package |
| [#98](https://github.com/240103098-code/student-marketplace/issues/98) | [#98](https://github.com/240103098-code/student-marketplace/issues/98), [#99](https://github.com/240103098-code/student-marketplace/issues/99), [#100](https://github.com/240103098-code/student-marketplace/issues/100) | Open package |
| [#101](https://github.com/240103098-code/student-marketplace/issues/101) | [#101](https://github.com/240103098-code/student-marketplace/issues/101), [#102](https://github.com/240103098-code/student-marketplace/issues/102) | Open package |
| [#103](https://github.com/240103098-code/student-marketplace/issues/103) | [#103](https://github.com/240103098-code/student-marketplace/issues/103) | Open package |

## Administrative consolidation audit

Before supersession closures, independent QA checks full 1–103 coverage, exactly one survivor per source, preserved acceptance criteria, acyclic canonical prerequisites, unchanged completed history, and untouched application work. Update survivor bodies first; only then post replacement comments and close the 64 superseded records as `not_planned`. Verify the resulting 34-open-issue count and links. Administrative audit PASS authorizes consolidation, not implementation completion.
