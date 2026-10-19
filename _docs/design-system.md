# Shared visual foundation

Adapted from the user-authorized Lovable source described in [provenance](lovable-integration.md). This is the shared foundation; screen-specific redesign continues in issues41/42.

- Paper: oklch(0.975 0.008 85); surface:white; ink:oklch(0.22 0.02 255).
- Primary/focus: deep teal oklch(0.45 0.08 195), with pale teal emphasis. Border:oklch(0.88 0.012 85).
- Semantic success, pending and error colors use corresponding soft backgrounds; informational session guidance stays neutral. Color supplements explicit text and roles.
- System sans-serif body with stronger compact heading hierarchy; no runtime font/CDN dependency. Card radius12px with restrained shadow; button/input radius8px.
- Reusable classes: `.panel`, `.listing-card`, `.account-form`, `.button.primary`, `.button.secondary`, `.form-feedback`, `.form-feedback.info`, `.form-feedback.error`, `.status-badge` with data-tone pending/error. Existing labels, errors, pending text and controls remain functional.
- SiteHeader/Wordmark provide one set of real links for desktop and mobile; mobile1100px drawer is named/modal, keyboard trapped, scroll locked and dismissible with focus restoration. Route navigation retains page heading focus.
- Keep visible focus, minimum42px buttons, wrapping content at390px, semantic form labels and reduced-motion behavior. No fake data, image tokens in URLs or client-invented admin capabilities.
