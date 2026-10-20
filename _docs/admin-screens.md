# Admin screen adaptation (#42)

Historical #42 screen/evidence snapshot from 2026-10-20; its counts describe that commit. Current storage/setup and newer tests are indexed in [documentation](index.md) and [iterations](iterations.md).

Uses the user-owned Lovable reference and the shared paper/white/ink/teal foundation from #45/#41. Provenance, source commit and license observations remain in [lovable-integration.md](lovable-integration.md). Source feature placeholders were not copied.

## Working screen coverage

| Route | Presentation and retained behavior |
| --- | --- |
| /admin | Server-confirmed navigation and three real review shortcuts. Loading, denied access and retry remain authoritative. |
| /admin/users | Responsive identity cards, eligibility/status text, bounded pagination and distinct protected administrator notice. Suspension/unsuspension confirmation, pending protection, fresh guards, safe failures and authoritative reload are preserved. Cancel returns keyboard focus to its action. |
| /admin/listings | Real all-state/status filtering, counts, pagination and readable review links. No fabricated queue entries. |
| /admin/listings/:id | White metadata overview, private contained gallery and separate Pending publication/removal cards. Reason guidance, approval/rejection confirmations, Removed retention and current permissions are unchanged. Removal cancel restores action focus. |
| /admin/reports | Readable reason/listing/time/status cards, real filters/paging and primary review action. Review stays independent of listing removal; first-review and reconciliation logic are preserved. |

Admin-only CSS provides wrapped navigation/actions, bounded cards, readable long identities and a single-column layout at390px. Status is always written as text; color is supporting information. Existing labels, live feedback, visible focus and keyboard controls remain. No backend, schema, dependency, API/auth helper, mutation replay, private-image contract or business-rule changes were made. No source mock data/auth or dead buttons were introduced.

## Verification and evidence

Frontend: **149 interaction tests passed**, including new confirmation autofocus/cancel restoration checks; production build passed. Backend: **257 tests with real PostgreSQL, zero skips**. Existing tests continue to cover paging/filtering, protected targets, private-photo cleanup, stale responses, demotion/expiry, malformed responses, ambiguous mutations, publication decisions and report reconciliation.

The documented `python -m tools.local_demo` command ran fresh PostgreSQL migrations, real production React/FastAPI, controlled protocol SMTP and Edge. It passed the complete real journey, including Pending invisibility, admin approval, buyer search/filter/detail/contact/report, admin report review/removal, rejection, suspension, Sold/delete and account cleanup. [Result](evidence/admin-screens/smoke-result.json): **107 real API responses**, cleanup complete. Screenshot-only hooks additionally exercised keyboard confirmation/cancel focus, gallery selection and desktop/mobile overflow assertions; the tracked runner and earlier generated demo outputs were restored afterward.

Viewed evidence at desktop1280×900/mobile390×844: [overview](evidence/admin-screens/overview-desktop.png), [users desktop](evidence/admin-screens/users-desktop.png), [users mobile](evidence/admin-screens/users-mobile.png), [suspension confirmation](evidence/admin-screens/users-confirm-mobile.png), [Pending desktop](evidence/admin-screens/pending-desktop.png), [Pending mobile](evidence/admin-screens/pending-mobile.png), [rejection form](evidence/admin-screens/rejection-mobile.png), [reports desktop](evidence/admin-screens/reports-desktop.png), [reports mobile](evidence/admin-screens/reports-mobile.png). Identities are grey-masked; content is synthetic. No passwords, codes, tokens or private emails are captured.

External SMTP inbox delivery and production deployment remain unverified. The later #43 mock/contract integration and #44 durable SQLite are now implemented; the final comprehensive matrix remains #53. The forty-task backlog and history are preserved.
