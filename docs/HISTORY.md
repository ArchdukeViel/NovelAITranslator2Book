# Project History

Concise record of completed, cancelled, and deferred specifications. Git history
contains full former requirements/design/task documents.

## Completed Specifications

| Specification area | Outcome | Current authority |
|---|---|---|
| Adapter plugins and source ingestion | Registry, adapters, offline fixtures, and safe fetch boundaries implemented. | `ARCHITECTURE.md` |
| Authentication and authorization | Owner/user/guest sessions, OAuth, password auth, CSRF, ownership, and rate limits implemented. | `ARCHITECTURE.md` |
| CI/CD and containers | CI gates, image publication, Compose topology, split services, and smoke tooling implemented. | `DEPLOYMENT.md` |
| S3/R2 storage and recovery | Storage abstraction, independent snapshots, retention, encrypted DB dumps, and restore verification implemented. | `STORAGE.md`, `OPERATIONS.md` |
| Translation chunking and resume | Deterministic paragraphs/chunks, bounded chapter parallelism, checkpoints, delta/resume hardening implemented. | `ARCHITECTURE.md`, `TRANSLATION.md` |
| Translation cache and QA | Exact cache identity, glossary invalidation, deterministic QA, prompt hardening, and advisory LLM-QA baseline implemented. | `TRANSLATION.md` |
| Glossary system | Suggestions, approval, sync, diagnostics, onboarding, revision invalidation, editor QA, and public annotations implemented. | `TRANSLATION.md` |
| Public reader (baseline) | Catalog/detail/chapter routes, availability, SEO, accessibility baseline, performance budget, taxonomy, and annotations implemented locally. The Yokocho Lantern + Layout Rework replacement target is documented in `DESIGN.md` and tracked as `DEBT-FE-01` in `WORK.md`; FE-01 (tokens, brand metadata, duplicate-CTA removal, dark default) shipped 2026-07-31 — see Frontend FE-01 below. Layout/route rework remains pending. | `DESIGN.md` |
| Admin operations | Users, audit, analytics, metrics, notifications, credentials, requests, health, and library summary implemented locally. | `ARCHITECTURE.md`, `OPERATIONS.md` |
| Legal workflow | Contact/support/legal pages, DMCA intake, owner review, audit, HTTP 451, sitemap/cache enforcement implemented locally. | `ARCHITECTURE.md`, `DESIGN.md` |
| Scheduler durability | Runtime state persistence, cooldown/exhaustion/heartbeat, leases, backup scheduling, and worker observability implemented. | `ARCHITECTURE.md`, `OPERATIONS.md` |
| Maintenance runtime status (DEBT-042) | Every registered cleanup task records durable transitions; owner API/UI reports cron, timezone, last completion, redacted result, and next eligibility. | `ARCHITECTURE.md`, `OPERATIONS.md` |
| Reader missing-asset boundary (DEBT-117) | Existing generated bookplate and asset-independent chapter/library behavior proven across routes; no redundant wrapper added. | `DESIGN.md` |
| Error handling and storage safety | Structured safe errors, logging, atomic JSON writes, file locks, schema tests, and storage boundary consolidation implemented. | `ARCHITECTURE.md`, `STORAGE.md` |

## Cancelled

| Work | Reason |
|---|---|
| PDF/EPUB/HTML/Markdown translated-novel generation | Reader downloads removed from product scope. Input adapters remain. |
| Generated-file manifest UI and freshness scheduler | No generated reader artifacts remain to observe. |
| Historical one-shot operation prompts | Replaced by canonical docs, `AGENTS.md`, and bounded active specs. |
| Render preview provider (DEBT-094) | Preview topology aligned with `ARCHITECTURE.md`: Vercel frontend plus Vercel FastAPI Function in monolith mode. Render monorepo/Blueprint paths and account verification removed; preview acceptance now flows through the Vercel disposable preview described in `ARCHITECTURE.md` and `DEPLOYMENT.md`. |

## Deferred Ideas

| Idea | Activation condition |
|---|---|
| Semantic cache | Approved evaluation, embedding/index, isolation, idempotency, and cost contract. |
| Expanded advisory LLM QA | Structured review-only findings and bounded provider/cost policy. |
| Contribution credentials | Full readiness gate in `ARCHITECTURE.md`. |
| Community and rankings | Public moderation, abuse controls, and trustworthy metrics. |

## Documentation Consolidation

Detailed completed/cancelled specs and archived prompts were collapsed into this
file because they were stale planning artifacts. Git remains the lossless record.

## 2026-07-29 Validation Evidence

Implementation commit: `184be8c`.

| Check | Result |
|---|---|
| Focused backend Ruff | Passed, 9 paths. |
| Backend Pyright | Passed, 0 errors, 0 warnings. |
| Maintenance/scheduler/lease tests | Passed, 46 tests; one pre-existing event-loop deprecation warning. |
| Reader and maintenance frontend tests | Passed, 98 tests across 5 files. |
| Frontend typecheck | Passed. |
| Frontend production build | Passed; `/admin/maintenance` generated successfully. |
| Router dependency guard | Passed with zero matches. |
| Graphify source refresh | Completed with 10,880 nodes and 32,345 edges. |

## 2026-07-30 Hardening Completion

Implementation commit: `98b1049`.

| Check | Result |
|---|---|
| Backend Ruff | Passed. |
| Focused backup, health, settings, and production-config tests | 72 passed. |
| Backend Pyright | 0 errors, 0 warnings. |
| Local smoke | Passed all public checks; production mode rejected missing cookie, conflicting modes, and HTTP external targets. |
| Runtime-role verifier (verify-runtime-role.py, 7 checks) | All true. |
| Parser/YAML/router/diff validation | Passed. |
| Security review | ACCEPT. |
| Graphify source refresh | 10,987 nodes, 32,559 edges. |

Closes local hardening: backup-freshness alert `OPERATOR_ALERT_STALE_BACKUP_HOURS`,
restore-freshness `DATABASE_RESTORE_VERIFICATION_MAX_AGE_DAYS`, authenticated
production smoke enforcement, external HTTPS monitor (best-effort 5-min schedule, `PRODUCTION_BASE_URL`
GitHub secret), rollback compatibility blocking gate, transactional runtime-role
verifier, parser/YAML/router/diff validation, security review.
Does not change launch `NO-GO` or satisfy hosted/manual gates in `WORK.md`.

## 2026-07-30 Tooling Completion

| Check | Result |
|---|---|
| Request body limits enforced | Auth 64 KiB, JSON 1 MiB, analytics 32 KiB default, Caddy 34 MiB outer guard. 413/415 per endpoint. |
| GitGuardian CI workflow | `.github/workflows/gitguardian.yaml`: push/same-repository-PR full-history scan, `ggshield` v1.52.2 pinned, owner-configured `GITGUARDIAN_API_KEY` secret reference, read-only token; fork PRs skip secret-backed scanning. |

Closes local request-boundary enforcement and GitGuardian workflow integration.
PR #12 proved successful secret-backed push and same-repository PR scans.
Required-check protection was configured and proven later (GH-001, PR #15 —
see below); sanitized incident/false-positive triage remains operator evidence.

## 2026-07-31 Frontend FE-01 (DEBT-FE-01)

Shipped the bounded FE-01 slice of the Yokocho Lantern + Layout Rework target
(`docs/DESIGN.md`): token swap in `globals.css` (light + dark), semantic
`success`/`warning`/`info` + `--focus-ring` tokens wired to Tailwind, public
surfaces consume tokens (badge, rating stars, notification list, request/review
success states, contributions banner), root metadata brand "Dokushodo",
novel-detail duplicate Start Reading CTA suppressed (`ContinueReading
hasHeroCta`), public theme default dark (respects explicit
`prefers-color-scheme: light`). Layout Rework routes/nav/search and the asset
system remain pending in `WORK.md` as `DEBT-FE-01` FE-02+; admin surfaces
intentionally unchanged.

| Check | Result |
|---|---|
| Frontend Vitest | 63 files, 770 tests passed. |
| Frontend typecheck | Passed. |
| Frontend production build | Passed. |
| Backend hosted-preview contract tests | 6 passed. |
| Backend Ruff | Passed. |
| Markdown local-link audit | 0 broken links. |
| Graphify source refresh | 11,035 nodes, 32,658 edges. |

Does not change launch `NO-GO` or satisfy hosted/manual gates in `WORK.md`.

PR #15 (`feat/yokocho-phase1-docs`, base `main`) opened and merged 2026-07-31
(squash): all required checks passed — `GitGuardian scan` (push +
pull_request), `docker-build`, `e2e-tests`,
`Analyze (actions|javascript-typescript|python)`, CodeQL, backend lint/tests,
and frontend-check; Vercel preview deployed. This proved the GH-001
required-check configuration (`GitGuardian scan` required) against a real
same-repository PR. The approving-review requirement was set to `0` because
GitHub forbids PR authors from approving their own pull request and this is a
single-operator repository (see `DEPLOYMENT.md` GitHub Controls). Sanitized
incident/false-positive triage remains operator evidence.

## 2026-07-31 Frontend FE-02 accessibility (DEBT-FE-01)

Token contrast verified programmatically against WCAG AA (4.5:1) for solid
fills, tinted chips, cards, and page backgrounds in both modes — 34 checks,
0 failures. Failures found and fixed during tuning: primary text on lantern
orange (2.23:1 dark), info text (2.94:1 dark), light accent text (3.39:1).
Added context tokens `--{success,warning,info,destructive,primary}-text`
(tinted-chip/inline text, per-mode shade) distinct from `-foreground`
(solid-fill text); destructive-foreground dark on red (4.63:1); light accent
fill rebalanced (340 55% 40%) with near-white accent-foreground (6.4:1).
Primary buttons gained the two-layer focus treatment
(`.bg-primary:focus-visible`: neutral inner ring + `--focus-ring` outer
offset). Components updated to `-text` tokens: badge, notification list,
use-notifications severity badges, contributions banner, rating-review and
request-control success messages, browse filter chips. Admin surfaces
intentionally unchanged per `DESIGN.md`. Validation: typecheck, 770 Vitest
tests, production build all pass. Remaining FE-02 items are manual browser
checks (keyboard, screen reader, 200% zoom, reduced motion) — operator
evidence.

## 2026-07-31 Frontend FE-03 navigation (DEBT-FE-01)

The public hamburger drawer is gone. Desktop (`md:`+) header now shows
inline primary nav — Home, Browse, Request, Library — plus catalog search,
theme toggle, notification bell, and account indicator; no hamburger exists
at any width (DESIGN.md F1/F2). Mobile header shrinks to brand + bell, and
primary navigation moves to a fixed bottom tab bar (Home, Browse, Search,
Library, Account) with `env(safe-area-inset-bottom)` padding. Guest behavior:
Library and Account tabs route to sign-in, preserving the intended
destination via `next` (login page now honors a safe in-app `next` and
returns there on success/close); notification bell is hidden for guests
(never shown disabled/empty). The Account tab doubles as a hub: new `/account`
page for authenticated readers with library shortcuts (Library, History,
Notifications, Requests, Contributions, Settings), a More list (Ranking,
Request Novel, Contribute, About, Support, Legal — only existing routes, per
the honesty principle; FAQ/News join when they ship), theme toggle, and sign
out; guests are redirected to sign-in. Reader quiet-chrome: on `/novels/…/chapter/…`
routes the header, tab bar, and footer are suppressed entirely, leaving only
the reading surface. `/browse-novels?focus=search` (the mobile Search tab)
focuses the catalog search input and strips the param for a clean URL.
`PublicSidebar` and its drawer were deleted. Validation: typecheck, 766 Vitest
tests (new: chrome suppression + shell route coverage, tab-bar guest/auth
hrefs, header nav), production build all pass. Remaining per DESIGN.md:
Search overlay is FE-04 (tab currently lands on browse search); novel-detail
sticky action bar replacing the tab bar is FE-07.

## 2026-08-01 Frontend FE-04 shared search overlay (DEBT-FE-01)

One shared search overlay replaces the separate header search form and the
mobile Search tab's redirect to the catalog page. It is mounted once in
`PublicShell` (outside the reader chrome-suppression block, so `/` and the
overlay work on chapter pages too). Desktop header search field, mobile
Search tab, and the global `/` shortcut all open it; Escape, backdrop click,
or an explicit close restore focus to the opener.

Behavior per DESIGN.md — Search contract: results grouped as Novels, Authors,
Genres & Tags with fuzzy matching on translated and original Japanese titles
plus exact tag matching; debounced 225 ms; a new keystroke aborts the
in-flight request (AbortController) while stale results stay visible until
the fresh response lands, so there is no loading flicker; "no matches"
renders only after a real response; full request failure shows an honest
error state and partial failure keeps whichever groups succeeded
(`Promise.allSettled`). ArrowDown/ArrowUp cycle rows (novels, authors, tags,
genres, always-last "See all results"), Enter opens the highlighted result
(novel detail, author query, tag/genre filter, or full results), and Enter
with nothing highlighted opens `/browse-novels?q=…`. An empty query shows
local-only recent searches (localStorage, max 8, case-insensitive dedupe,
min 2 chars, clearable) plus genre shortcuts.

Backend gap closed for the Japanese-title contract: the public catalog now
matches `original_title` in both the DB path
(`Novel.title | Novel.original_title | Novel.author`) and the
storage-fallback `novel_matches_search`, covered by new tests in
`test_public_router.py`. Validation: typecheck, 781 Vitest tests (new:
22-test overlay suite covering open/close, focus return, debounce,
cancellation, no-flicker, error/partial failure, keyboard navigation,
recent-search storage; updated search-entry, tab-bar, and shell suites),
production build, and backend catalog suites (156 tests) all pass.

## 2026-08-01 Frontend FE-05 browse/catalog (DEBT-FE-01)

Browse filters moved from the results-dominating top panel to a desktop left
sidebar. Only its heading and Clear-all action are sticky; filter content
uses normal page scrolling, avoiding adjacent scroll containers. Mobile uses
a bottom-sheet dialog with Escape/backdrop close, an applied-filter count on
the trigger, and pinned Apply/Clear controls. The results header now owns the
count, compact sort control, URL-backed grid/list toggle, and an honest
"Surprise me" action limited to currently loaded novels. Active filters sit
below as individually removable chips; pagination remains explicit and
catalog scroll position restores across detail-page history navigation.

Canonical `/tags/[tag]`, `/genres/[genre]`, and
`/sources/[source-key]` routes reuse the catalog with URL/shareable presets;
search and genre/tag shortcuts now point to those routes. Arbitrary utility
filters on `/browse-novels` are `noindex, follow`, sort/view variants
canonicalize away, and paginated filtered views remain self-canonical.
Source metadata fails closed for indexing unless a non-empty source catalog
can be proven. Backend catalog gained exact canonical `source_key` filtering
in both SQLAlchemy DB and storage-fallback paths. `/authors/[author-slug]`
remains intentionally absent until the stable identity/alias contract in
`WORK.md` is approved.

Validation: frontend typecheck, 790 Vitest tests across 65 files, production
build (47 routes, including all three new dynamic routes), backend public
router 123 tests, and focused Ruff all pass. Pyright reached one pre-existing
optional-dependency error (`pypdf` unavailable in untouched
`backend/src/novelai/inputs/pdf.py`).

## 2026-08-01 Frontend FE-06 homepage rails (DEBT-FE-01)

Homepage long stack, Reading Paths box, utility grid, and duplicate catalog
CTA were removed. Accessible horizontal rails now cover Continue Reading,
New Releases, Recently Updated, and the one or two genres with the most
translated catalog novels. Rails are labeled regions, keyboard-scroll with
arrow keys, expose visible previous/next controls for pointer and keyboard
focus, honor reduced motion, and retain real See-all links. Guests receive a
quiet sign-in continuation tile; signed-in readers reuse existing history.

The hero now has one Start Reading CTA. Because no admin featured-selection
persistence/API contract exists, it does not falsely label the newest novel
"Featured": it uses a neutral Spotlight label only for an eligible novel
with synopsis and a readable chapter. Manual admin-curated rotation remains
registered in `WORK.md` as the bounded backend dependency.

Catalog sorting gained real `updated_at` support (latest chapter timestamp,
falling back to row/catalog update time) in DB and storage paths. `/random`
uses a count plus one-item random page for uniform selection, redirects
straight to novel detail, and falls back to `/browse-novels?notice=empty`
when no novel is available. Validation: frontend typecheck, 769 Vitest tests
across 67 files, production build (48 routes), backend public-router 125
tests, focused Ruff, and router dependency guard all pass.

## 2026-08-02 Frontend FE-07 novel detail (DEBT-FE-01)

Novel detail now uses a sticky desktop left panel for the bookplate, title,
status, metadata, Save control, and exactly one adaptive Start/Continue CTA.
On mobile, the same action becomes a slim fixed bottom bar and `PublicShell`
suppresses the global mobile tab bar on detail routes, preventing stacked
fixed controls.

Overview, Chapters, and Reviews are URL-backed (`?tab=chapters`) segmented
views. Overview owns synopsis and canonical tag/genre links. Chapters adds
search, ascending/descending order, volume collapse/expand-all, first-unread
and latest anchors, read/last-read markers from account progress, explicit
untranslated rows, and progressive 100-row rendering for long lists. Reviews
contains the existing honest rating/review form; no fake recommendation or
other-reader data was added.

Public chapter summaries still lack added-at and explicit translation-failure
fields, and no public other-reader review-list endpoint/pagination contract
exists. New/Failed markers and review lists remain registered in `WORK.md`
across 67 files, and production build (48 routes) all pass.

## 2026-08-02 Frontend FE-08 chapter reader (DEBT-FE-01)

Reader typography/theme/width controls moved from inline chrome into one
thumb-reachable floating Aa button above the safe area. Its sheet provides
the exact supported sizes (16/18/20/22px), widths (Narrow 560px, Standard
680px, Wide 800px), light/dark/sepia themes, and reset-to-18px/Standard while
preserving the saved reader theme. The sheet documents `←`, `→`, and `.`
shortcuts and tells guests that position remains local to this device.

A fixed 3px progress bar tracks real document scroll. Signed-in readers
restore and debounce-save account progress, with immediate pagehide flush;
guests restore/save the same percentage in localStorage. Resume waits for
layout paint and performs a one-shot resize correction, while font/width
changes recalculate percentage against the new layout. Arrow keys navigate
chapters outside editable controls. Top and bottom navigation remain, with
the bottom row explicitly reading Previous chapter · Back to novel · Next
chapter and promoting Next as the strongest end-of-chapter action.

Validation: frontend typecheck, 785 Vitest tests across 68 files (including
Aa choices/shortcut/reset/disclosure, account and guest resume, live progress,
keyboard navigation), and production build (48 routes) all pass.

## 2026-08-02 Frontend FE-09 library board/list and account shell (DEBT-FE-01)

The account area gained a desktop sidebar (Library, History, Notifications,
Requests, Contributions, Settings) with active-route highlighting. Reviews and
Support render as honest non-link "Unavailable" rows because no public
contract exists for them.

The account landing page shows an honest summary sourced only from existing
APIs: currently-reading and total-library counts from `useLibrary`, reading
history and most-recent activity from `useHistory`, unread notifications from
`useUnreadCount`. No counts or fields were invented.

The library page is a board/list of the user's saved novels: five named
groups (Reading, Plan to read, Completed, Dropped, Unknown) derived from
existing library status values, client-side slug search, client sort (title
asc/desc, added asc/desc), board presentation on desktop (md+) and list on
mobile with an explicit Board/List toggle, per-item Remove through the
existing remove-from-library mutation, and an empty-state CTA back to
`/browse-novels`.

Because the backend lacks plan-to-read/dropped status mutation, bulk status
update, and progress/title/recent-update fields/filter/badge on the public
library payload, the UI groups by existing status only and exposes no fake
controls, counts, or badges. These stay registered in `WORK.md` as bounded
backend contracts.

Final branch validation at `8759969`: frontend Vitest 809 tests across 70 files,
lint, typecheck, and 47-page production build all pass. Focused coverage includes
library-board.test.tsx and account-desktop-shell.test.tsx for group routing,
search, sort, view toggle and media default, empty state, remove mutation,
sidebar navigation/active state, and landing summary counts. GitHub CI and
GitGuardian also pass at that HEAD. Branch remains unmerged.

Follow-up audit added a persistent FE-02 token regression test for all 34
documented WCAG AA pairs, then fixed two account-shell defects: unauthenticated deep account
routes now preserve their exact pathname through sign-in, and the shell no
longer nests a `main` landmark around child pages that own their own `main`.
Focused tests cover both regressions. `WORK.md` and `DESIGN.md` status blocks
were also reconciled with shipped FE-09 evidence; gated backend, operator, and
asset work remains active rather than being represented by fake UI. Final
follow-up validation: frontend lint and typecheck passed, 813 Vitest tests
across 71 files passed, and production build generated 47 pages.

## 2026-08-02 Frontend FE-10 — FAQ, news, and account reviews (DEBT-FE-01)

Renamed the "Phase 1" slice label to `FE-01` throughout the docs to match the
FE-02..FE-09 slice naming already in use (DESIGN.md, WORK.md, HISTORY.md).

Shipped the remaining FE-10 routes from `docs/DESIGN.md`:

- `/faq` — flat categorized Q&A, no auth, built on the shared `StaticPage`;
  linked from the footer and the mobile Account More hub.
- `/news` — flat dated list, no auth, built on `StaticPage`; linked from the
  footer and the mobile Account More hub.
- `/account/reviews` — lists the signed-in reader's own reviews with novel
  title links, star rating, review body, an "Edit review" link to the novel's
  reviews tab (`/novels/[slug]?tab=reviews`), and removal through the existing
  delete-review mutation. Auth-gated like the other account pages; honest
  loading/error/empty states. New: status badge shows each review's moderation
  state (Pending / Published / Not published).
- Backend `GET /api/user/reviews` — new session-scoped endpoint returning the
  current user's reviews with novel slug/title, newest first
  (`ReviewService.list_user_reviews`). `useDeleteReview` now also invalidates
  the my-reviews query.
- Desktop account sidebar: Reviews moved from the "Unavailable" list to a real
  link (Support remains the only unavailable row). Mobile More hub now lists
  Ranking, Request Novel, Contribute, FAQ, News, About, Support, and Legal per
  DESIGN.md's hub contract; footer Read column gained FAQ and News.

Validation: backend `test_user_data_router.py` 45 tests pass (added guard entry
for the new GET route plus a contract test proving per-user scoping and novel
metadata); frontend typecheck, lint, and focused Vitest suites pass (account
reviews page, account shell, navigation consistency, metadata); full Vitest
suite (820 tests / 72 files) and production build (50 pages) pass. The GET
endpoint carries no rate limit, matching sibling user-data GETs
(`/library`, `/history`, `/requests`), and its `status`/`updated_at` fields
keep the existing hardcoded `pending`/`created_at` contract shared with
`PUT /api/user/reviews/{slug}` — a real review-status column awaits the
approved visibility/moderation contract. Remaining gated items
(public review-list pagination, visibility/moderation contract) stay open in
`WORK.md`; no surface is faked.

## 2026-08-02 Review moderation contract (solve the risks)

Closed the remaining FE-10 risks from WORK.md DEBT-FE-01 / DEBT-REV-01.

- DB migration `c3a7e9f5b1d2_add_review_moderation_fields`: `reviews.status`
  (pending|published|rejected, default pending), `updated_at` (real,
  backfilled from created_at), `moderated_at`, `reviewer_notes`,
  `reviewed_by_user_id`; indexes on status and (novel_id, status). Backfill:
  status defaults to pending for existing rows.
- `Review` ORM model updated to match.
- `ReviewService`: `upsert_review` resets status → pending + clears moderation
  fields + sets real updated_at on every edit; `_review_response`/`list_user_reviews`
  expose real status/updated_at; new `list_published_reviews` (keyset cursor
  pagination, published only, no user_id or status in public items — per
  DEBT-REV-01 rule 4); new `list_all_reviews` (owner admin list with novel
  metadata + pagination, mirrors `TakedownService.list_requests`); new
  `moderate_review` (validates {published,rejected}, sets moderated_at/notes).
- Public route `GET /api/public/novels/{slug}/reviews`: guest-accessible,
  404 on unknown novel, 451 on active takedown, Cache-Control public max-age=60,
  `{items, next_cursor}` shape with limit 1-50.
- Admin router `admin_reviews.py`: `GET /api/admin/reviews` (owner-only list +
  filters) and `POST /api/admin/reviews/{review_id}/review` (status/reviewer_notes,
  400 invalid, 404 missing), mirrors `admin_takedown.py` structure including CSRF
  dependency and audit via `AuditService.log("review.moderated", ...)`.
- `user_data.py` PUT/DELETE /reviews/{slug}: emit `AuditService.log` with
  action `"review.written"` / `"review.deleted"`, actor = session user,
  target_type="review", metadata {"slug": ...}.
- Admin dashboard sidebar: Reviews link added.
- Frontend: novel-detail Reviews tab now shows community reviews (published only;
  "Load more" cursor pagination; honest empty state; no author identity).
  Account reviews page shows status badges. Admin Reviews page for moderation.
  `publicApi.novelReviews()` + `useNovelReviews` hook with upsert/delete cache
  invalidation.

Existing reviews backfill to `pending` — honest for pre-moderation rows that
were never shown publicly (no public listing existed). `updated_at` is real;
`created_at` never changes. No gated surface or moderation state is faked.

Validation: backend 74 tests pass (test_review_moderation, test_public_reviews,
test_admin_reviews, test_user_data_router 45 — zero regressions); ruff clean;
pyright unchanged (1 pre-existing pypdf error only); router-layer guard clean.
Frontend 828 Vitest/74 files pass (13 new), typecheck clean, lint clean.

## 2026-08-03 Design System & Frontend Documentation Hardening

Synchronized frontend design documentation with implemented tokens, resolved specification contradictions, hardened shared and component contracts, and formalized reader and asset contracts:

- **Public Design System (`docs/design/public/design-system.md`)**: Rewritten from 36-line stub to comprehensive visual-token contract. Documents all 39 CSS custom properties across light and dark modes, token architecture (fill, foreground, text tiers), canonical semantic status mapping, color usage rules, spacing rhythm, radius variants, elevation layers, z-index layers, typography, motion, accessibility requirements, and implementation mapping.
- **Semantic Status Alignment**: Resolved conflict between `feedback.md` and `admin/design-system.md`. Standardized canonical mapping: success (completed, published, healthy, active), info (running, scheduled, informational), warning (stale, partial, degraded, hiatus), destructive (failed, rejected, deleted, blocked), muted (inactive, dropped, unavailable). Updated `feedback.md`, `admin/design-system.md`, and `content-and-copy.md`.
- **Responsive Breakpoints**: Resolved conflict between `responsive.md` (≥1024px) and `shell.md` (≥768px). Documented standard Tailwind viewport breakpoints alongside explicit "Shell Adaptation Breakpoints" explaining the `md:` (768px) public shell switch.
- **Shared Contracts**: Hardened `interaction.md` (state matrix, async width preservation, shortcut suppression), `accessibility.md` (WCAG 2.2 AA target, non-text contrast, forced colors, live regions, automated vs manual matrix), `responsive.md` (breakpoints, max widths, safe areas), `states.md` (18 canonical states, relationships, component mapping), `content-and-copy.md` (locale formatting, title hierarchy, CJK wrapping, terminology, safe error messages).
- **Component Contracts**: Hardened `forms.md` (input/textarea specs, draft preservation, required fields), `feedback.md` (status badges, alert banners, toasts, skeletons), `dialogs-and-sheets.md` (focus traps, scroll locking, search overlay, destructive confirmation), `cards.md` (token usage, accessibility, states), `navigation.md` (z-index, accessibility, shell adaptation), `README.md` (component index). Added new `buttons.md` (variants, sizes, focus rings, hover states).
- **Reader Contract & Verification**: Updated `chapter-reader.md` with theme token details and contrast requirements. Added `reader-contrast.test.ts` validating light, dark, and sepia contrast pairs. Discovered and fixed sepia secondary contrast defect (`#8a7060` → `#816353`, raising contrast against `#f8f1e4` from 4.09:1 to 4.86:1 for WCAG AA compliance).
- **Assets & Admin System**: Updated `assets.md` to reflect actual PNG asset inventory (`brand-mark.png`, `open-graph.png`, `404.png`, `empty.png`, `maintenance.png`), document PWA/favicon requirements, file-size budgets, and fallback behavior. Hardened `admin/design-system.md` with compact density rules, data table patterns, security/PII masking, and operational status roles.
- **Templates & Status Alignment**: Updated `page.md` and `domain.md` templates with metadata fields for owner, review date, automated tests, manual acceptance, performance, and drift. Updated `docs/DESIGN.md` status index to distinguish contract status, implementation status, automated verification, manual acceptance, active work, and ownership. Updated audit `2026-08-02-public-ui.md` with honest multi-column resolution tracking. Updated `docs/WORK.md` DEBT-FE-01A with forced colors and real-device testing items.

Validation: `reader-contrast.test.ts` passes (6 tests), `token-contrast.test.ts` passes (34 checks), `git diff --check` clean. Does not satisfy manual/hosted acceptance in `WORK.md`.
