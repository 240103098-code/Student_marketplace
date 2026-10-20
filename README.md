# Student Marketplace

A university-only marketplace built with React, FastAPI and local SQLite (with explicit PostgreSQL compatibility). Students verify an exact `sdu.edu.kz` email address, create listings with private images, and contact sellers externally. New listings require manual admin approval before buyers can browse them.

Implemented: JWT access and rotating refresh sessions, password recovery/change, profiles/avatars, listing creation/editing/photos/Sold/deletion, search and filters, seller contact links, reports, current-role admin moderation, publication decisions, permanent account deletion and finite local abuse limits. There is no payment processing or built-in chat.

## Run and verify

Read the [fresh-checkout setup guide](_docs/local-setup.md) for pinned installation, configuration, migrations, startup and full checks. The [SQLite setup/restart smoke](_docs/sqlite-setup.md) needs no PostgreSQL server. The [one-command real-stack demo](_docs/demo.md) creates its own disposable PostgreSQL cluster and uses real React/FastAPI plus controlled loopback SMTP; it never resets a supplied database.

Tested: Python 3.13.15, Node 24.19.0, npm 12.2.0, PostgreSQL 18.6, Playwright 1.62.1 and Edge 155.0.4283.45. Backend suite: 292 tests spanning real PostgreSQL, volatile memory and persistent SQLite; [latest exact verification scopes](_docs/evidence/sqlite-persistence/verification.txt) distinguish the full run and focused corrections. Frontend: 157 interaction tests and production build. [Recorded demo evidence](_docs/evidence/demo-result.json) includes desktop/mobile screenshots and the real request count.

## Project documents

- [Established MVP requirements](_docs/plan.md)
- [Exactly 40 backlog tasks](_docs/tasks.md) and [preserved history](_docs/backlog-history.md)
- [Development and independent QA process](_docs/process.md)
- [API contracts](_docs/api.md)
- [Security boundaries and concrete verification matrix](_docs/security.md)
- [Demo walkthrough and requirement map](_docs/demo.md)

Track work in [this repository's GitHub issues](https://github.com/240103098-code/Student_marketplace/issues).

This is a local MVP, with no production deployment or distributed rate-limit guarantee. Controlled SMTP protocol success does **not** verify delivery to a real university inbox; external provider credentials and an intentional operator inbox check remain outstanding.

The user-owned Lovable design is adapted across the shared shell and working student/admin screens. [Final integration guide](_docs/integration-contracts.md) covers explicit frontend-only synthetic demo mode, typed contracts, OpenAPI export/check and real-mode verification. Real FastAPI remains the default; no automatic Lovable sync or provider switch is configured. [Durable local SQLite](_docs/sqlite-setup.md) is the fresh-development default; explicit PostgreSQL and [volatile FastAPI memory mode](_docs/memory-backend.md) remain available.

[Canonical API inventory and forward iterations](_docs/canonical-api-contract.md) describe the completed machine-readable contract and the memory and persistent SQLite iterations without rewriting earlier project history.
