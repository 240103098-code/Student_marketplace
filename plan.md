# Student Marketplace — Project Requirements

**Project:** Student Marketplace  
**Status:** Requirements gathering in progress  
**Last recorded decision:** Question 40 — Item condition options  
**Next open decision:** Question 41 — Listing approval workflow  

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
| Authentication | Email/password with university-email verification; JWT access and refresh tokens |
| Image storage | Uploaded files in the backend's **`uploads/`** directory; database stores file paths |
| Development / demo | Run React, FastAPI, and PostgreSQL **locally** |

Backend modules / routers should cover **authentication, listings, users, and administration**, with shared services and database access. Store environment-specific configuration and secrets in environment variables (not source code).

## 3. Registration, login, and account security

### Registration

1. User signs up with their **university email** and password.
2. Backend checks that the email matches **one approved university domain**, defined in configuration.
3. Backend sends a **real verification email** using SMTP or an email provider.
4. User enters the verification code to activate their account.
5. User may enter a code incorrectly **up to five times**. After five incorrect attempts, the user must request a **new code**.
6. Only verified users may browse or use the marketplace.

**Email delivery decision:** real outgoing verification email, not terminal-only demo codes. SMTP / provider credentials must be configured securely via environment variables. No specific provider has yet been chosen.

**Not yet specified:** verification code length, code expiry time, resend cooldown, mail provider, and detailed abuse controls.

### Sessions

- Use **JWT access tokens** and **refresh tokens**.
- Refresh token handling should be secure, with support for **rotation and revocation**.
- Exact token lifetimes, storage/transmission strategy, and logout implementation are technical-design details yet to be finalized.

### Password management

- Authenticated users can **change their password**.
- Users who forget their password can **reset it via a code sent to their university email**.

### Account deletion

- Users can **permanently delete their own accounts**.
- Their listings and personal information are also deleted, apart from records that must be retained for security or legal reasons.
- Retention exceptions, if any, require a clear policy during implementation.

## 4. User profiles

Each user has a **basic profile**:

- Name
- Optional profile photo
- Contact details, such as phone number, Telegram username, or another contact method
- Verified university email (used for account identity)

Users may edit their **name, profile photo, and contact details**. The verified university email **cannot be changed**.

## 5. Listings

### Create a listing

Sellers can create listings with the following fields:

| Field | Requirement |
| --- | --- |
| Title | Required listing title |
| Description | Item description |
| Price | Asking price |
| Category | Choose from a **fixed predefined list** |
| Condition | Choose **New** or **Used** |
| Photos | Upload **up to 5 images** |

The **first uploaded image** is displayed as the listing's main photo.

### Categories

Use a predefined set of categories; examples agreed upon include:

- Electronics
- Clothing
- Books
- Furniture
- Other

**Note:** This is an example set, not yet a finalized exhaustive list.

### Item conditions

Only two options:

- **New** — unused item.
- **Used** — previously owned or used item.

Condition is also available as a browse filter.

### Editing a published listing

Sellers may edit **only**:

- Price
- Description

They **cannot edit title, photos, category, or condition** after publishing. To change those, they must delete the listing and create a new one.

> This limited-editing decision supersedes an earlier general idea that listings would be editable without specifying restrictions.

### Listing status and lifecycle

- **Active:** visible to verified marketplace users.
- **Sold:** seller marks the item as sold; it disappears from public search and browsing but remains stored in the seller's account.
- **Deleted:** seller removes the listing.
- **No automatic expiration:** listings remain active until marked sold or deleted.
- **No temporary hiding/pause feature:** there is no separate Hidden status.

### My Listings dashboard

Sellers have a dedicated **My Listings** page where they can:

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
- Remove inappropriate listings
- Suspend user accounts
- Review user-submitted listing reports

### Reporting flow

- Verified users can **report a listing**.
- They select a **reason** (for example, spam, prohibited items, or misleading information).
- Admins review reports in the admin panel and may take action, including removing listings.

This is a **simple reporting system**. The MVP does not require an advanced report-status tracking system for reporters or long-form evidence submissions.

### Publication approval — **NOT DECIDED**

Question 41 was asked but not yet answered:

- **A. Automatic publishing:** listings become visible immediately; admins act on reports afterward.
- **B. Manual approval:** every listing needs admin approval before becoming visible.
- **C. Hybrid:** listings appear immediately, but suspicious ones are flagged for review.

**Current status:** Awaiting a decision. The earlier recommendation was **A**, but it has **not been selected** by the user.

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
- [ ] Implement chosen listing-publication approval policy (**open decision**)

### Technical

- [ ] Set up React frontend
- [ ] Set up modular FastAPI backend
- [ ] Set up PostgreSQL, SQLAlchemy, and Alembic
- [ ] Configure one approved university email domain
- [ ] Set up SMTP / real-email provider
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

## 11. Outstanding details / implementation decisions

The following have **not** been fully specified and should not be treated as selected requirements:

1. **Question 41:** auto-publish, manual approval, or hybrid moderation.
2. Exact university email domain.
3. Final full category list.
4. SMTP/email provider, verification-code expiry, resend cooldown, and code length.
5. JWT lifetimes and exact secure refresh-token storage approach.
6. Photo file types, individual size limits, and image validation.
7. Whether any listing fields besides title are mandatory and their input validation rules.
8. Admin assignment / creation process and exact admin permissions.
9. Precise deletion and security/audit data-retention rules.
10. Automated tests and production deployment approach (if/when needed).

---

## 12. Decision history (questions 1–40)

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
| Session mechanism | JWT access + refresh tokens |
| **Q26: Verification delivery** | **Real emails via SMTP or provider** |
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
| **Q41: Approval** | **Not yet answered** |

*This document distinguishes confirmed choices from recommendations and unresolved technical details.*
