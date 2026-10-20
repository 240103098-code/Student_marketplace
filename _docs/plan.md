# Student Marketplace — Project Requirements

**Project:** Student Marketplace
**Status:** MVP decision baseline recorded; implementation in progress
**Last recorded decision:** 2026-10-12 — university domain and manual approval confirmed; implementation defaults authorized
**Remaining setup:** Deployment-specific SMTP credentials and local service configuration

## 1. Project overview

Student Marketplace is a **web application for students at one university to buy and sell items**. Only students who have registered and verified an email address from the university's approved domain may access the marketplace.

The platform facilitates discovery and contact rather than transactions: sellers publish listings, buyers browse listings and contact sellers through external channels, and the parties arrange payment and handover independently.

### Core principles

- Target users: **students of one university**.
- Eligible items: **almost any legal item**, subject to platform rules and moderation.
- Access: **verified students only**; unverified visitors cannot browse listings or see seller contact details.
- Payments and pickup: **outside the platform**, arranged directly between buyer and seller.
- Initial scope: **MVP**, built and demonstrated locally before any online deployment.

## 2. Tech stack and architecture

| Layer | Decision |
| --- | --- |
| Frontend | **React** |
| Backend | **Python FastAPI** |
| Database | **PostgreSQL** |
| ORM | **SQLAlchemy** |
| Database migrations | **Alembic** |
| Architecture | **Modular FastAPI monolith** |
| Authentication | Email/password with university-email verification; JWT access tokens and opaque refresh sessions |
| Image storage | Uploaded files in the backend's **`uploads/`** directory; database stores file paths |
| Development / demo | Run React, FastAPI, and PostgreSQL **locally** |

Backend modules / routers should cover **authentication, listings, users, and administration**, with shared services and database access. Store environment-specific configuration and secrets in environment variables (not source code).

## 3. Registration, login, and account security

### Registration

1. User signs up with their **university email** and password.
2. Backend checks that the email matches exactly **sdu.edu.kz**, defined in configuration (subdomains are not eligible).
3. Backend sends a **real verification email** using configurable SMTP.
4. User enters the verification code to activate their account.
5. User may enter a code incorrectly **up to five times**. After five incorrect attempts, the user must request a **new code**.
6. Only verified users may browse or use the marketplace.

**Email delivery default:** configurable real SMTP with TLS/STARTTLS appropriate to the server. Hostname, port, sender, and credentials are external operational configuration; no SMTP account or live credentials are claimed to exist. Console-only code delivery does not satisfy the feature.

### Email codes and passwords — authorized implementation defaults

- Cryptographically generated six-digit codes last ten minutes, with a sixty-second resend cooldown and at most five wrong attempts per code.
- Replacement invalidates the previous code. Store codes hashed and separate registration and password-reset purposes.
- Passwords accept 12–128 characters, have no forced composition rule, and use Argon2id hashing.

### Sessions — authorized implementation defaults

- JWT access tokens last fifteen minutes; keep them in browser memory and transmit them in Authorization Bearer headers.
- Opaque refresh sessions last seven days from login, rotate on each use, and revoke the token family on detected reuse. Store tokens hashed server-side; use HttpOnly SameSite=Lax cookies, with Secure required outside local HTTP development.
- Logout, password reset/change, suspension, and account deletion revoke refresh sessions. Suspension also blocks new logins and existing protected requests.

### Browser security — authorized implementation defaults

- Allow only configured frontend origins with credentials; never use wildcard credentialed CORS.
- Cookie-authenticated mutation endpoints require a matching allowed Origin and a CSRF token. Read-only GET requests never mutate state.
- Exclude passwords, raw codes, tokens, and secrets from logs and committed files.

### Abuse controls — authorized implementation defaults

- Registration: ten attempts per IP per hour.
- Login: ten failures per normalized email/IP pair per fifteen minutes.
- Verification/password-reset code submissions: five failures per code.
- Email-send requests: five per email per hour plus the sixty-second cooldown.
- Recovery initiation: ten requests per IP per hour.
- Limits return retry guidance without revealing account existence; recovery responses remain generic.

### Password management

- Authenticated users can **change their password**.
- Users who forget their password can **reset it via a code sent to their university email**.

### Account deletion

- Users can **permanently delete their own accounts**.
- Authorized deletion default: remove identity, contacts, avatar, listings, listing photos, codes, sessions, and reports involving the deleted identity or listings. No personal-data retention exception is adopted for this local MVP.

## 4. User profiles

Each user has a **basic profile**:

- Name
- Optional profile photo
- Contact details, such as phone number, Telegram username, or another contact method
- Verified university email (used for account identity)

Users may edit their **name, profile photo, and contact details**. The verified university email **cannot be changed** and never becomes a public contact field.

Authorized defaults: trimmed name is required and 1–100 characters. Contact fields are optional: phone up to 30 characters; Telegram username 5–32 letters, digits, or underscores; HTTPS external contact URL up to 2048 characters. At least one valid contact method must exist before listing submission.

## 5. Listings

### Create a listing

Sellers can create listings with the following fields:

| Field | Requirement |
| --- | --- |
| Title | Required, 3–120 characters |
| Description | Required, 10–2000 characters |
| Price | Required, nonnegative, up to 1,000,000,000 KZT with at most two decimal places |
| Category | Required choice from the fixed predefined list |
| Condition | Required **New** or **Used** |
| Photos | Optional, zero to five images |

The **first uploaded image** is displayed as the listing's main photo.

### Categories

Authorized implementation defaults use currency **KZT** and this complete category set:

- Electronics
- Clothing
- Books
- Furniture
- Other

These limits, categories, currency, and contact rules are implementation defaults adopted under the user's authorization, not individually selected user decisions.

### Images — authorized implementation defaults

Avatar and listing uploads accept JPEG, PNG, and WebP only, with a maximum five MiB per file and twenty megapixels. Validate decoded image content, reject SVG and unsupported content, and generate safe filenames. Store files beneath backend `uploads/` and paths in PostgreSQL; preserve listing photo order with the first uploaded image as main photo. Image access requires verified authorization.

### Item conditions

Only two options:

- **New** — unused item.
- **Used** — previously owned or used item.

Condition is also available as a browse filter.

### Editing a published listing

Sellers may edit **only**:

- Price
- Description

Price/description edits retain the existing approval. They **cannot edit title, photos, category, or condition** after publishing. To change those, they must delete the listing and create a new one.

> This limited-editing decision supersedes an earlier general idea that listings would be editable without specifying restrictions.

### Listing status and lifecycle

- **Pending:** every newly submitted listing is private to its seller and admins until manual admin approval.
- **Active:** approved listings are visible to verified marketplace users; approval sets the publication date.
- **Rejected:** private to the seller and admins with a short rejection reason; sellers delete and recreate rather than edit immutable fields.
- **Sold:** seller marks the item as sold; it disappears from public search and browsing but remains stored in the seller's account.
- **Deleted:** seller removes the listing.
- **No automatic expiration:** listings remain active until marked sold or deleted.
- **No temporary hiding/pause feature:** there is no separate Hidden status.

### My Listings dashboard

Sellers have a dedicated **My Listings** page where they can:

- View pending and rejected listings with rejection reasons
- View active listings
- View sold listings
- Edit permitted fields (price and description)
- Mark an active listing as sold
- Delete listings

## 6. Browsing, search, and discovery

### Homepage

The homepage has a **modern, minimal layout**, including:

- Keyword search bar
- Category navigation
- Grid of recent listing cards showing **photos and prices**

Visual direction: **white backgrounds, neutral colors, simple cards, subtle accents**.

### Search and filters

Verified users can:

- Search by **keywords**
- Browse by **category**
- Filter by **price range**
- Filter by **condition** (New / Used)

### Ordering

- Listings are sorted by **newest first** (publication date descending).
- The MVP will **not** offer user-selectable sorting by price, oldest first, popularity, or relevance.

### Not included

- **No favorites / saved-listings feature**.
- **No automatic listing expiration**.

## 7. Buyer–seller contact and transactions

The platform does **not** include an internal messaging/chat system.

For an active listing, verified buyers can:

- View seller **contact information**.
- Use a **Contact Seller** button to open the seller's preferred external messaging app (for example, Telegram or WhatsApp), when a suitable link is available.

The buyer and seller arrange **payment, delivery/pickup, and any negotiation themselves**. No checkout, payment processing, order tracking, or built-in delivery workflow is part of the MVP.

## 8. Administration and reporting

### Basic admin panel

Admins can:

- View users
- View listings
- Approve or reject pending listings with a short rejection reason
- Remove inappropriate listings
- Suspend user accounts
- Review user-submitted listing reports

### Reporting flow

- Verified users can **report a listing**.
- They select a **reason** (for example, spam, prohibited items, or misleading information).
- Admins review reports in the admin panel and may take action, including removing listings.

This is a **simple reporting system**. The MVP does not require an advanced report-status tracking system for reporters or long-form evidence submissions.

### Publication approval — confirmed manual approval

The user explicitly selected mandatory manual admin approval before initial publication. New listings start Pending; only admins may approve them, setting their publication date. Only approved Active listings appear in student browsing and search. Rejected listings remain private to their seller and admins with a short rejection reason. Published price/description edits retain approval, and admin removal remains available.

Admin provisioning is an authorized implementation default: a local CLI promotes an existing verified account. There is no public role-assignment endpoint. Suspension blocks new logins and existing protected requests.

## 9. MVP feature checklist

### Student-facing

- [ ] Register with approved university email and password
- [ ] Receive real verification code by email
- [ ] Verify account (maximum 5 incorrect attempts per code)
- [ ] Log in and stay signed in using access/refresh tokens
- [ ] Change password
- [ ] Reset forgotten password via university email
- [ ] View and edit basic profile and contact information
- [ ] Permanently delete own account
- [ ] Browse the marketplace after verification
- [ ] Search by keyword
- [ ] Browse by predefined category
- [ ] Filter by price range and New/Used condition
- [ ] View listings newest first
- [ ] View listing details and seller contact methods
- [ ] Open external messaging app with Contact Seller button
- [ ] Create listing with up to five photos
- [ ] Edit listing price and description only
- [ ] View active and sold listings in My Listings
- [ ] Mark item sold
- [ ] Delete own listing
- [ ] Report inappropriate listing using a reason

### Admin-facing

- [ ] View users and listings
- [ ] Review listing reports
- [ ] Remove inappropriate listings
- [ ] Suspend accounts
- [ ] Approve/reject pending listings before initial publication

### Technical

- [ ] Set up React frontend
- [ ] Set up modular FastAPI backend
- [ ] Set up PostgreSQL, SQLAlchemy, and Alembic
- [ ] Configure exactly sdu.edu.kz without subdomains
- [ ] Set up configurable real SMTP with TLS/STARTTLS
- [ ] Implement JWT access + refresh tokens with secure rotation/revocation
- [ ] Store uploaded photos in backend `uploads/` and paths in PostgreSQL
- [ ] Run frontend, backend, and database locally

## 10. Explicitly excluded from the MVP

- Built-in chat or direct messages
- In-platform payments or checkout
- In-platform shipping, delivery, or pickup coordination
- Favorites, bookmarks, or saved-listing collections
- Temporary hiding / pausing listings
- Automatic listing expiration or renewal workflow
- User-selectable sorting options beyond newest first
- Public or anonymous marketplace browsing
- Changing the account's verified university email
- Editing listing title, photos, category, or condition after publication
- Advanced report tracking and reporting against users (as opposed to listings)
- Online production deployment in the initial local demo

## 11. Decision baseline and remaining operational setup

The user explicitly selected **sdu.edu.kz** (no subdomains) and **mandatory manual admin approval**. All numerical validation, code, password, session, image, browser-security, contact, deletion, admin-provisioning, SMTP, and abuse-control rules above are user-authorized implementation defaults. They are active requirements; they are not individually selected historical user answers.

No MVP product-policy choice remains open in this baseline. SMTP hostname, port, sender, credentials, and local service configuration remain external operator setup. Do not fabricate or commit these values or claim that live infrastructure already exists. Production deployment remains excluded from the initial local MVP; relevant tasks will add implementation and automated verification.

---

## 12. Decision history (questions 1–41 and current baseline)

The requirements above consolidate earlier choices. The following maps the established choices into a compact record; the original question numbers for decisions **1–25** are not all available in this transcript, so they are recorded by topic rather than assigning possibly inaccurate numbers.

| Topic / question | Selected decision |
| --- | --- |
| Project | Student Marketplace for buying/selling items |
| User base | One university |
| Item scope | Almost any legal items |
| Payments/meetups | Arranged externally between users |
| University gate | University email verification |
| Core MVP | Listing CRUD, browsing/search/filtering, profiles |
| Chat | No in-app chat; contact externally |
| Profile | Basic name, optional photo, contact details |
| Listing data | Title, description, price, category, condition, photos |
| Sold listings | Hidden from public search; retained in seller's account |
| Discovery | Keywords, categories, price range, condition |
| Platform | Web app |
| Stack | React, FastAPI, PostgreSQL |
| Login | University email + password + verification code |
| Homepage | Search, categories, recent-listing photo/price grid |
| Images | Local backend uploads directory, DB paths |
| Seller management | Separate My Listings dashboard |
| Admin panel | View users/listings, remove listings, suspend accounts |
| Design | Modern minimal, white/neutral, subtle accents |
| Categories | Predefined fixed categories |
| Deployment | Local development/demo |
| Backend design | Modular monolith with routers |
| Approved email | One configurable domain |
| Database layer | SQLAlchemy + Alembic |
| Session mechanism | JWT access + opaque refresh sessions (current baseline) |
| **Q26: Verification delivery** | **Real emails; configurable SMTP selected in current baseline** |
| **Q27: Verification failures** | **5 attempts, then request a new code** |
| **Q28: Photo limit** | **Up to 5 per listing** |
| **Q29: Contact method** | **Display contact details + Contact Seller button** |
| **Q30: Reporting** | **Basic listing reports, admin review** |
| **Q31: Favorites** | **No favorites** |
| **Q32: Sorting** | **Newest first only** |
| **Q33: Expiration** | **Listings never expire automatically** |
| **Q34: Marketplace visibility** | **Verified students only** |
| **Q35: Profile editing** | **Name, photo, contacts editable; email fixed** |
| **Q36: Passwords** | **Change and email-based reset** |
| **Q37: Hide listing** | **No temporary hiding** |
| **Q38: Delete account** | **Permanent self-service deletion** |
| **Q39: Listing edits** | **Price and description only** |
| **Q40: Item condition** | **New / Used** |
| **Q41: Approval** | Previously unanswered; superseded on 2026-10-12 by mandatory manual admin approval |
| Current explicit domain choice | Exactly sdu.edu.kz, no subdomains |
| Current implementation baseline | Technical defaults above adopted under user authorization on 2026-10-12 |

*Earlier unanswered approval, category-example, token/code/image, and retention statements are superseded by the current baseline. SMTP credentials remain operational setup, not an unresolved product policy.*


## Forward storage iteration — issue #51

The historical PostgreSQL architecture above remains the established persistent implementation. An explicit development/test `sqlite+pysqlite:///:memory:` option now runs the same real FastAPI services with portable shared models, full-transaction serialization and per-app temporary images; no records or images survive normal shutdown. It is separate from frontend mock mode, rejects production and retains real SMTP/JWT/operator eligibility checks. See [memory-backend setup](memory-backend.md). Persistent/default SQLite and migration strategy remain the next iteration in issue #44; this addition does not rewrite the earlier decisions or claim PostgreSQL migrations execute on SQLite.
