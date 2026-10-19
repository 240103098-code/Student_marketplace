# Student Marketplace

A university-only marketplace built with React, FastAPI and PostgreSQL. Students verify an exact `sdu.edu.kz` email address, create listings with private images, and contact sellers externally. New listings require manual admin approval before buyers can browse them.

Implemented: JWT access and rotating refresh sessions, password recovery/change, profiles/avatars, listing creation/editing/photos/Sold/deletion, search and filters, seller contact links, reports, current-role admin moderation, publication decisions, permanent account deletion and finite local abuse limits. There is no payment processing or built-in chat.

## Run and verify

Read the [fresh-checkout setup guide](_docs/local-setup.md) for pinned installation, configuration, migrations, startup and full checks. The [one-command real-stack demo](_docs/demo.md) creates its own disposable PostgreSQL cluster and uses real React/FastAPI plus controlled loopback SMTP; it never resets a supplied database.

Tested: Python 3.13.15, Node 24.19.0, npm 12.2.0, PostgreSQL 18.6, Playwright 1.62.1 and Edge 155.0.4283.45. Complete backend verification: 257 tests with real PostgreSQL; frontend: 147 interaction tests and production build. [Recorded demo evidence](_docs/evidence/demo-result.json) includes desktop/mobile screenshots and the real request count.

## Project documents

- [Established MVP requirements](_docs/plan.md)
- [Exactly 40 backlog tasks](_docs/tasks.md) and [preserved history](_docs/backlog-history.md)
- [Development and independent QA process](_docs/process.md)
- [API contracts](_docs/api.md)
- [Security boundaries and concrete verification matrix](_docs/security.md)
- [Demo walkthrough and requirement map](_docs/demo.md)

Track work in [this repository's GitHub issues](https://github.com/240103098-code/Student_marketplace/issues).

This is a local MVP, with no production deployment or distributed rate-limit guarantee. Controlled SMTP protocol success does **not** verify delivery to a real university inbox; external provider credentials and an intentional operator inbox check remain outstanding.

The user-owned Lovable visual foundation is being integrated in separate packages. [Source provenance, shell comparison and sequence](_docs/lovable-integration.md) document the shared shell (#45); student/admin screens and final mock/contract integration remain follow-up work.
