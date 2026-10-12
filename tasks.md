# Student Marketplace — MVP Task Backlog

Tasks are ordered roughly by implementation sequence. Each task is intended to fit into one development session, has a self-contained scope, and should include focused tests where practical. The product is a React + FastAPI + PostgreSQL web marketplace restricted to verified students at one university; buying, payments, and pickup happen outside the platform.

**Unresolved decisions:** The listing-approval policy (automatic, manual, or hybrid), approved university email domain, final category names, SMTP provider, and several security/upload limits are not yet selected. Tasks that require those choices explicitly call them out; no option is assumed to have been approved.

## 1. Create an empty project with a passing test
Goal: Start a clean repository in which a basic automated test passes.
Description: Create an empty project structure with `frontend/`, `backend/`, and `_docs/`, plus a minimal test runner and one trivial passing test. Document the single command used to run the test; do not implement marketplace features.

## 2. Document local prerequisites and startup commands
Goal: Make the development environment reproducible for a new contributor.
Description: Write setup instructions for Python, Node.js, PostgreSQL, environment variables, and the project's directory layout. Include commands for installing dependencies and running tests locally, updating examples as the app grows.

## 3. Initialize the FastAPI application
Goal: Provide a minimal backend that starts locally.
Description: Create the FastAPI entry point and separate router locations for authentication, users, listings, and administration. Add a `/health` endpoint returning a success response and a test confirming it.

## 4. Set up backend test fixtures
Goal: Allow isolated FastAPI endpoint tests.
Description: Configure pytest, a reusable API test client, and dependency overrides so endpoint tests do not send real emails or depend on a shared developer database. Add a small fixture example to prove the setup works.

## 5. Initialize the React application
Goal: Provide a working frontend development shell.
Description: Create a React app inside `frontend/` with its package scripts and a minimal root page. Confirm the development server starts and the production build completes.

## 6. Set up frontend automated tests
Goal: Allow reliable component tests.
Description: Configure a React-compatible test runner and testing utilities. Add one simple rendering test and document the command for running frontend tests.

## 7. Add backend environment configuration
Goal: Load runtime settings without committing secrets.
Description: Define typed settings for database URL, approved email domain, SMTP credentials, token secrets, frontend origin, and upload directory. Provide a placeholder `.env.example`, ignore real `.env` files, and test missing required settings.

## 8. Connect FastAPI to PostgreSQL
Goal: Establish reusable database sessions.
Description: Configure SQLAlchemy's engine, session factory, and FastAPI database dependency for a local PostgreSQL instance. Add an isolated connection or integration test that checks a simple database operation.

## 9. Initialize Alembic migrations
Goal: Track database schema changes predictably.
Description: Configure Alembic to use the project's SQLAlchemy metadata and environment settings. Create and test a baseline migration, including a clean upgrade path for a local database.

## 10. Define the user database model
Goal: Store verified student accounts and basic profiles.
Description: Add a SQLAlchemy user table with unique university email, password hash, verification state, name, optional avatar path, optional contact fields, role, and suspension state. Include a migration and tests for required fields and uniqueness.

## 11. Define verification-code storage
Goal: Persist one-time email verification challenges safely.
Description: Model hashed verification codes with their owner, purpose, expiry, failed-attempt count, and used state. Add a migration and tests demonstrating that verification can enforce five incorrect attempts per issued code.

## 12. Define refresh-session storage
Goal: Support revocable and rotating refresh tokens.
Description: Add a database-backed refresh-session or refresh-token record tied to a user, with expiry and revocation state. Include a migration and tests for revoking an existing session and rejecting an expired one.

## 13. Define categories and listing schema
Goal: Store items with a fixed category and New/Used condition.
Description: Create database structures for listings with owner, title, description, price, predefined category, condition (`new` or `used`), publication date, and active/sold status. Keep the category set configurable until the university's final predefined list is agreed, and test valid versus invalid values.

## 14. Define listing-photo records
Goal: Associate up to five ordered photos with each listing.
Description: Add a listing-photo model containing the owning listing, stored relative file path, and display order. Include a migration and model/service tests showing the first photo can be identified as the cover image.

## 15. Define listing-report records
Goal: Store reasons users submit for inappropriate listings.
Description: Create a report table linking reporter and listing, a reason selected from a small controlled set, and an admin-review state. Include a migration and tests for valid reasons and associations.

## 16. Agree on remaining MVP configuration values
Goal: Record unresolved choices before behavior depends on them.
Description: Confirm the approved university email domain, final category list, verification-code duration and resend rules, photo file types/limits, and whether listings require approval. Record the chosen values in the requirements file; do not silently treat earlier recommendations as decisions.

## 17. Validate university email addresses
Goal: Reject registration from unapproved email domains.
Description: Implement server-side email normalization and exact-domain matching against the one configured university domain. Test allowed addresses, addresses from other domains, and lookalike suffixes.

## 18. Implement password hashing utilities
Goal: Store and verify passwords securely.
Description: Add a maintained password-hashing algorithm/library and utilities for hashing and comparing passwords without storing plaintext values. Test successful verification, mismatched passwords, and distinct salts.

## 19. Implement account registration API
Goal: Let students start registration with university email and password.
Description: Add an endpoint that validates the approved email domain, hashes the password, and creates an unverified user account. Return safe errors for invalid input or duplicate addresses and test the endpoint without sending an email yet.

## 20. Build the SMTP email sender
Goal: Send real transactional emails through configured SMTP settings.
Description: Add a small email service that sends a message using environment-provided server credentials, TLS configuration, and sender address. Mock delivery in automated tests and document how to configure a real SMTP account locally.

## 21. Issue registration verification codes
Goal: Email a one-time code when a student registers.
Description: Generate a secure code, store only its hash and metadata, and send the code using the SMTP service. Use the agreed expiry setting and test that the emailed code corresponds to the stored challenge without persisting plaintext.

## 22. Verify student email addresses
Goal: Activate accounts only after a correct verification code.
Description: Add an API that checks code validity, expiry, and failed-attempt count, then marks the account verified on success. After five incorrect attempts, invalidate that code and require a newly issued code; test boundary cases.

## 23. Resend a registration verification code
Goal: Recover when a student loses or does not receive a code.
Description: Add an endpoint that issues a replacement code for an unverified account, invalidating the prior code. Apply the agreed resend cooldown and request limits, and test that an old code no longer works.

## 24. Create JWT access tokens
Goal: Authenticate requests using short-lived access tokens.
Description: Implement signed JWT issuance and validation, including user identity and token expiry. Add tests for valid, expired, malformed, and incorrectly signed tokens.

## 25. Implement login API
Goal: Let verified students sign in with email and password.
Description: Add an endpoint that validates credentials, requires a verified and unsuspended account, and returns or sets the established session credentials. Test valid login and rejection of incorrect passwords, unverified users, and suspended users.

## 26. Implement refresh-token rotation API
Goal: Renew sessions without reusing old refresh tokens.
Description: Build an endpoint that accepts a valid stored refresh token, revokes or rotates it, and issues a new access/refresh token pair. Test replay rejection, expired tokens, and revoked sessions.

## 27. Implement logout and session revocation
Goal: Let users explicitly end a session.
Description: Add a logout endpoint that invalidates the active refresh session and clears any refresh-token cookie used by the app. Test that logout prevents future refreshes from that session.

## 28. Protect verified-user endpoints
Goal: Keep all marketplace data private to verified students.
Description: Add reusable FastAPI dependencies that require an authenticated, verified, non-suspended user for listings, profiles, searches, and reports. Test anonymous, unverified, and suspended requests against at least one protected endpoint.

## 29. Configure browser session security
Goal: Use access and refresh tokens safely from React.
Description: Define the token transport and storage strategy, including refresh-cookie attributes if cookies are chosen, CORS origin restrictions, and CSRF safeguards where necessary. Test browser-facing auth behavior so credentials are not exposed to unrelated origins.

## 30. Add current-user profile API
Goal: Return a student's own basic profile.
Description: Create a protected `GET /users/me` endpoint exposing name, verified email, optional profile photo, and contact details without password hashes or tokens. Add response-schema tests verifying private account fields are omitted.

## 31. Add profile editing API
Goal: Allow changes to name, photo path, and contact methods only.
Description: Create a protected profile update endpoint with validated fields for name and seller contact details. Reject attempts to change the verified university email, role, or verification state, and test both allowed and forbidden updates.

## 32. Add a profile-photo upload endpoint
Goal: Let students add or replace an optional avatar.
Description: Validate image type and size using agreed upload limits, store the file under the backend uploads directory, and persist its relative path. Test unauthorized uploads, invalid files, and replacement handling.

## 33. Add authenticated password change
Goal: Let logged-in students change passwords.
Description: Build an endpoint requiring the current password and a valid new password, then replace the stored hash. Test a correct change and rejection when the existing password is wrong.

## 34. Request a forgotten-password reset code
Goal: Send password recovery codes to registered university email addresses.
Description: Add a reset-request endpoint that creates a purpose-specific, expiring code and sends it through SMTP. Use a non-enumerating response for unknown addresses and test request limits and code issuance.

## 35. Reset a forgotten password
Goal: Let users set a new password after email-code verification.
Description: Validate the reset code, enforce its attempt and expiry rules, replace the account's password hash, and invalidate the used code. Revoke existing refresh sessions after a successful reset and test that stale sessions cannot refresh.

## 36. Permanently delete a user account
Goal: Support self-service deletion of an account and its data.
Description: Add a protected endpoint that requires an appropriate confirmation and deletes or anonymizes the user's profile, listings, associated photos, and contact information. Document and test any narrowly scoped security/legal retention exceptions instead of inventing a general retention policy.

## 37. Validate listing input fields
Goal: Enforce consistent listing data before saving.
Description: Create input validation for title, description, nonnegative price in the project's agreed currency, predefined category, and `new`/`used` condition. Keep any not-yet-decided length or price limits configurable, and add valid/invalid schema tests.

## 38. Implement listing image-file validation
Goal: Accept safe uploads without allowing arbitrary files.
Description: Validate actual image content, approved formats, file size, and limits on multipart requests before writing to `uploads/`. Add tests for non-images, oversized uploads, path traversal attempts, and allowed formats.

## 39. Implement listing-photo storage service
Goal: Save and clean up local listing images consistently.
Description: Build helpers to write images under the backend `uploads/` directory with generated safe filenames and ordered metadata. Add tests for storing, retrieving the generated path, and deleting files when a listing is removed.

## 40. Create a listing API
Goal: Let verified students publish a listing with up to five photos.
Description: Add a protected endpoint that saves a listing owned by the authenticated user and attaches zero to five validated images, with the first image as cover. Enforce the publication policy selected in Task 16 and test ownership, field validation, and the six-photo rejection case.

## 41. List active marketplace items API
Goal: Show verified users only publicly visible active listings.
Description: Add a paginated endpoint returning listing cards with title, price, cover image, category, condition, and publication date ordered newest first. Exclude sold, deleted, and any not-yet-approved listings under the selected publication policy, and test ordering and visibility.

## 42. Search listings by keyword API
Goal: Find active items from text entered by a buyer.
Description: Extend the listing-browse endpoint with a case-insensitive keyword query matching suitable title and description fields. Keep newest-first ordering and test empty queries, matching terms, and hidden/sold exclusions.

## 43. Filter listings by category API
Goal: Restrict results to one predefined category.
Description: Add a category query parameter to the protected listing-browse endpoint and validate it against the configured categories. Test results inside and outside the category while preserving newest-first ordering.

## 44. Filter listings by price range API
Goal: Return items within the requested price bounds.
Description: Add minimum and maximum price parameters to the listing-browse endpoint, including validation that minimum does not exceed maximum. Test inclusive boundaries and combination with keyword searches.

## 45. Filter listings by condition API
Goal: Find only New or Used items.
Description: Add an optional `new`/`used` condition query parameter to the protected listing-browse endpoint. Test that it composes with price, category, and keyword filters without altering newest-first sort order.

## 46. Retrieve listing details API
Goal: Show full information for one visible listing.
Description: Add a protected endpoint returning the description, price, category, condition, ordered photos, seller name, and available seller contact methods for an active listing. Reject access to listings that are sold, removed, or unapproved except where the owner/admin is explicitly authorized.

## 47. Generate safe external seller-contact links
Goal: Support opening the seller's preferred messaging app.
Description: Validate stored contact identifiers and generate allowed Telegram or WhatsApp links without permitting arbitrary script or unsafe URL schemes. Test supported contacts, missing contacts, and invalid identifiers.

## 48. List the seller's own listings API
Goal: Show active and sold items in My Listings.
Description: Add a protected endpoint returning only listings owned by the signed-in user, including their active or sold status. Test that another student's listings are never included and that sold listings remain in the owner's results.

## 49. Edit permitted listing fields API
Goal: Let owners change price and description after publishing.
Description: Add an owner-only update endpoint accepting exactly price and description, using the same validation rules as listing creation. Reject attempted changes to title, photos, category, condition, ownership, or status through this endpoint and test those restrictions.

## 50. Mark a listing as sold API
Goal: Remove sold items from marketplace search but keep seller history.
Description: Add an owner-only action that transitions an active listing to sold. Test that the item disappears from browse/search results but remains visible in My Listings.

## 51. Delete an owned listing API
Goal: Allow sellers to permanently remove a listing.
Description: Add an owner-only deletion endpoint that removes its database records and locally stored photos safely. Test authorization, nonexistent IDs, and successful image cleanup.

## 52. Decide and implement listing publication approval
Goal: Apply the chosen automatic, manual, or hybrid review workflow.
Description: After the product owner selects a policy, implement the smallest additional listing state and admin action needed to enforce it. Test that a listing becomes browse-visible at the right point and that unapproved items never leak into public results.

## 53. Submit a listing report API
Goal: Let verified users flag an active listing using a reason.
Description: Add a protected endpoint that creates a report for a visible listing with a controlled reason such as spam, prohibited item, or misleading information. Validate the reason and listing visibility, and test malformed or unauthorized reports.

## 54. Add an administrator authorization guard
Goal: Restrict management endpoints to admin users.
Description: Create a reusable backend dependency that checks a signed-in verified user's admin role and active account state. Test that ordinary users cannot access admin routes even if they change client-side requests.

## 55. Define how the first admin is created
Goal: Safely bootstrap administrator access in local development.
Description: Document and implement a controlled local admin-provisioning method that does not allow public self-registration as an admin. Test that registration cannot set the admin role and that the bootstrap procedure is deliberate.

## 56. List users in the admin API
Goal: Give admins a read-only overview of registered accounts.
Description: Create a protected admin endpoint returning paginated users with email, name, verified state, and suspension state. Exclude password hashes, reset codes, refresh tokens, and other secrets from responses and tests.

## 57. List listings in the admin API
Goal: Let admins inspect active, sold, and removed-status listings as appropriate.
Description: Add an admin endpoint with listing owner, status, publication date, and basic details. Ensure it can review items not visible in normal marketplace search, subject to the chosen publication policy.

## 58. Review listing reports in the admin API
Goal: Show admins submitted reports and their review state.
Description: Add an admin endpoint listing reports with listing reference, reporter reference, reason, creation date, and review status. Test role protection and filtering by pending versus reviewed reports.

## 59. Mark a report reviewed
Goal: Prevent admins from repeatedly processing the same report.
Description: Add an admin action to update a report's review state after inspection. Test that only admins may use it and that it does not automatically remove a listing.

## 60. Remove an inappropriate listing as admin
Goal: Let moderators take reported listings out of public view.
Description: Add an admin endpoint for removing a listing, separate from seller-initiated deletion, while preserving any minimum record necessary to understand report actions. Test that removed items disappear from browse results and that owners cannot restore them through edit requests.

## 61. Suspend and unsuspend accounts as admin
Goal: Block accounts that violate marketplace rules.
Description: Create admin actions to update a user's suspension state and test both suspension and reversal. Ensure suspended users cannot log in or use protected marketplace APIs, including when previously issued tokens remain unexpired.

## 62. Set up React routes and shared page layout
Goal: Provide navigation for the student marketplace pages.
Description: Add a shared header and route placeholders for sign-in, registration, verification, home, listing details, new listing, My Listings, profile, and admin. Add a simple navigation test without implementing those pages' business logic.

## 63. Add frontend API client and auth handling
Goal: Connect React to FastAPI with consistent session behavior.
Description: Create a centralized HTTP client that uses the backend base URL, attaches credentials or access tokens appropriately, and handles unauthorized responses. Test the request configuration and one simulated expired-session response.

## 64. Build registration form
Goal: Let students enter university email and password in React.
Description: Create a responsive registration form that validates basic input, calls the registration API, and navigates to email verification on success. Show understandable error messages for invalid domains and duplicate registrations.

## 65. Build email verification screen
Goal: Let newly registered students activate their accounts.
Description: Create a code-entry form and resend-code control connected to the verification APIs. Display incorrect-attempt feedback and make the five-attempt limit and code replacement understandable.

## 66. Build login form
Goal: Let verified students sign in through the browser.
Description: Build an email/password form connected to the login endpoint and route successful users to the marketplace. Show clear errors for bad credentials and unverified accounts without leaking sensitive technical details.

## 67. Protect frontend marketplace routes
Goal: Prevent anonymous or unverified users from opening private app pages.
Description: Add a reusable auth guard for home, listings, My Listings, profile, and admin routes, using backend verification as the final authority. Test redirects for unauthenticated users and the admin-route guard for ordinary students.

## 68. Add logout UI
Goal: Let users sign out from the application header or profile.
Description: Connect a visible logout action to the backend revocation endpoint and clear client-side session state. Test that signing out returns the user to the login screen and prevents reopening protected pages without signing in.

## 69. Build password-change form
Goal: Let signed-in students update their password.
Description: Add a profile/settings form for current password, new password, and confirmation, then call the password-change endpoint. Display validation and success/error states without echoing entered passwords.

## 70. Build forgotten-password request screen
Goal: Let students request a reset code by email.
Description: Provide a university-email input that calls the reset-request endpoint and explains the next step. Display the same generic success message for known and unknown addresses.

## 71. Build password-reset confirmation screen
Goal: Let students set a new password with a reset code.
Description: Create inputs for verification code, new password, and confirmation, then call the reset API. Handle expired/invalid codes and show a route back to login after success.

## 72. Build marketplace home page
Goal: Display the search bar, categories, and newest listing cards.
Description: Implement a modern minimal React page with a white/neutral design, category navigation, and a responsive card grid showing photo and price. Load the newest visible listings from the protected browse API and include loading, empty, and error states.

## 73. Build reusable listing card component
Goal: Present consistent item previews across marketplace pages.
Description: Create a card component for cover photo, title, price, condition, and optional status on owner pages. Test behavior when a listing has no photo and when titles are long.

## 74. Connect keyword search in React
Goal: Let students find listings by typing search terms.
Description: Wire a search field to the backend keyword query and render matching results on the browse page. Include a clear-search action, loading feedback, and a no-results message.

## 75. Build category filter UI
Goal: Let students browse one predefined category.
Description: Render the configured category options and pass the selection to the browse API. Keep the selected category visible and test that clearing it restores the unfiltered list.

## 76. Build price-range filter UI
Goal: Let students restrict results to affordable listings.
Description: Create minimum and maximum price inputs and send valid ranges to the browse API. Show validation when minimum exceeds maximum and keep results ordered newest first.

## 77. Build New/Used condition filter UI
Goal: Let students filter items by condition.
Description: Add New, Used, and All filter choices to the browse interface. Connect the selected value to the API and test its interaction with active category and price filters.

## 78. Build listing details page
Goal: Show one active listing's complete information.
Description: Display title, description, price, category, condition, seller name, and ordered photos from the listing-details API. Handle inaccessible or sold listings gracefully rather than exposing seller information through an error state.

## 79. Build listing photo gallery
Goal: Let buyers view up to five images of an item.
Description: Create a reusable gallery with the first image as the main photo and controls to switch between images. Include an accessible single-image/empty-image state and test gallery navigation.

## 80. Build seller contact panel
Goal: Help buyers contact a seller outside the platform.
Description: Display available seller contact details and a Contact Seller button that opens a validated Telegram or WhatsApp URL when one exists. Do not add in-app chat, payment, or purchase workflows.

## 81. Build new-listing form
Goal: Let verified students submit an item for sale.
Description: Add inputs for title, description, price, predefined category, and New/Used condition, connected to the create-listing API. Show validation errors and a success state consistent with the selected publication-approval policy.

## 82. Build listing photo uploader
Goal: Attach up to five ordered images while creating a listing.
Description: Add an image picker with previews, removal before submission, and a clear five-photo limit. Submit the photos using the backend upload contract and display errors for unsupported or oversized files.

## 83. Build My Listings dashboard
Goal: Show a seller's active and sold items separately.
Description: Create a protected page that loads only the signed-in user's listings and groups or filters them by Active and Sold. Include clear empty states and actions for editing, marking sold, and deleting each applicable item.

## 84. Build restricted listing-edit form
Goal: Let owners change only price and description.
Description: Provide a form populated from an owned listing with just those two editable fields. Do not include controls for editing title, photos, category, or condition, and test that submitted data contains only permitted properties.

## 85. Add Mark as Sold interaction
Goal: Let sellers close a listing from My Listings.
Description: Connect a confirmation action to the mark-sold API, then update the listing's status in the dashboard. Ensure sold items no longer offer a misleading action to publish or hide them.

## 86. Add Delete Listing interaction
Goal: Let sellers remove a listing deliberately.
Description: Add a confirmation dialog and connect it to the owner-only listing delete API. Update the dashboard after success and handle failed or unauthorized deletions visibly.

## 87. Build profile details page
Goal: Show a student's verified identity and contact information.
Description: Create a protected profile screen showing name, fixed university email, optional avatar, and contact methods. Make it clear that the verified email cannot be edited.

## 88. Build profile-edit form
Goal: Let students update name, avatar, and contact details.
Description: Connect editable profile fields and optional avatar upload to the relevant backend endpoints. Validate contact details and present save success or failure without exposing administrative account fields.

## 89. Add account deletion UI
Goal: Let students permanently remove their own account.
Description: Provide a clearly worded confirmation step connected to the delete-account API, explaining that listings and profile information are removed. Clear the local session and return the user to an unauthenticated screen after deletion.

## 90. Build listing-report interaction
Goal: Let students report an inappropriate listing.
Description: Add a Report action to visible listing details with a fixed reason selector and a submit button. Connect it to the report API and show a simple confirmation without advanced reporter-side status tracking.

## 91. Build admin navigation and access screen
Goal: Give authorized admins a separate moderation workspace.
Description: Create an admin layout with links to users, listings, and reports. Hide it from ordinary users for convenience while relying on backend admin checks for actual security.

## 92. Build admin user list
Goal: Let admins find accounts and view suspension status.
Description: Load the admin users endpoint into a simple table with email, name, verification, and suspension columns. Include pagination or another lightweight way to navigate large result sets.

## 93. Add admin suspend/unsuspend controls
Goal: Let admins moderate user access from the UI.
Description: Connect confirmation actions in the admin users table to suspend and unsuspend endpoints. Refresh user state after changes and display errors without assuming the operation succeeded.

## 94. Build admin listing list
Goal: Let admins inspect listed items and their publication states.
Description: Load the admin listing endpoint into a table showing title, owner, status, and publication date. Provide a way to open details and handle listings unavailable to ordinary students.

## 95. Add admin remove-listing control
Goal: Let admins remove inappropriate content from the UI.
Description: Add a confirmation action on admin listing rows that calls the moderation removal API. Refresh the list and verify the removed listing is not available through normal search.

## 96. Build admin report queue
Goal: Let admins review reasons for listing reports.
Description: Create a report list showing reason, item reference, reporter reference, time, and pending/reviewed state. Connect a Mark Reviewed control to the admin API and let the admin open the reported listing for investigation.

## 97. Build approval UI if required by the chosen policy
Goal: Support manual approval or hybrid review only if selected.
Description: If the owner selects manual or hybrid listing review, add a small admin queue and the corresponding approve/reject actions. If automatic publishing is selected, mark this task unnecessary rather than inventing an approval feature.

## 98. Test end-to-end registration and sign-in
Goal: Prove a new student can enter the marketplace securely.
Description: Add an automated browser/API flow covering university registration, mocked SMTP delivery, verification, login, refresh, and logout. Assert that unverified or signed-out users cannot browse private listings.

## 99. Test end-to-end selling and discovery
Goal: Prove the primary buy/sell browsing flow works.
Description: Add a flow in which one verified student creates a listing with photos and another searches, filters, opens it, and follows an external contact link. Then mark the item sold and assert it disappears from public results but stays in the seller's dashboard.

## 100. Test end-to-end moderation and account controls
Goal: Prove reporting and security controls work together.
Description: Add a flow for submitting a listing report, reviewing it as an admin, removing the item, and suspending its owner. Confirm the owner cannot access protected endpoints and that a separate user can still use the marketplace.

## 101. Check keyboard access and responsive layouts
Goal: Make core student and admin screens usable on phones and with keyboards.
Description: Review forms, dialogs, listing cards, image gallery, and navigation at narrow and wide widths. Fix missing labels, focus behavior, keyboard interactions, and obvious contrast problems, and add targeted tests where practical.

## 102. Verify upload cleanup and deletion rules
Goal: Avoid orphaned images and unexpected data exposure.
Description: Test deleting listings, replacing avatars, deleting accounts, and removing listings as admin against the uploads directory and database references. Document any deliberate moderation/audit retention exception and verify that ordinary users cannot retrieve retained private records.

## 103. Prepare a repeatable local demo
Goal: Run the complete MVP locally from documented steps.
Description: Write a concise checklist to start PostgreSQL, FastAPI, and React, configure SMTP securely, apply migrations, and create a test admin and verified student accounts. Test the instructions from a clean setup and include a manual walkthrough of registration, listing, discovery, reporting, and moderation.
