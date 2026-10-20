# Public documentation index

Current as of **2026-10-20**, after canonical contract, memory and durable SQLite. These are public project documents; ignored environments, credentials, local operational notes, database files and whole chat/tool logs are not project documentation exports.

| Purpose | Documents and status |
| --- | --- |
| Start here / current requirements | [Repository README](../README.md), [plan](plan.md), [requirements/task/evidence map](requirements-map.md). Current local default is durable SQLite; PG/memory are explicit alternatives. |
| Current install/start/migrate/stop/check | [Local setup](local-setup.md), [SQLite default, backup/reset and restart smoke](sqlite-setup.md), [real volatile memory](memory-backend.md). PG alternative uses its original migration stream. |
| Current API/security and transport | [API](api.md), [canonical inventory](canonical-api-contract.md), [generated OpenAPI](../openapi.yml), [security](security.md), [real/mock integration guide](integration-contracts.md). Their historical verification subsections are labelled snapshots. |
| Current visuals / source attribution | [Design system](design-system.md), [Lovable source provenance](lovable-integration.md), [original mock photos/intentional price overrides](mock-original-photos.md). Source ownership/provenance is retained, no automatic sync or invented license. |
| Process and roles | [AGENTS](../AGENTS.md), [process](process.md), [task template](task-template.md), [testing guidelines](testing-guidelines.md), [PM](team/pm.md), [engineer](team/software-engineer.md), [QA](team/qa-engineer.md). |
| Authentic selected dialogue and actual order | [Brainstorm excerpts/coverage limits](brainstorm.md), [iteration log](iterations.md). Quotes and summaries are explicitly separate; unavailable original interview is not reconstructed. |
| Preserved backlog/history | [Exactly forty tasks](tasks.md), [import/consolidation history](backlog-history.md). Historical task technology/order is not silently rewritten to match later storage choices. |
| Historical demo/screen reports with usable scoped commands | [Original PostgreSQL real-stack demo](demo.md), [student screens](student-screens.md), [admin screens](admin-screens.md). Their earlier test counts describe their original commits, not today's suite size. |
| Immutable-style verification snapshots | Files under [evidence](evidence), including original PG demo, student/admin/integration contracts, original photos/price overrides, canonical contract, memory and SQLite snapshots. They keep the counts/results actually observed. Later QA comments can supplement them; they are not retroactively rewritten. |

Current baseline: 292 backend tests (full verification requires guarded real PostgreSQL **and** the memory/file suites),157 frontend tests, typecheck, real build/mock isolation and actual-app OpenAPI drift checks. See [iteration evidence](iterations.md) for the independent full-run result and [setup](local-setup.md) for reproduction. This index does not claim pending final cross-mode [#53](https://github.com/240103098-code/Student_marketplace/issues/53), live inbox delivery or production deployment is complete.
