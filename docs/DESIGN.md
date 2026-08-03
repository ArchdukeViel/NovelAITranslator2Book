# Dokushodo Design System

Canonical design authority for Dokushodo (読書道), a public reader for translated Japanese web novels with an owner-operated ingestion and translation control plane. This document is the single source of truth for visual identity, tokens, layout, components, states, accessibility, responsive behavior, motion, copy, and anti-slop rules. It supersedes all earlier design documents and is the reference for every page brief under `docs/design/`.

## 1. Purpose and Authority

### 1.1 Product

Dokushodo is a webnovel reader. Readers discover translated Japanese web novels, read chapters in a quiet typographic surface, track reading progress, save novels to a personal library, request novels, and leave ratings and reviews. A separate owner-only control plane ingests source novels, schedules translation, moderates requests and reviews, and manages credentials and system health.

### 1.2 Surfaces

- Public surface: reader-facing experience served to guests and signed-in readers. Visual identity is Modern Japanese Literary, built on the Shuji Vermillion and Washi theme with restrained bunko (paperback book) and lantern motifs.
- Admin surface: owner-only operational control plane. Utilitarian, high-density, no literary decoration.

### 1.3 Design authority and conflict resolution

When documents conflict, authority is resolved in this order:

1. `docs/ARCHITECTURE.md`: technical boundaries, route ownership, security, and storage contracts.
2. `docs/DESIGN.md`: this document, the canonical design authority.
3. `docs/design/public/*.md` and `docs/design/admin/*.md`: standalone Stitch page briefs.
4. `docs/WORK.md`: active unfinished work register.
5. `docs/HISTORY.md`: completed implementation evidence.

Design documents must not duplicate technical architecture, backend schemas, security boundaries, or operational procedures. Those belong in `docs/ARCHITECTURE.md`, `docs/CONFIGURATION.md`, and `docs/DEPLOYMENT.md`.

### 1.4 Relationship to page briefs

`docs/design/public/` and `docs/design/admin/` contain exactly one standalone visual-generation brief per rendered page. Each brief repeats a compact Global Visual Snapshot so it can be copied alone into Google Stitch or another image-generation tool. The snapshot is render context, not a second authority; this document remains canonical. When this document and a brief disagree, this document wins and the brief must be corrected.

### 1.5 Document maintenance

- Update this document when global tokens, typography, layout, components, states, accessibility, responsive, motion, content, or brand behavior change.
- Update a page brief only when that page's visual behavior changes.
- Run `graphify update . --no-cluster` after every documentation edit.
- Dead briefs are removed when their route is removed; new rendered routes receive a brief before the change ships.

## 2. Current Design Status

The frontend App Router overhaul (PR #38) is merged and describes the current implementation baseline at commit `95fbcd0` and its descendants.

- Implemented: full public surface (home, browse, taxonomy, novel detail, chapter reader, account, auth, trust and system pages), full admin surface (dashboard, crawler, library, activity, scheduler, maintenance, analytics, requests, reviews, users, editor, credentials, settings, audit, takedowns, glossary), shared search overlay, light and dark site themes, reader light/dark/sepia themes, brand assets, and the Stitch-ready page brief structure.
- Frontend verification baseline at the merge: 76 test files and 841 tests passed.
- Not implemented: ranking data (the Ranking page intentionally shows an unavailable state), public contribution key management (gated, documented as not available), profile editing, account deletion, and admin-curated featured rotation (the homepage spotlight is derived from catalog data, not owner curation).
- Deferred intentionally: extended locale support, WebGL graphics, GSAP sequences.
- Still manually unverified: screen-reader acceptance across NVDA/VoiceOver/TalkBack, forced-colors mode, and 200% zoom reflow. These are tracked as manual acceptance work in `docs/WORK.md` (DEBT-FE-01A). Do not claim hosted or manual visual validation that was not performed.

## 3. Design Read and Target Dials

- Product: Dokushodo
- Audience: webnovel readers
- Public identity: Modern Japanese Literary
- Primary theme: Shuji Vermillion and Washi
- Supporting motifs: restrained bunko/bookplate and lantern identity
- Admin identity: utilitarian operational control plane

Surface dials (0 to 10 scale; higher means more visual variance, motion, or density):

| Surface | DESIGN_VARIANCE | MOTION_INTENSITY | VISUAL_DENSITY |
|---|---|---|---:|
| Public discovery | 7 | 4 | 4 |
| Public reader | 1 | 2 | 2 |
| Account and auth | 3 | 3 | 4 |
| Admin | 1 | 2 | 8 |

Interpretation:

- Public discovery (home, browse, genre, tag, source, ranking, novel detail): the most expressive public area. Vermillion focal actions, bookplate covers, one hero moment per page, restrained editorial flair.
- Public reader (chapter reader): intentionally quiet. The story text is the entire screen; chrome is suppressed, no decorative motion, near-zero visual variance.
- Account and auth (account pages, login, logout, auth callback): calm and functional, moderately dense, personal data surfaces with clear hierarchy.
- Admin: utilitarian control plane. Very high density, low variance, minimal motion, no public literary motifs.
- Informational, trust, and system pages (about, contact, cookie policy, DMCA, FAQ, legal, maintenance, news, not found, error, privacy, support, terms): public surface values applied at the restrained end. One focal moment or action at most, no decorative motifs, calm editorial composition.

## 4. Brand Identity

### 4.1 Name and logo roles

- Product name: Dokushodo (読書道). Public copy must never use the internal codename "Novel AI".
- The lantern is the signature identity shape. It appears in two distinct forms.

### 4.2 Brand mark (minimalist)

- File: `frontend/public/assets/dokushodo/brand/brand-mark.png`
- A one-color minimalist pinched-lantern silhouette, no gradients.
- Used in desktop and mobile navigation headers and the footer.
- Must remain recognizable from 16px to 64px height.
- Safe zone: 4px padding around the mark.
- Budget: under 50 KiB.

### 4.3 Application icon (detailed)

- File: `frontend/public/assets/dokushodo/brand/icon.svg`
- Detailed lantern with a soft window glow, kanji accent (読), and tassel. Subtle linear gradients are permitted inside this asset only (`#E23E1D` to `#C22F13` body; `#FFF3E0` to `#FFE0B2` glow).
- Used as the scalable icon source, favicon source, and app shortcut icon.
- Fallbacks: `favicon.ico`; `apple-touch-icon.png` (180x180).

### 4.4 PWA icons and manifest

- Manifest route: `frontend/app/manifest.ts`.
- `icon-192.png` (192x192, purpose any); `icon-512.png` (512x512, purpose maskable).
- Manifest background and theme color: Midnight Slate `#131822`.
- PWA name: "Dokushodo"; short name: "Dokushodo"; standalone display.

### 4.5 Open Graph image

- File: `frontend/public/assets/dokushodo/brand/open-graph.png`
- 1200x630 px default social image, used by `og:image` and `twitter:image` when no novel-specific image exists.
- Budget: under 200 KiB.

### 4.6 Illustrations

- Files under `frontend/public/assets/dokushodo/illustrations/`: `empty.png` (catalog and library empty states), `404.png` (page-not-found surface), `maintenance.png` (maintenance surface).
- Flat vector-style illustrations on the brand palette; no synthetic blurs or glassmorphism.
- Each under 100 KiB. Decorative images use `alt=""` and are not the source of meaning.

### 4.7 Logo treatment rules

- Allowed: brand mark in navigation and footer; icon in favicon, manifest, and shortcuts; open-graph image for social; detailed lantern in illustrations and the app icon.
- Prohibited: stretching, recoloring, rotating, adding shadows or glow to the brand mark, placing the mark on busy imagery without safe zone, and repeating lantern geometry as background decoration, bullet markers, or section motifs.
- Brand fidelity: never redraw the lantern from memory; use the shipped assets.

## 5. Color System

All tokens are HSL values on `:root` (light) and `.dark` (dark). Status must never rely on color alone; pair with text or icon.

### 5.1 Semantic token roles

| Role | Light HSL | Dark HSL | Use |
|---|---|---|---|
| `--background` | `38 25% 96%` (Washi warm paper) | `222 25% 10%` (Midnight Slate) | Page background |
| `--foreground` | `222 20% 14%` | `38 20% 90%` | Default body text |
| `--card` | `0 0% 100%` | `222 20% 14%` | Card, popover, modal surfaces |
| `--card-foreground` | `222 20% 14%` | `38 20% 90%` | Text on card surfaces |
| `--popover` | `0 0% 100%` | `222 20% 14%` | Popover and dropdown surfaces |
| `--popover-foreground` | `222 20% 14%` | `38 20% 90%` | Text on popover surfaces |
| `--primary` | `14 80% 50%` (Shuji Vermillion) | `14 85% 55%` | Primary CTAs, active tabs, focal actions |
| `--primary-foreground` | `14 20% 4%` | `14 20% 4%` | Text on primary fill |
| `--primary-text` | `14 75% 32%` | `14 70% 75%` | Vermillion text on neutral surfaces |
| `--secondary` | `195 25% 88%` (soft teal) | `195 25% 22%` | Structural chips, dividers, supporting fills |
| `--secondary-foreground` | `222 20% 14%` | `38 25% 85%` | Text on secondary fill |
| `--muted` | `38 18% 90%` | `222 16% 20%` | Quiet surfaces, skeletons, disabled areas |
| `--muted-foreground` | `222 20% 14%` | `38 20% 90%` | Text on muted surfaces (known limitation: equals foreground; use size or weight for de-emphasis, never rely on this token for hierarchy) |
| `--accent` | `340 55% 40%` (Sakura) | `340 62% 66%` | Favorites, ratings, save-to-library, reading progress, source titles |
| `--accent-foreground` | `340 25% 96%` | `38 25% 7%` | Text on accent fill |
| `--destructive` | `1 75% 55%` | `1 75% 55%` | Errors, failed states, removal, blocked content |
| `--destructive-foreground` | `1 20% 4%` | `1 20% 4%` | Text on destructive fill |
| `--destructive-text` | `1 20% 22%` | `1 20% 62%` | Destructive text on neutral surfaces |
| `--border` | `222 20% 14% / 0.09` | `38 20% 87% / 0.1` | Card, input, and divider borders |
| `--input` | `38 20% 90%` | `222 16% 16%` | Input field background |
| `--ring` | `14 80% 45%` | `14 85% 60%` | Focus ring |
| `--focus-ring` | `14 80% 45%` | `14 85% 60%` | Primary button outer focus ring |
| `--success` | `150 45% 32%` | `150 45% 38%` | Completed, published, healthy, active |
| `--success-text` | `150 20% 18%` | `150 20% 58%` | Success text on neutral surfaces |
| `--warning` | `45 80% 48%` | `45 85% 55%` | Stale, partial, degraded, hiatus |
| `--warning-text` | `45 20% 18%` | `45 20% 58%` | Warning text on neutral surfaces |
| `--info` | `205 70% 45%` | `205 70% 55%` | Running, scheduled, informational |
| `--info-text` | `205 20% 20%` | `205 20% 58%` | Info text on neutral surfaces |
| `--sidebar` | `38 20% 90%` | `222 25% 8%` | Sidebar background |
| `--sidebar-accent` | `38 18% 87%` | `222 16% 16%` | Sidebar hover and active accent |

### 5.2 Usage rules

- Vermillion (`--primary`) is for primary focal actions and active selection only: "Start Reading", "Sign In", primary form submits, active tabs, active account and admin nav items. Never decorative.
- Sakura (`--accent`) is restricted to favorites, star ratings, save-to-library actions, reading progress indicators, and original source titles. Never used for buttons, focus rings, or generic highlights.
- Soft teal (`--secondary`) is for structural chips, dividers, and supporting emphasis.
- Semantic statuses: success = completed/published/healthy; info = running/scheduled; warning = stale/partial/hiatus/degraded; destructive = failed/rejected/removed/blocked; muted = inactive/dropped/unavailable.
- Reader light, dark, and sepia themes are an independent token system scoped to the reading surface only; they must not leak into global surfaces, and global tokens must not be toggled by the reader theme switch.

### 5.3 Resolved terminology

- "Lantern orange", "deep teal", "indigo accents", and "Plum" are retired. The canonical palette is Shuji Vermillion, Sakura, Soft Teal, Washi Warm Paper, and Midnight Slate.

## 6. Typography

### 6.1 Font families and roles

| Font | Files | Role |
|---|---|---|
| DM Sans (variable) | `--font-dm-sans` | All UI chrome: navigation, buttons, forms, body copy on pages |
| Noto Serif JP (variable) | `--font-noto-serif-jp` | Literary role: novel titles, chapter titles, reading content, section headings on public surfaces |
| DM Mono (400, 500) | `--font-dm-mono` | Metadata: chapter numbers, timestamps, word counts, identifiers, status labels |

Rules:

- Literary serif is for titles and reading content on public surfaces. Do not mix families within one semantic element.
- Admin surfaces never use the serif font; UI and table text is DM Sans, identifiers and numbers are DM Mono.

### 6.2 Hierarchy and sizes

- Page title (public): large literary serif, e.g. 36 to 48px at desktop, 30px at mobile.
- Hero title (home spotlight): literary serif, 30 to 60px across breakpoints.
- Section headings: literary serif 20 to 24px on public surfaces.
- Body: 14 to 16px DM Sans with relaxed leading (1.6 to 2.0 for reading text).
- Metadata labels: 11 to 12px DM Mono, uppercase with letter spacing, muted.
- Admin: compact 12 to 14px DM Sans; 12px uppercase muted table headers; DM Mono for IDs, timestamps, counts.

### 6.3 Line length and reading typography

- Reading column widths: default 680px, narrow 560px, wide 800px.
- Chapter reader body: Noto Serif JP, line-height 1.8, justified narration with left-aligned last line on desktop, left-aligned on mobile, strict line-breaking for CJK (kinsoku shori).
- Dialogue paragraphs are always left-aligned.
- Long titles wrap cleanly and are never truncated on primary displays; truncation is allowed only in compact card contexts.
- CJK text uses safe word wrapping; mixed Japanese and English inline text wraps naturally.

### 6.4 Emphasis and wrapping

- Emphasis uses weight and size, not color alone.
- Italic is reserved for placeholders and secondary notes, never for entire paragraphs of interface copy.
- No em dashes or en dashes in generated interface copy.

## 7. Layout System

### 7.1 Breakpoints

| Breakpoint | Width | Purpose |
|---|---|---|
| Base | < 640px | Phones; 320px minimum support |
| `sm` | >= 640px | Large phones, small tablets |
| `md` | >= 768px | Shell switches to desktop navigation at this width |
| `lg` | >= 1024px | Desktop grids; admin sidebar fixed; novel detail sticky cover panel |
| `xl` | >= 1280px | Wide desktop |
| `2xl` | >= 1536px | Ultra-wide; content never exceeds its max width |

### 7.2 Maximum widths and gutters

- Public page content: max 1280px (`max-w-7xl`); gutters 16px mobile, 24px at `md` and wider.
- Reading columns: 560 / 680 / 800px.
- Content and legal pages: max 896px (`max-w-4xl`) or 768px (`max-w-3xl`).
- Admin content: fluid, constrained by the fixed sidebar; page padding 20px.
- Browse grids: fill available width with responsive columns.

### 7.3 Shells

- Public shell: sticky header with inline links (Home, Browse, Request, Library), search trigger, theme toggle, notification bell, and user menu on `md` and up; compact header plus fixed bottom tab bar (Home, Browse, Search, Library, Account) below `md`. Footer with navigation and legal columns.
- Account shell: fixed left sidebar (desktop) with Library, History, Notifications, Requests, Reviews, Contributions, Settings, an Unavailable Support entry, theme control, and Sign out; mobile shows a horizontal scrollable sub-navigation bar instead.
- Admin shell: fixed left sidebar with Home, Add Novel, Library, Activity Log, Scheduler, Maintenance, Analytics, Requests, Reviews, Users, Editor, Credentials, Settings, Audit Log; top bar with breadcrumb and session controls; collapsible drawer on narrow viewports.
- Reader chrome: on chapter routes the public header, tab bar, and footer are suppressed entirely; only a minimal reader chrome bar and progress line remain.

### 7.4 Fixed-control collision and safe areas

- At most one fixed bottom bar on screen at a time.
- Fixed bars pad for `env(safe-area-inset-bottom)`; sticky headers must never obscure focused content (scroll margin).
- Novel detail uses a fixed bottom reading bar on mobile that suppresses the tab bar.

### 7.5 Tables and overflow

- Admin tables scroll horizontally on narrow viewports with sticky headers; public surfaces prefer card and list layouts over tables.

## 8. Shape, Border, and Elevation System

- Base radius: 6px (`0.375rem`). Derived: large 6px (cards, modals), medium 4px (buttons, inputs, badges), small 2px (chips, compact elements), full pill for status badges and avatars.
- The PR #38 overhaul returned to this base radius system; no oversized rounded containers.
- Prefer flat surfaces: cards are distinguished by border, not shadow. Elevation is reserved for overlays: small shadow for popovers and dropdowns, medium for elevated cards, large for complex menus, 2xl for modals and drawers.
- Overlay backdrops may use subtle blur; static surfaces must not.
- Prohibited: decorative glow, colored shadows, or elevation on non-overlay UI surfaces.
- Icon sizing: 16 to 20px inline icons; 24px+ for touch-primary icons.
- Z-index scale: sticky header 1, sticky content 10, sidebar 20, public header 30, mobile nav and fixed CTAs 40, modal/search/reader chrome 50, admin overlay 60, skip link 100. No arbitrary values.

## 9. Component and Interaction System

All component contracts below are global. Do not create component Markdown files under `docs/design/`; this section is canonical.

### 9.1 Buttons and links

- Primary buttons: vermillion fill, dark text, medium radius; exactly one per region.
- Secondary: bordered or card-surface with visible border; ghost for table row actions.
- Destructive: red fill or bordered red; used for removal and rejection with confirmation.
- Links: inline text with hover underline or muted-to-foreground color shift; never nested inside other interactive elements.
- Icon-only buttons always have accessible names.

### 9.2 Inputs and forms

- Inputs: bordered fields with light input background, visible focus ring; height 36px public, 32 to 36px admin.
- Labels above fields; errors associated with their field, destructive-colored, never generic.
- All fields required unless marked optional; disabled controls are clearly dimmed.

### 9.3 Badges and statuses

- Status badges: pill-shaped, semantic color with text label (never color alone), compact text.
- Tones: green success, amber warning, red destructive, blue info, neutral muted, violet for admin review status override.
- No decorative status dots; badges are semantic or they do not exist.

### 9.4 Cards and novel cards

- Cards: bordered flat surfaces with comfortable padding on public surfaces; dense on admin.
- Novel cards: cover (real cover image or bookplate fallback generated from title), literary title, one metadata line, hover indication that never includes scale or tilt on the whole card. Whole-card link nesting is prohibited; the title and an explicit action carry the link behavior.
- Bookplate fallback covers: restrained initials-and-borders bookplate; they exist only until real cover art is available.

### 9.5 Rails

- Horizontal scroll regions with labeled headers, arrow-key navigation, partial peek of the next card on mobile, max 5 rails per page above the footer on home.

### 9.6 Tabs

- Segmented tabs with vermillion fill for the active tab (novel detail: Overview, Chapters, Reviews) and sticky under the public header.

### 9.7 Pagination

- Compact Previous and Next controls with a page indicator; public catalog uses a next-page control.

### 9.8 Navigation

- See Shell rules (section 7.3). Active nav items use vermillion fill (public account) or accent bar/highlight (admin).

### 9.9 Search overlay

- Full-screen centered overlay opened from the header or the mobile Search tab; large input at top, results below, Escape closes, focus trapped while open, `/` keyboard shortcut available site-wide.

### 9.10 Dialogs, sheets, and popovers

- Dialogs: modal with backdrop, clear title, explicit confirm and Cancel; destructive dialogs name the affected target and use an active verb ("Remove", "Delete", "Reject", "Clear State").
- Sheets: bottom sheets for browse filters on mobile; one fixed bar at a time.
- Popovers: dropdown surfaces with small shadow; dismissed on Escape and outside click.

### 9.11 Toasts and alerts

- Toasts auto-dismiss after 4 seconds minimum, announce politely, and are never the sole feedback for destructive or error actions.
- Alerts and banners: inline bordered banners with icon, title, description, and an action when recoverable.

### 9.12 Skeletons

- Loading states use muted pulse placeholders matching final layout dimensions; never blank pages.

### 9.13 Admin tables and confirmation flows

- Tables: sticky muted uppercase headers, hover row highlight, compact cells, bulk selection checkboxes, selected-row action bar, horizontal scroll on narrow viewports.
- Admin confirmation flows: every destructive, crawler, or bulk action requires an explicit modal confirming the affected target; confirm button uses the active verb.

### 9.14 Keyboard, focus, and disabled behavior

- Everything interactive is keyboard operable; visible focus on all controls; two-layer focus on primary buttons (dark inner ring plus vermillion outer ring).
- Pending mutations disable the triggering control and show an inline spinner; focus returns to the triggering control after dialogs close.
- No nested interactive controls anywhere (no link inside link, no button inside link).

## 10. Shared State System

Canonical state behavior for data surfaces:

| State | Presentation |
|---|---|
| Initial | Skeleton matching final layout |
| Loading | Pulse skeletons or inline spinner; shown within 100ms; never blank |
| Empty | Clear explanation plus recovery action; never "0 chapters" style copy |
| Settled | Normal content |
| Pending mutation | Disabled control with inline spinner |
| Success | Toast or inline confirmation, success-toned |
| Partial / stale | Cached data with a subtle stale or partial indicator |
| Recoverable error | Inline error banner with retry action; preserves user input |
| Unavailable | Honest unavailable banner; never claims the feature exists |
| Unauthorized | Redirect to sign-in preserving the intended destination |
| Forbidden | Clear role message, no redirect loop |
| Not found | 404 surface with return-home and browse-catalog actions |
| Legal / HTTP 451 | Honest legal notice for removed content |
| Rate-limited | "Please wait a moment" style message |
| Maintenance | Maintenance surface explaining the reader is unavailable |
| Cancelled | Restore previous state, no error shown |
| Background revalidation | Existing data shown while fresh data loads silently |

Stitch variants: loading, empty, recoverable error, and unavailable are the states most worth separate frames. Do not overload one image with every state; use at most three alternate frames per brief.

## 11. Accessibility

Target: WCAG 2.2 Level AA.

- Contrast: 4.5:1 normal text, 3:1 large text and non-text controls, 3:1 focus indicators, 3:1 meaningful icons. Verified automatically for token pairs in both modes (34 contrast checks).
- Keyboard: full keyboard operability, visible focus everywhere, focus never obscured by sticky or fixed chrome.
- Landmarks: main, header, nav, footer, complementary as applicable; one h1 per page; heading hierarchy reflects visual hierarchy.
- Forms: labels on all fields, errors linked to fields, autofill compatible, no redundant entry.
- Live regions: polite for status and results, assertive for errors and destructive confirmations.
- Dialogs: focus trapped, focus restored on close, Escape supported.
- Target sizes: minimum 24x24px, 44x44px preferred on touch.
- Reduced motion: all animation and transition durations collapse to near zero under `prefers-reduced-motion`; no functionality depends on motion.
- Forced colors: borders, focus rings, and status text remain visible in Windows High Contrast mode.
- Zoom and reflow: no content loss at 200% zoom; 320px minimum width with intentional mobile composition.
- Reader: reading text honors user font size, CJK line-breaking, and a high-contrast reading surface in all three themes.
- Admin tables: readable at compact density, sortable headers, text-based statuses.
- Language and title labeling: `lang` reflects document language; every page has a meaningful title.
- Automated checks cover token contrast, focus-visible CSS presence, and reduced-motion CSS. Screen-reader, forced-colors, 200% zoom, touch target, and keyboard walkthroughs are manual acceptance (DEBT-FE-01A).

## 12. Responsive Behavior

- 320px: minimum supported; mobile shell with tab bar; grids collapse to single column; tables become scroll containers or lists.
- 640px (`sm`): two-column card grids begin.
- 768px (`md`): public shell switches from tab bar to full header; library board view is the desktop default.
- 1024px (`lg`): three-column grids; novel detail gains the sticky cover column; account gains the fixed sidebar; admin gains the fixed sidebar.
- 1280px (`xl`): max content width reached; hero sections complete their asymmetric composition.
- 1440px: standard desktop composition width for Stitch briefs.
- 1536px (`2xl`): ultra-wide; content stays within max widths.

Mobile composition is an intentional re-architecture, not a stacked desktop layout: priority order, hidden non-essential regions, transformed fixed bars, and touch-sized targets are specified per page.

## 13. Motion and Graphics

Approved motion ladder, reflected at the current post-overhaul level:

1. No motion: reader body text, dense admin tables, critical operator buttons, reduced-motion state.
2. CSS transitions only: hover color, focus rings, tab changes, card outline hover (120 to 300ms, no springs).
3. Native View Transition API where it gracefully degrades; never required for function.
4. Motion (framer-motion) only for isolated presence transitions such as dialog and search overlay enter and exit, with reduced-motion handling and dynamic import.
5. GSAP only for an approved single brand sequence; none exists today.
6. Three.js and WebGL are prohibited without explicit owner authorization.

Current implementation uses CSS transitions and native browser behavior only. No decorative animation: no word-by-word reading animation, no scroll hijacking, no marquees, no scale-and-tilt hover on cards. Hover effects apply only on hover-capable devices.

## 14. Content and Copy

- Voice: public copy is warm, clear, and respectful of the reading experience; admin copy is operational and precise.
- Protected navigation labels: Home, Browse, Request, Library (public header and tab bar); Account (mobile tab); Ranking, Contribute, FAQ, News, About, Support, Legal, Privacy, Terms, DMCA, Contact, Cookie Policy (footer). Admin sidebar labels: Home, Add Novel, Library, Activity Log, Scheduler, Maintenance, Analytics, Requests, Reviews, Users, Editor, Credentials, Settings, Audit Log.
- CTA consistency: "Start Reading" for the first readable chapter; "Sign In" and "Sign up" as auth actions; "Continue with Google" for OAuth; destructive verbs are explicit ("Remove", "Delete", "Reject", "Clear State").
- Error copy: safe, no stack traces, no internal paths, no IDs. Generic fallback: "Something went wrong. Please try again later."
- Empty-state copy: explain why it is empty and give a recovery action.
- No fake claims: never present simulated numbers, fake reviews, or invented ranking data. Unavailable features say "not available yet".
- No em dashes or en dashes in generated interface copy.
- CJK copy wraps safely; Japanese titles display in the literary serif; original Japanese title is secondary to the translated title.
- Dynamic content slots in briefs use bracketed placeholders such as [Novel title], [Original Japanese title], [Chapter count], [Publication status], [Updated date].
- Legal copy is frozen; briefs reference protected labels and required excerpts only, never restate full legal text.
- Dates and numbers format per visitor locale; relative time for recent events.

## 15. Anti-Slop Rules

Prohibited patterns (TasteSkill-derived, enforced project-wide):

- No generic SaaS hero with dual CTAs.
- No mesh-gradient blobs, radial blobs, or ambient blurred circles.
- No every-section-in-a-card layout; use paper space and structural dividers.
- No excessive pills, rounded containers, or decorative status dots.
- No fake product UI, fake metrics, or fake rankings.
- No generic marketing copy ("seamless", "unlock", "elevate", "cutting-edge").
- No arbitrary monospace uppercase eyebrows above every section.
- No decorative vertical Japanese text as a page motif (the home hero retired this pattern).
- No public motifs in admin; admin never uses lantern badges, sakura accents, or literary borders.
- Reader surface is calmer than discovery; no animation used as decoration.
- No default component-library appearance; every control is themed to the Dokushodo contract.
- No glassmorphism on static surfaces.

PR #38 retired patterns: multi-layer hero gradients, the radial blob, decorative vertical Japanese text on the hero, duplicate browse entry points, duplicate start-reading CTAs, and nested interactive card links.

## 16. SEO and Metadata

- Root metadata: site name Dokushodo, default title "Dokushodo", template "%s | Dokushodo", public description, Open Graph type website, default OG image, Twitter summary_large_image.
- Route metadata: every page provides a title and description; browse-style routes emit canonical URLs; search and filter-heavy pages are noindex where appropriate; source pages index only when the source provably has novels.
- Robots: index rules per route; 404 and error routes are noindex.
- Sitemap and robots routes exist and list public routes.
- Dynamic metadata: novel pages use novel data for title and description; chapter routes carry chapter identity in metadata.
- Heading hierarchy: one h1 per page matching the visual title; h2 sections; visual and semantic hierarchy agree.
- Internal anchors: chapter rows and jump links ("First unread", "Latest") are real anchors with stable ids.
- Page briefs state visual heading requirements but never technical SEO implementation details.

## 17. Reference Principles

WTR-Lab is recorded only as a domain reference for the reading experience.

- Adapted principles: quiet chrome, restrained literary motifs, honest data presentation, reader-first typography.
- Rejected patterns: WTR-Lab-style monetization, ranking gimmicks, social proof widgets, and any import of unsupported metrics.
- No visual copying of WTR-Lab assets or layouts; the Dokushodo identity is original.
- WTR-Lab is never used as an admin design reference.

## 18. Stitch Page-Brief Protocol

- Each page file under `docs/design/public/` or `docs/design/admin/` is standalone.
- Copy the entire page file into Stitch to generate the page design.
- Every brief repeats a compact Global Visual Snapshot (approximately 150 to 300 words) so it works without `docs/DESIGN.md`.
- The repeated snapshot is render context, not a second authority; `docs/DESIGN.md` remains canonical.
- Briefs contain no code, API references, tests, or implementation details.
- Briefs request one desktop composition at 1440px and one mobile composition at 390px.
- The normal settled state is the primary generated image; important alternate states are requested as additional frames, at most three.

## 19. Page Index

### 19.1 Public pages

| Page | Route(s) | Stitch brief | Availability | Primary state | Alternate visual states |
|---|---|---|---|---|---|
| Home | `/home` | `public/home.md` | Implemented | Settled rails and spotlight | Loading, empty |
| Browse novels | `/browse-novels` | `public/browse-novels.md` | Implemented | Settled catalog grid | Loading, empty, error |
| Genre | `/genres/[genre]` | `public/genre.md` | Implemented | Settled filtered grid | Empty |
| Tag | `/tags/[tag]` | `public/tag.md` | Implemented | Settled filtered grid | Empty |
| Source | `/sources/[sourceKey]` | `public/source.md` | Implemented | Settled filtered grid | Empty |
| Novel detail | `/novels/[slug]` | `public/novel-detail.md` | Implemented | Overview tab settled | Chapters tab, loading, not found |
| Chapter reader | `/novels/[slug]/chapter/[chapterId]` | `public/chapter-reader.md` | Implemented | Reading surface | Loading, chapter unavailable |
| Ranking | `/ranking` | `public/ranking.md` | Implemented (unavailable state) | "Rankings are not live" state | None |
| Request novel | `/request-novel` | `public/request-novel.md` | Implemented | Settled form | Empty history |
| Contribute | `/contribute` | `public/contribute.md` | Implemented | Gated informational state | None |
| Account overview | `/account` | `public/account-overview.md` | Implemented | Settled summary cards | Loading |
| Account library | `/account/library` | `public/account-library.md` | Implemented | Board view settled | List view, empty, guest prompt |
| Account history | `/account/history` | `public/account-history.md` | Implemented | Settled list | Empty, error, guest prompt |
| Account notifications | `/account/notifications` | `public/account-notifications.md` | Implemented | Settled activity list | Empty |
| Account requests | `/account/requests` | `public/account-requests.md` | Implemented | Settled history table | Empty |
| Account reviews | `/account/reviews` | `public/account-reviews.md` | Implemented | Settled review list | Empty, delete confirmation |
| Account contributions | `/account/contributions` | `public/account-contributions.md` | Implemented | Gated unavailable state | None |
| Account settings | `/account/settings` | `public/account-settings.md` | Implemented | Settled settings panels | None |
| Login | `/login` | `public/login.md` | Implemented | Sign-in state | Sign-up state, OAuth unavailable |
| Logout | `/logout` | `public/logout.md` | Implemented | Signing-out state | None |
| Auth callback | `/auth/callback` | `public/auth-callback.md` | Implemented | Processing state | None |
| About | `/about` | `public/about.md` | Implemented | Settled article | None |
| Contact | `/contact` | `public/contact.md` | Implemented | Settled form | Success, error |
| Cookie policy | `/cookie-policy` | `public/cookie-policy.md` | Implemented | Settled article | None |
| DMCA | `/dmca` | `public/dmca.md` | Implemented | Settled form | Success |
| FAQ | `/faq` | `public/faq.md` | Implemented | Settled article | None |
| Legal | `/legal` | `public/legal.md` | Implemented | Settled article | None |
| Maintenance | `/maintenance` | `public/maintenance.md` | Implemented (status page) | Status surface | None |
| News | `/news` | `public/news.md` | Implemented | Settled article | None |
| Not found | `/not-found` (global 404) | `public/not-found.md` | Implemented | 404 surface | None |
| Error | `/error` (route error) | `public/error.md` | Implemented | Error surface | None |
| Privacy | `/privacy` | `public/privacy.md` | Implemented | Settled article | None |
| Random | `/random` | `public/random.md` | Implemented (runtime redirect) | Redirect surface | Empty recovery |
| Support | `/support` | `public/support.md` | Implemented | Settled article | None |
| Terms | `/terms` | `public/terms.md` | Implemented | Settled article | None |

### 19.2 Admin pages

| Page | Route(s) | Stitch brief | Availability | Primary state | Alternate visual states |
|---|---|---|---|---|---|
| Dashboard | `/admin/dashboard` | `admin/dashboard.md` | Implemented | Settled metrics and worker panel | Worker error |
| Activity log | `/admin/activity` | `admin/activity.md` | Implemented | Settled grouped table | Empty, delete confirmation |
| Activity detail | `/admin/activity/[activityId]` | `admin/activity-detail.md` | Implemented | Settled phase table | Loading |
| Analytics | `/admin/analytics` | `admin/analytics.md` | Implemented | Settled counts | Unavailable groups |
| Audit log | `/admin/audit` | `admin/audit.md` | Implemented | Settled events table | Empty, detail drawer |
| Crawler | `/admin/crawler` | `admin/crawler.md` | Implemented | Settled panels | Run progress dialog, error dialog |
| Credentials | `/admin/credentials` | `admin/credentials.md` | Implemented | Settled table plus form | Empty, delete confirmation |
| Editor | `/admin/editor` | `admin/editor.md` | Implemented | Settled chapter edit | Glossary QA blocked |
| Glossary | `/admin/novels/[novelId]/glossary` | `admin/glossary.md` | Implemented | Settled entries table | Empty, import candidates |
| Library | `/admin/library` | `admin/library.md` | Implemented | Settled novels table | Empty, delete confirmation |
| Maintenance | `/admin/maintenance` | `admin/maintenance.md` | Implemented | Settled tasks table | Error |
| Requests | `/admin/requests` | `admin/requests.md` | Implemented | Settled queue table | Empty, confirmation |
| Reviews | `/admin/reviews` | `admin/reviews.md` | Implemented | Settled moderation table | Empty, confirmation |
| Settings | `/admin/settings` | `admin/settings.md` | Implemented | Settled runtime table | Confirmation |
| Takedowns | `/admin/takedowns` | `admin/takedowns.md` | Implemented | Settled notice cards | Empty, error |
| Scheduler health | `/admin/translation` | `admin/translation.md` | Implemented | Settled models table | Empty |
| Users | `/admin/users` | `admin/users.md` | Implemented | Settled users table | Empty |
| User detail | `/admin/users/[userId]` | `admin/user-detail.md` | Implemented | Settled summary panels | Invalid user |

### 19.3 Redirects and aliases (nonvisual routes, no briefs)

- `/` redirects to `/home`.
- `/admin` redirects to `/admin/dashboard`.
- `/random` resolves a random novel and redirects to `/novels/[slug]`, or to `/browse-novels?notice=empty` when the catalog is empty. Its brief documents the redirect surface it renders while resolving.

## 20. Verification and Maintenance

- Route-to-page coverage: after frontend route changes, regenerate the App Router page inventory and reconcile with the page index. Every rendered page must map to one brief; every brief must map to a real route; uncovered pages and orphan briefs must be zero.
- Global change propagation: when this document changes a global rule, review the Global Visual Snapshot of every brief and update the shared snapshot wording.
- Page review cadence: any merged change to a page's visual composition triggers a review of that page's brief in the same change.
- Dead-file removal: when a route is deleted, delete its brief and remove it from the page index.
- Manual visual review: expected for token, typography, shell, and page-composition changes; record results in `docs/HISTORY.md`.
- Documentation validation commands:

```powershell
# Final design tree
Get-ChildItem -Path "docs\design" -Recurse | Sort-Object FullName | ForEach-Object {
    $_.FullName.Replace((Resolve-Path ".").Path + "\", "")
}

# Required headings in every brief
rg -l "^## (Design Task|Product Context|Global Visual Snapshot|Page Goal|Audience and Access|Primary Action|Information Hierarchy|Desktop Composition|Mobile Composition|Page Anatomy|Key Components|Representative Content|Normal Settled State|Alternate Visual States|Interaction Cues|Accessibility and Legibility|Assets|Preserve Exactly|Avoid|Stitch Output Requirements)" docs/design/public docs/design/admin | Measure-Object

# Implementation residue in briefs
rg -n "frontend/|backend/|npm run|pytest|Vitest|React Query|Zustand|use[A-Z]|query key|API endpoint|Tailwind|className=|\.tsx|\.ts\b" docs/design/public docs/design/admin

# Prohibited punctuation in canonical docs (unicode escapes: EN DASH U+2013, EM DASH U+2014)
rg -n "[\x{2013}\x{2014}]" docs/DESIGN.md docs/design

# Stale canonical links
rg -n "design/shared|design/components|design/templates|design/audits|frontend-v2-implementation-handoff|verification-contract" docs AGENTS.md README.md
```

- Git hygiene: documentation-only commits; `git diff --check`; `graphify update . --no-cluster` after every edit; never modify `frontend/**`, `backend/**`, deployment, database, API contracts, tests, or `.agents/**` during design documentation work.
