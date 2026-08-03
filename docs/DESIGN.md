# Frontend Design Index & Authority Map

Canonical frontend design index and authority map for Dokushodo (読書道) — a translated Japanese web novel reading site.

## Scope and Purpose

`docs/DESIGN.md` is the primary entry point and authority map for frontend design, visual identity, accessibility, responsive behavior, public reader experience, and admin operational design.

Subordinate specifications live under `docs/design/`.

## Authority and Conflict-Resolution Order

When documents conflict, authority is determined by:

1. `docs/ARCHITECTURE.md` — Technical boundaries, route ownership, security, and storage contracts win over design specs.
2. `docs/DESIGN.md` — Master design index and authority map.
3. Subordinate design contracts under `docs/design/`.
4. `docs/WORK.md` — Active unfinished work register.
5. `docs/HISTORY.md` — Completed implementation evidence and historical record.

Subordinate design files MUST NOT duplicate technical architecture, backend schemas, security boundaries, or operational procedures. They link to `docs/ARCHITECTURE.md`, `docs/CONFIGURATION.md`, `docs/OPERATIONS.md`, or `docs/DEPLOYMENT.md`.

## Surface Definitions

- **Public Surface (`frontend/app/(public)/*`):** Reader-facing experience (Yokocho Lantern palette, Bunko-bon shelf visual identity, quiet reader chrome, mobile tab bar).
- **Admin Surface (`frontend/app/(admin)/admin/*`):** Operator-facing administrative control plane (high-density, information-dense, security-masked, no Yokocho motifs).

## Design Authority Map

### Shared Design Contracts
- [`docs/design/shared/principles.md`](design/shared/principles.md) — Product UX principles.
- [`docs/design/shared/interaction.md`](design/shared/interaction.md) — Control states, keyboard rules, forms, dialogs.
- [`docs/design/shared/accessibility.md`](design/shared/accessibility.md) — WCAG AA compliance, ARIA, focus, contrast.
- [`docs/design/shared/responsive.md`](design/shared/responsive.md) — Breakpoints, safe areas, layout adaptation.
- [`docs/design/shared/states.md`](design/shared/states.md) — Standard data states (loading, empty, error, settled, unavailable).
- [`docs/design/shared/content-and-copy.md`](design/shared/content-and-copy.md) — Tone, terminology, CJK wrapping, safe copy.

### Public Design Specifications
- [`docs/design/public/design-system.md`](design/public/design-system.md) — Yokocho Lantern palette, typography, status badges.
- [`docs/design/public/assets.md`](design/public/assets.md) — Brand mark, favicons, OG image, empty state illustrations.
- [`docs/design/public/shell.md`](design/public/shell.md) — Desktop header, mobile bottom tab bar, chrome suppression.
- [`docs/design/public/discovery/`](design/public/discovery/README.md) — Home, Browse, Search overlay, Taxonomy & Source pages.
- [`docs/design/public/reading/`](design/public/reading/README.md) — Novel detail (sticky panel & tabs), Chapter reader (Aa panel).
- [`docs/design/public/account/`](design/public/account/README.md) — Library board, Reading history, Authored reviews, Notifications, Settings.
- [`docs/design/public/participation/`](design/public/participation/README.md) — Request novel, API contribution.
- [`docs/design/public/authentication/`](design/public/authentication/README.md) — Login page/modal, OAuth callback, Logout.
- [`docs/design/public/trust/`](design/public/trust/README.md) — Informational pages (FAQ, News, About), DMCA takedown.
- [`docs/design/public/system/`](design/public/system/README.md) — 404 Not Found, Error fallback, Maintenance mode.

### Admin Design Specifications
- [`docs/design/admin/design-system.md`](design/admin/design-system.md) — High-density visual direction, operational status tokens, PII masking.
- [`docs/design/admin/shell.md`](design/admin/shell.md) — Sidebar navigation, breadcrumbs, page frame.
- [`docs/design/admin/ingestion/`](design/admin/ingestion/README.md) — Crawler trigger, Activity logs.
- [`docs/design/admin/content/`](design/admin/content/README.md) — Catalog library, Translation jobs, Editor, Glossary.
- [`docs/design/admin/moderation/`](design/admin/moderation/README.md) — Requests queue, Review moderation, DMCA takedowns.
- [`docs/design/admin/people/`](design/admin/people/README.md) — User accounts & roles.
- [`docs/design/admin/operations/`](design/admin/operations/README.md) — System dashboard, Analytics, Audit log, Credentials, Maintenance status.

### Component Primitives
- [`docs/design/components/`](design/components/README.md) — Cards (compact vs rich), Forms, Navigation, Dialogs & Sheets, Feedback.

### Contract Templates
- [`docs/design/templates/domain.md`](design/templates/domain.md) — Standard domain contract structure.
- [`docs/design/templates/page.md`](design/templates/page.md) — Standard page contract structure.

### Audits & History
- [`docs/design/audits/2026-08-02-public-ui.md`](design/audits/2026-08-02-public-ui.md) — Historical UI/UX flaw audit catalog (F1–F20).

## Design & Implementation Status Index

| Area | Contract Status | Implementation Status | Automated Verification | Manual Acceptance | Active Work | Canonical Contract | Owner |
|---|---|---|---|---|---|---|---|
| Public Tokens | Approved | Implemented | `token-contrast.test.ts` (34 checks), `typecheck`, `build` | DEBT-FE-01A (Open) | DEBT-FE-01 | `docs/design/public/design-system.md` | Frontend lead |
| Navigation Shell | Approved | Implemented | `chrome-suppression.test.tsx`, `mobile-tab-bar.test.tsx` | DEBT-FE-01A (Open) | DEBT-FE-01 | `docs/design/public/shell.md` | Frontend lead |
| Shared Search | Approved | Implemented | `search-overlay.test.tsx` (22 tests), `public-router.py` | DEBT-FE-01A (Open) | DEBT-FE-01 | `docs/design/public/discovery/search.md` | Frontend lead |
| Browse & Taxonomy | Approved | Implemented | `browse-page.test.tsx`, `taxonomy-contract.test.tsx` | DEBT-FE-01A (Open) | DEBT-FE-01 | `docs/design/public/discovery/browse.md` | Frontend lead |
| Novel Detail | Approved | Implemented | `novel-detail-honesty.test.tsx`, `novel-detail-tabs.test.tsx` | DEBT-FE-01A (Open) | DEBT-FE-01 | `docs/design/public/reading/novel-detail.md` | Frontend lead |
| Chapter Reader | Approved | Implemented | `reader-contrast.test.ts` (6 tests), `reader-controls.test.tsx` | DEBT-FE-01A (Open) | DEBT-FE-01 | `docs/design/public/reading/chapter-reader.md` | Frontend lead |
| Library & Account | Approved | Implemented | `library-board.test.tsx`, `account-desktop-shell.test.tsx` | DEBT-FE-01A (Open) | DEBT-FE-01 | `docs/design/public/account/library.md` | Frontend lead |
| Request Novel | Approved | Implemented | `request-novel.test.tsx`, `public_requests.py` | DEBT-FE-01A (Open) | DEBT-FE-01 | `docs/design/public/participation/request-novel.md` | Frontend lead |
| Review Moderation | Approved | Implemented | `test_review_moderation.py` (74 tests), `reviews.test.tsx` | DEBT-FE-01A (Open) | DEBT-FE-01 | `docs/design/admin/moderation/reviews.md` | Product lead |
| Admin Operations | Approved | Implemented | `admin-shell.test.tsx`, `maintenance.test.tsx` | DEBT-FE-01A (Open) | DEBT-FE-01 | `docs/design/admin/design-system.md` | Ops lead |
| Component Primitives | Approved | Implemented | `button.test.tsx`, `badge.test.tsx`, `input.test.tsx` | DEBT-FE-01A (Open) | DEBT-FE-01 | `docs/design/components/README.md` | Frontend lead |

## Non-Negotiable Review Gates

1. **Accessibility (WCAG 2.1 AA):** All interactive elements operable by keyboard, visible focus (two-layer on primary buttons), 4.5:1 text contrast, screen-reader labels.
2. **Security & Redaction:** Credentials masked (`mask-token.ts`), no raw backend errors or stack traces exposed on public surfaces.
3. **No Unbacked Claims:** Never present simulated numbers or fake reviews; state unavailable features explicitly.
4. **Chrome Suppression:** Reader routes must suppress header navigation, bottom tab bar, and footers.
5. **No Nested Controls:** Card surfaces must not nest `<a>` inside `<a>` or buttons inside links.

For active implementation tasks, see [`docs/WORK.md`](WORK.md). For completed evidence, see [`docs/HISTORY.md`](HISTORY.md).
