# Shared visual foundation

Adapted from the user-authorized Lovable source described in [provenance](lovable-integration.md). The shared foundation is applied to student screens in issue41; admin adaptation continues in issue42.

- Paper: oklch(0.975 0.008 85); surface:white; ink:oklch(0.22 0.02 255).
- Primary/focus: deep teal oklch(0.45 0.08 195), with pale teal emphasis. Border:oklch(0.88 0.012 85).
- Semantic success, pending and error colors use corresponding soft backgrounds; informational session guidance stays neutral. Color supplements explicit text and roles.
- System sans-serif body with stronger compact heading hierarchy; no runtime font/CDN dependency. Card radius12px with restrained shadow; button/input radius8px.
- Reusable classes: `.panel`, `.listing-card`, `.account-form`, `.button.primary`, `.button.secondary`, `.form-feedback`, `.form-feedback.info`, `.form-feedback.error`, `.status-badge` with data-tone pending/error. Existing labels, errors, pending text and controls remain functional.
- SiteHeader/Wordmark provide one set of real links for desktop and mobile; mobile1100px drawer is named/modal, keyboard trapped, scroll locked and dismissible with focus restoration. Route navigation retains page heading focus.
- Keep visible focus, minimum42px buttons, wrapping content at390px, semantic form labels and reduced-motion behavior. No fake data, image tokens in URLs or client-invented admin capabilities.


## Student screens (#41)

Student-only styles are scoped beneath .student-page; admin pages keep their prior layout. FormIntro groups actual forms without owning values, validation or requests. Auth routes have a compact centered form; profile uses avatar/contact sections with a separate permanent-deletion danger zone. Read-only fields have muted/dashed surfaces; destructive buttons use explicit red/text labels and retain confirmation/cancel.

Catalog filters use a full-width query and four balanced desktop filters, stacking on narrow screens. Auto-fill card tracks keep a single result at normal card width instead of stretching across the page. Exact price/status text remains explicit; Pending/Active/Sold/Rejected/Removed receive semantic supporting tones. Gallery images are contained without distortion, with keyboard photo controls; contact/report cards form a desktop sidebar and stack at mobile width. Create/edit forms retain upload ordering/progress/uncertainty and immutable fields. See [coverage/evidence](student-screens.md).
