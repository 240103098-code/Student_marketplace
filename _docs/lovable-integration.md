# Lovable integration: visual foundation (#45)

Source: https://github.com/240103098-code/sdu-student-marketplace at **07305f1f4007f1b8de852db3cb707d085e9f6caf**. The user explicitly authorized reuse of their source project. No repository LICENSE file exists; this records user-authorized provenance, not an invented open-source license. No credentials, sample marketplace records/images, localStorage session implementation, telemetry/error reporting or source provider/backend were imported.

## Actual source inspection before adaptation

On 2026-10-20 local time, installed the committed bun.lock with **Bun 1.3.13 --frozen-lockfile**, then ran the unchanged source with Node24.19.0 and Vite8.1.5:

```
bun install --frozen-lockfile
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5178 --strictPort
```

The workspace used the actual downloaded Windows x64 baseline Bun executable because npm's uninitialized bun.exe shim failed before execution. The frozen install succeeded (516 packages); no target dependency was added. Vite regenerated its routeTree line endings; after stopping the owned source server, that generated file was restored to its original committed content. Source Git is clean and no source commits/pushes were made. Normal operators can use a compatible installed Bun version with the same frozen command. Source fonts are Figtree/Outfit; its initial session hydration may briefly show only the wordmark before navigation appears.

Viewed real Edge155.0.4283.45 browser rendering at desktop1280×900 and mobile390×844, including opened drawer. [Source desktop](evidence/lovable-shell/source-desktop.png), [source mobile](evidence/lovable-shell/source-mobile.png), [source drawer](evidence/lovable-shell/source-mobile-menu.png). The source /marketplace and most feature routes are explicitly “This screen isn't built yet” empty screens; its home is also a blank-app placeholder. Its README is not evidence of implemented backend workflows.

## Adaptation and retained architecture

Adapted source src/styles.css palette/radius/shadow/typographic hierarchy, src/components/site-header.tsx wordmark/compact responsive navigation/drawer concept and src/components/common.tsx surface/feedback/status styling into target frontend/src/styles.css and SiteHeader.jsx. App.jsx delegates header rendering but retains its existing history router, protected-route whitelist, heading focus and honest logout behavior. No source assets were copied. The target uses a local system sans-serif stack rather than introducing remotely fetched Google fonts; weight/spacing/hierarchy approximate the source without an external font dependency.

Warm paper and white bordered surfaces, dark ink/deep teal, rounded cards and restrained semantic colors are reusable CSS primitives documented in design-system.md. The target keeps existing real forms/cards, rather than substituting source placeholders. The mobile drawer uses plain React/CSS with accessible name, expanded/controls state, scroll lock, focus trap, Escape/backdrop/close dismissal and trigger focus return. Route changes close it and retain normal page-heading focus. All working target routes remain available; a wider1100px breakpoint accommodates the target's additional security/account navigation. Source TanStack Start/server/Radix/lucide inventory was not transplanted.

Current server-confirmed auth/admin capabilities alone determine protected links. FastAPI remains the default API; Auth.jsx/api.js, CSRF/single-flight refresh, memory-only tokens and private-image fetching are unchanged. Failed logout remains an honest error with retry; mobile displays that feedback inside the open drawer. No SQLite/provider switch or development mock mode was introduced.

## Target reproduction and scope

Follow local-setup.md for pinned target install and actual backend. For a shell-only comparison run `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5179 --strictPort` from target frontend. [Target desktop](evidence/lovable-shell/target-desktop.png), [target mobile](evidence/lovable-shell/target-mobile.png), [target drawer](evidence/lovable-shell/target-mobile-menu.png) use actual API mode with no backend running, so existing session-unavailable guidance is visible rather than fabricated auth. No response mocks or source records were used for this reference comparison. Browser checks verified Escape focus return, actual Register navigation, drawer closure and no390px horizontal overflow. Unit tests additionally cover focus trapping, capability states, pending logout and dismissal; existing auth tests cover failed logout and session behavior.

This completes the shared shell foundation only. Keep the original forty tasks/history unchanged; the separate integration sequence is **#45 → #41 student screens → #42 admin screens → #43 explicit development mock/contract completion and final real-stack verification**. **#44 SQLite assessment is deferred**, outside frontend integration. Independent QA verifies each package; orchestrator publishes the exact approved commit, then independent QA confirms publication and closes it. Engineer never closes.

Verification: 146 frontend tests/build and 257 actual-PostgreSQL backend tests (zero skips) passed; see [record](evidence/lovable-shell/verification.txt). Owned source/target Vite and PostgreSQL services were stopped. No target dependencies changed.


## Student route adaptation (#41)

The published shell foundation is now applied to existing student screens; source placeholders were not copied. Shared FormIntro markup and scoped CSS style auth/recovery/verification, profile/avatar/contacts, password/deletion, marketplace filters/cards, detail/gallery/contact/report, create/edit and My Listings states/actions. No auth/API/business logic, backend, schema, provider, source files or dependencies changed. [Student coverage and real-stack evidence](student-screens.md) records the screen map and deliberate card/gallery/destructive-boundary adaptations. Admin visuals (#42) and explicit mock/contract/final integration (#43) are still follow-ups; SQLite (#44) stays deferred.

## Admin route adaptation (#42)

The shared foundation now styles actual admin overview/navigation, users, listing review/private gallery/publication/removal and reports. Responsive cards and distinct confirmation boundaries preserve fresh server authority, real data, safe pending/error states and all existing contracts. [Coverage and real-stack evidence](admin-screens.md) records desktop/mobile checks. No source placeholders, data, auth, dependencies or backend changes were imported. #43 remains the explicit mock/contract/final integration follow-up; #44 stays deferred.
