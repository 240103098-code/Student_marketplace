# Student screen adaptation (#41)

Built on published shell foundation fe84d68d441c63631e09827e2fb246720a1884be and the user-owned Lovable source provenance in [lovable-integration.md](lovable-integration.md). Source feature routes are placeholders; this adapts the target's actual working forms and data rather than importing those empty pages or sample records.

## Coverage and deliberate presentation changes

| Working screens | Adaptation; behavior retained |
| --- | --- |
| Sign-in/register/verify/recovery/reset/password | Shared FormIntro heading/hints, compact white form and consistent spacing/focus/feedback. Generic errors, cooldown/429 guidance, password/code secrecy and session behavior are unchanged. |
| Profile/avatar/contact | Cohesive desktop sections/mobile stack, private photo/file empty states and readable verified read-only email. Changed-only saves remain separate from destructive confirmation. |
| Permanent account deletion | Clearly separated danger zone with explicit irreversible text and red action styling. Current-password confirmation/cancel, pending protection, server-confirmed clearing and uncertainty remain intact. |
| Marketplace | Balanced desktop filters/mobile stack, exact KZT price emphasis, bounded image-first cards, result counts/empty/error states and pagination. Search/filter requests, ordering and protected blob handling unchanged. |
| Detail/gallery/contact/report | White item overview, contained ordered gallery, desktop contact/report sidebar/mobile stack, pressed/focus styles. Safe external links and genuine report flow unchanged; no chat/payment actions added. |
| Create/photo progress/edit | Grouped item instructions, bounded read-only fields, ordered preview tiles and existing confirmed/partial/uncertain progress. No metadata/upload replay or editing-policy change. |
| My Listings | Real state text plus supporting Active/Sold/Pending/Rejected/Removed tones, clear moderation feedback and separated delete/Sold confirmations. Safe authoritative refresh and actual action contracts remain. |

All new feature CSS is scoped to .student-page. Admin feature design is untouched and remains #42. Shared router/Auth/api helpers and backend/schema/dependencies are unchanged. No source localStorage auth, mock accounts/tokens/records, Supabase/provider or fake button was introduced. Source remains read-only. Forty-task backlog/history are preserved.

## Actual browser and real-stack evidence

Executed the existing `python -m tools.local_demo` command with the documented fresh private PostgreSQL cluster, real production React/FastAPI and memory-only protocol SMTP. Temporary screenshot-only hooks visited empty auth forms and captured student stages; no API was intercepted or mocked. The runner and earlier generated #40 demo outputs were restored to their committed content afterward. The copied [smoke result](evidence/student-screens/smoke-result.json) records **PASS**, **113 actual API responses** and **cleanup complete**.

Desktop1280×900/mobile390×844 evidence: [auth desktop](evidence/student-screens/auth-desktop.png), [auth mobile](evidence/student-screens/auth-mobile.png), [catalog desktop](evidence/student-screens/catalog-desktop.png), [catalog mobile](evidence/student-screens/catalog-mobile.png), [detail desktop](evidence/student-screens/detail-desktop.png), [detail mobile](evidence/student-screens/detail-mobile.png), [profile desktop](evidence/student-screens/profile-desktop.png), [profile mobile](evidence/student-screens/profile-mobile.png), [create desktop](evidence/student-screens/create-desktop.png), [create mobile](evidence/student-screens/create-mobile.png), [My Listings mobile](evidence/student-screens/mine-mobile.png).

Screenshots use synthetic listing content only; profile email is grey-redacted and auth fields are empty. No password, code, token or private identity is captured. Capture scrolls to page top so a sticky header is not misleadingly frozen halfway through a full-page image. Representative captures were visually inspected for grouping, focus, wrapping and card width. Actual browser checks assert no390px horizontal overflow on every public auth form, profile/create/edit/My Listings/catalog/detail; existing smoke activates the gallery with keyboard and inspects contact hrefs without opening them. Manual approval/Pending invisibility, reporting/admin review/removal, rejection feedback, suspension denial, Sold/deletion and account cleanup still pass against the real stack.

The first visual review exposed a single-result card stretching across the desktop row. Auto-fill tracks now retain a normal card width; mobile remains one bounded column. No business/API defect was observed.

## Verification and remaining scope

Frontend command: `npm run test -- --run --maxWorkers=2` — **147 passed**, all21 files. A focused settings test verifies deletion cancellation leaves unsaved profile edits intact and sends no PATCH/DELETE, preserving independent form boundaries. All existing tests/assertions are retained. Two default highly parallel first-run cases hit their1000ms waits under CPU load; both passed in isolation and the complete two-worker run passed without increasing timeouts or skipping cases. `npm run build` passed with40 modules.

Backend command: `.venv/Scripts/python.exe -m unittest discover -s tests -v` with the existing guarded disposable PostgreSQL lifecycle — **257 passed, zero skips**. Real-stack smoke was repeated after visual refinements and passed. See [exact verification record](evidence/student-screens/verification.txt). Owned services stopped; disposable data removed; diff check passed.

The integration is not yet complete: admin screen adaptation (#42) and explicit development mock/contract completion with final integration verification (#43) remain. SQLite is deferred (#44). Local protocol SMTP does not prove real university-inbox delivery or production readiness; no external person/contact was messaged/opened.
