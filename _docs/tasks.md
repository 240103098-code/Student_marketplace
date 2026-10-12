## 1. Set up an empty project with a passing automated test
Goal: Create the smallest runnable project and prove its test runner works.
Description: Create an empty project skeleton without marketplace features. Add one automated smoke test and document the command that makes it pass.

## 2. Record the remaining MVP decisions
Goal: Document the values and policies needed before dependent features begin.
Description: Confirm the university domain, categories, field limits, email settings, token settings, image limits, admin provisioning, and deletion retention rules. Record the user's publication-policy choice without assuming automatic, manual, or hybrid approval.

## 3. Add local configuration
Goal: Load development settings without committing secrets.
Description: Add environment-based settings and an example configuration for FastAPI, PostgreSQL, email delivery, JWT, and uploads. Validate missing required settings and document the local configuration steps.

## 4. Connect PostgreSQL and migrations
Goal: Make the backend database connection and first migration repeatable.
Description: Configure SQLAlchemy sessions and Alembic against local PostgreSQL. Add a database connection check and document applying and reverting the initial migration.

## 5. Create the React application shell
Goal: Provide a minimal frontend with navigation and a passing test.
Description: Set up React with routes for authentication and the marketplace. Add a simple component test and use the agreed white, neutral, minimal visual style.

## 6. Create account and session tables
Goal: Store accounts, email codes, and revocable refresh sessions.
Description: Add SQLAlchemy models and migrations for user identity, verification state, suspension, roles, codes, and refresh sessions. Include uniqueness and expiry fields needed by authentication without adding listing tables.

## 7. Register university students
Goal: Accept registration only for the approved university email domain.
Description: Add a registration endpoint with normalized university-email validation and secure password hashing. Cover invalid domains, malformed input, and duplicate addresses with focused tests.

## 8. Send real verification emails
Goal: Deliver university verification codes through configured email delivery.
Description: Connect the selected SMTP service or email provider and send registration codes using a reusable email service. Keep credentials in environment variables and test delivery errors without exposing codes or secrets in logs.

## 9. Verify and resend email codes
Goal: Activate students securely with at most five wrong attempts per code.
Description: Add verification and resend endpoints using the agreed code lifetime and resend cooldown. Invalidate a code after five incorrect attempts and test expiry, reuse, and replacement codes.

## 10. Add login and access-token authorization
Goal: Allow only eligible verified accounts to access protected endpoints.
Description: Add password login, JWT access-token issuance, and a shared verified-user dependency. Test invalid credentials, unverified accounts, suspended accounts, and expired or malformed tokens.

## 11. Rotate refresh tokens and support logout
Goal: Keep sessions renewable and explicitly revocable.
Description: Add refresh-token rotation and logout using stored sessions and the agreed secure token transport. Reject revoked or reused refresh tokens and cover the rotation and revocation rules with tests.

## 12. Build registration and verification screens
Goal: Let a student register and verify their university email.
Description: Create React registration and code-verification forms connected to the existing authentication endpoints. Show validation, resend cooldown, expired-code, and exhausted-attempt messages.

## 13. Build login and protected navigation
Goal: Let verified students sign in and stay signed in safely.
Description: Add the login form, shared authenticated API handling, and protected React routes. Handle token refresh and logout while returning unauthenticated or suspended users to an appropriate screen.

## 14. Add password changes
Goal: Let signed-in students change their own password.
Description: Add a password-change endpoint and a small account form requiring the current password. Apply the agreed password rules and revoke sessions as required by the session policy.

## 15. Add forgotten-password recovery
Goal: Let students reset passwords through real university email codes.
Description: Add code-based recovery endpoints and a simple reset form using the existing email and code services. Enforce expiry and attempt limits, avoid account enumeration, and revoke old sessions after a successful reset.

## 16. Add profile read and edit endpoints
Goal: Let students update their basic profile while keeping email fixed.
Description: Add authenticated endpoints for name and external contact details. Validate supported contact values and reject attempts to change the verified university email.

## 17. Build the profile screen
Goal: Let students view and edit their own name and contact details.
Description: Create a React profile form connected to the profile endpoints. Display the verified email as read-only and show clear saving and validation feedback.

## 18. Add optional profile photos
Goal: Let students upload or remove a safe profile image.
Description: Add validated avatar upload and removal with files stored under the backend uploads directory and paths stored in PostgreSQL. Connect a small photo control to the profile screen and reject invalid file types or oversized files.

## 19. Create listing and report tables
Goal: Store listing data, ordered image paths, categories, and reports.
Description: Add models and migrations for listings, predefined categories, ordered photos, and reason-based reports. Represent active and sold lifecycle states and any additional state required by the explicitly chosen publication policy.

## 20. Create listings through the API
Goal: Let verified students submit validated listing fields.
Description: Add an endpoint for title, description, price, category, and New or Used condition using the agreed field rules. Assign ownership and apply the chosen publication policy while testing invalid input and unauthorized creation.

## 21. Upload listing photos
Goal: Store up to five safe photos for each listing.
Description: Add owner-authorized listing photo upload with validated types, sizes, and safe generated filenames in uploads. Store ordered paths in PostgreSQL, use the first uploaded image as the main photo, and protect image access from unverified users.

## 22. Build the new-listing form
Goal: Let students submit a listing and up to five photos.
Description: Create a React form for the agreed listing fields and ordered photo selection using the existing endpoints. Show upload errors and the actual publication outcome required by the chosen policy.

## 23. Edit listing price and description
Goal: Let sellers change only the permitted fields after publication.
Description: Add an owner-authorized update endpoint and a small editing form for price and description. Reject title, category, condition, or photo changes after publication and test another student's update attempt.

## 24. Build My Listings
Goal: Let sellers view their own active and sold listings.
Description: Add an authenticated endpoint for a student's own listings and a React dashboard with active and sold sections. Include any policy-specific unpublished state only if the selected approval workflow requires it.

## 25. Mark a listing as sold
Goal: Let sellers remove sold items from marketplace discovery.
Description: Add an owner-authorized sold action and connect it to My Listings. Keep sold items in the seller dashboard while excluding them from marketplace browsing and search.

## 26. Delete an owned listing
Goal: Let sellers remove a listing and its uploaded photos.
Description: Add an owner-authorized deletion endpoint and a confirmation action in My Listings. Remove the associated photo files and test that other students cannot delete the listing.

## 27. Add protected marketplace browsing
Goal: Return visible active listings newest first.
Description: Add a verified-user listing feed with bounded pagination and descending publication-date order. Exclude sold, removed, and policy-ineligible listings, and test access by anonymous or unverified users.

## 28. Add keyword search
Goal: Let verified students search listing text.
Description: Add a keyword parameter to the marketplace endpoint using parameterized database queries. Cover matching text, blank input, and no results without adding relevance or user-selectable sorting.

## 29. Add category, price, and condition filters
Goal: Let students narrow discovery using the agreed MVP filters.
Description: Extend the marketplace endpoint with category, minimum and maximum price, and New or Used filters. Allow filters to combine with keyword search and reject invalid ranges or unknown values.

## 30. Build the marketplace homepage
Goal: Show search, category navigation, filters, and recent listing cards.
Description: Create a responsive React homepage connected to the existing discovery endpoint. Display main photos and prices with loading, empty, error, and pagination states.

## 31. Build listing details and external contact
Goal: Let verified buyers inspect an item and contact its seller externally.
Description: Add a protected listing-detail endpoint and a React detail screen with its photo gallery and seller contact details. Provide validated external contact links when available and keep payments, chat, and pickup outside the application.

## 32. Let students report listings
Goal: Collect a simple reason-based report for admin review.
Description: Add a verified-user reporting endpoint and a reason selector on the listing detail screen. Validate report reasons and show submission feedback without building advanced reporter status tracking.

## 33. Add admin access and navigation
Goal: Restrict administration to explicitly provisioned admins.
Description: Implement the agreed local admin-provisioning method and a shared admin authorization dependency. Add protected admin navigation and test access rejection for ordinary, unverified, and suspended accounts.

## 34. Build admin user review and suspension
Goal: Let admins view users and suspend an account.
Description: Add a paginated admin user endpoint and a simple user-management screen with suspension confirmation. Enforce suspension on existing sessions and protected requests and test ordinary-user rejection.

## 35. Build admin listing review and removal
Goal: Let admins inspect listings and remove inappropriate content.
Description: Add admin listing-list and removal endpoints with a simple management screen. Remove affected listings from discovery, handle associated images consistently, and test admin-only access.

## 36. Build the admin report queue
Goal: Let admins review reason-based listing reports.
Description: Add a paginated report endpoint and a basic report screen linking to the reported listing. Reuse the existing listing-removal action and provide a simple way to mark a reviewed report as handled.

## 37. Complete the chosen publication workflow
Goal: Make publication behavior match the user's recorded policy.
Description: Review creation, visibility, and admin controls against the policy recorded in task 2 and implement only missing policy-specific behavior. Add focused tests for the selected workflow without introducing unrequested approval steps.

## 38. Add permanent account deletion
Goal: Let students permanently remove their account and owned content.
Description: Add an authenticated deletion endpoint and a confirmation control on the account screen. Remove owned listings, images, personal data, and sessions according to the documented retention policy.

## 39. Check security boundaries and abuse controls
Goal: Close gaps in authorization, safe uploads, and sensitive endpoints.
Description: Run a focused security review of ownership checks, private image access, external links, secret handling, CORS, and cookie or CSRF requirements. Add the agreed limits to registration, login, code requests, and recovery and regression-test any identified gaps.

## 40. Verify and document the local MVP demo
Goal: Prove the main student and admin journeys work locally.
Description: Add a small automated smoke suite covering verified access, listing creation, discovery, external contact, reporting, and admin action using reusable fixtures. Document running React, FastAPI, PostgreSQL, migrations, email configuration, and the tests for a repeatable local demonstration.
