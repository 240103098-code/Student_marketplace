# Shared visual foundation: Campus Paper (#110)

Campus Paper supersedes the earlier teal foundation. The accent is now saturated blue; no teal tokens or hue ~195 values remain. All values are CSS custom properties in the commented block at the top of `frontend/src/styles.css`.

- Tokens: paper `#f6f1e6`, surface white, graphite ink `#1c2026`, muted ink, 1px lines, blue accent with hover/active/soft, success/pending/danger each with a soft background, a sticker yellow, a type scale (`--fs-caption` to `--fs-display`), spacing `--space-1..8`, radii, three subtle shadows (raised layers only: menu, dialog, toast), control heights (40px, 44px touch minimum at 1100px and narrower, 48px large) and state tokens for hover, active, focus ring (2px solid, 2px offset, `:focus-visible`), disabled (`not-allowed`), loading and error.
- Fonts: system stacks only (serif display for headings, sans body, mono for stamps); no `@font-face`, `@import` or CDN.
- Student-life details: dashed perforation under the header and above the footer, `.price-tag` sticker (`PriceTag`, KZT), stamp-like `.status-badge`.
- Shared components live in `frontend/src/ui/` (`index.js`): Button (primary, secondary, ghost, danger; default, large; `loading`; `href` renders a link), Field, StatusBadge (pending, active, sold, rejected, removed), Skeleton and Loading, Notice and Toast, Dialog, EmptyState, ErrorState, NotFound, PriceTag.
- Seeing every component and state: `ui/Gallery.jsx` is rendered by `ui/Gallery.test.jsx` and, in development builds only, at `/?ui-gallery` (gated by `import.meta.env.DEV` in `main.jsx`, absent from production builds).
- Motion: only `transform` and `opacity` are animated (page fade 160ms, menu slide, dialog, notice, spinner, skeleton pulse). `prefers-reduced-motion: reduce` disables all animation and transitions. Nothing waits on an animation; no scroll hijacking or ambient motion.
- Shell: sticky header with dashed bottom edge, modal mobile menu at 1100px and narrower (named dialog, focus trap, Esc, scroll lock, focus restoration), footer pinned to the viewport bottom, 16px gutters at 600px and narrower, `scroll-padding-top` so focused content is not hidden by the sticky header.
- Per-screen restyling is #111-#115; the older student/admin notes below describe layouts that remain.

Adapted from the user-authorized Lovable source described in [provenance](lovable-integration.md). The shared foundation is applied to student screens in issue41; admin adaptation is completed in issue42. These visual primitives apply across the real SQLite/memory/PostgreSQL modes and explicit synthetic mock; storage/auth mode never changes server authority. [Current docs index](index.md) links setup and dated screen evidence.

- Semantic success, pending and error colors use corresponding soft backgrounds; informational session guidance stays neutral. Color supplements explicit text and roles.
- System sans-serif body with stronger compact heading hierarchy; no runtime font/CDN dependency. Card radius12px with restrained shadow; button/input radius8px.
- Reusable classes: `.panel`, `.listing-card`, `.account-form`, `.button.primary`, `.button.secondary`, `.form-feedback`, `.form-feedback.info`, `.form-feedback.error`, `.status-badge` with data-tone pending/error. Existing labels, errors, pending text and controls remain functional.
- SiteHeader/Wordmark provide one set of real links for desktop and mobile; mobile1100px drawer is named/modal, keyboard trapped, scroll locked and dismissible with focus restoration. Route navigation retains page heading focus.
- Keep visible focus, minimum42px buttons, wrapping content at390px, semantic form labels and reduced-motion behavior. No fake data, image tokens in URLs or client-invented admin capabilities.


## Student screens (#41)

Student-only styles are scoped beneath .student-page; admin pages keep their prior layout. FormIntro groups actual forms without owning values, validation or requests. Auth routes have a compact centered form; profile uses avatar/contact sections with a separate permanent-deletion danger zone. Read-only fields have muted/dashed surfaces; destructive buttons use explicit red/text labels and retain confirmation/cancel.

Catalog filters use a full-width query and four balanced desktop filters, stacking on narrow screens. Auto-fill card tracks keep a single result at normal card width instead of stretching across the page. Exact price/status text remains explicit; Pending/Active/Sold/Rejected/Removed receive semantic supporting tones. Gallery images are contained without distortion, with keyboard photo controls; contact/report cards form a desktop sidebar and stack at mobile width. Create/edit forms retain upload ordering/progress/uncertainty and immutable fields. See [coverage/evidence](student-screens.md).

## Administration screens (#42)

Admin routes use the same paper, white cards, ink and blue accent tokens. Navigation wraps; queue cards keep a bounded width and long identities wrap. Status text has supporting tones. Pending publication and destructive removal occupy separate cards; red identifies destructive confirmation. Private gallery images use contain sizing. On narrow screens cards/decisions stack without page overflow. Cancelled suspension/removal confirmations restore action focus. See [admin coverage](admin-screens.md).
