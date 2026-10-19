# Supplied product photos restored (#47)

Reproduced the reported regression in explicit mock mode: the catalog contained one generic book and its detail image decoded to1×1. It now restores all six JPEGs from the user-supplied Lovable repository at commit07305f1f4007f1b8de852db3cb707d085e9f6caf. The source repository remains unchanged. [Provenance](mock-photo-provenance.json) records exact source/target paths, bytes and SHA-256 for every image; all six target files are byte-identical originals, with no transformation or invented license.

| ID/photo | Title | Category | Source price/KZT | Current demo price/KZT |
| --- | --- | --- | --- | --- |
| 1 | Graphing calculator, works perfectly | Electronics1 | 38000.00 | 15000.00 |
| 2 | Noise-cancelling over-ear headphones | Electronics1 | 62000.00 | 20000.00 |
| 3 | 24-inch IPS monitor, 1080p | Electronics1 | 45000.00 | 30000.00 |
| 4 | Algorithms textbook bundle (4 books) | Books3 | 12000.00 | 12000.00 |
| 5 | Winter down jacket, size M | Clothing2 | 25000.00 | 12000.00 |
| 6 | LED desk lamp with USB charging port | Furniture4 | 6500.00 | 6500.00 |

The four lower demo prices are intentional user-requested overrides in #48, not prices attributed to the source repository. Provenance retains source_price separately from demo_price; #47 screenshots remain historical evidence of the original prices. All six JPEG hashes and item identities are unchanged.

All are Active demo fixtures with deterministic newest-first order and safe synthetic seller/contact identities. Existing canonical numeric identifiers, two-decimal strings and protected /listings/{id}/photos/{id} DTOs remain. Seed assets live under frontend/src/mock-assets, imported by the DEV-only mock photo module; they are never placed in public/. After current mock eligibility/ownership/linkage checks, the photo route reads the local bundled original and returns image/jpeg bytes, then existing UI code creates/revokes private blob URLs. Admin review uses its separate protected route. Source URLs do not replace protected DTO URLs.

These six visual fixtures belong only to the explicit synthetic demo. They do not seed or modify real PostgreSQL records, real upload storage or production content. Uploaded synthetic demo files still use the generated placeholder; real backend image decoding/limits/privacy are unchanged. Local Vite asset reads are allowed and counted separately from prohibited backend/external calls. Reset reconstructs all six image mappings; deleting/removing one record leaves other originals intact. To inspect the seeded seller's own listings, sign in as seller-demo@sdu.edu.kz with a synthetic password, in the same tab. The existing banner and [mock setup](integration-contracts.md) remain required.

## Verification

All157 frontend tests, typecheck and production build/isolation pass. The two new photo tests compare six mappings, actual JPEG signatures/bytes/hashes, private permission/linkage checks before reads, seller/admin visibility and delete/remove/reset isolation. Production checks compare emitted bytes against all six original hashes and reject fixture titles/asset names; real-mode output contains none of them, and mock production builds remain refused. Three affected backend OpenAPI/model/HTTP contract checks pass after updating the current canonical example to the restored catalog. Backend runtime/schema/dependencies are unchanged, so the already verified full PostgreSQL suite was not redundantly rerun.

[Browser result](evidence/mock-original-photos/mock-browser-result.json): all six originals decode at816×816 and each detail blob matches the exact source SHA-256; image/jpeg confirmed. Full mock student/admin journey passes with32 local asset reads, **zero real backend/external requests** and no browser storage. Actual1280px/390px captures were viewed: [catalog desktop](evidence/mock-original-photos/six-products-desktop.png), [catalog mobile](evidence/mock-original-photos/six-products-mobile.png), [detail desktop](evidence/mock-original-photos/original-detail-desktop.png), [detail mobile](evidence/mock-original-photos/original-detail-mobile.png), [seller](evidence/mock-original-photos/original-seller.png), [admin](evidence/mock-original-photos/original-admin.png). Existing #43 browser controls/lifecycle assertions still run. Earlier evidence is preserved.

Reproduce with the explicit mock server, then `MOCK_EVIDENCE_DIR` set to a new directory and `node tools/mock_browser.mjs`, as documented in the integration guide. No dependency installation or user-preview restart is needed. Production deployment and real inbox verification remain separate; SQLite#44 stays deferred.

## Intentional demo-price overrides (#48)

Calculator15000.00, headphones20000.00, monitor30000.00 and jacket12000.00 are current user-requested demo prices. Textbooks12000.00 and lamp6500.00 remain unchanged. The source_price/demo_price fields preserve this distinction, and all original JPEG hashes remain unchanged. Existing fixture/transport/filter tests (16 cases), typecheck and production build/isolation pass; three affected no-database contract checks pass. [Quick browser verification](evidence/demo-price-overrides/browser-result.json) checks all six catalog/detail amounts and original image hashes; the inclusive12000.00–12000.00 filter returns both the textbooks and jacket. [Current catalog](evidence/demo-price-overrides/catalog.png) shows the new prices. Prior #47 screenshots remain historical evidence. No full backend suite or full-stack smoke was needed for this fixture-only change.
