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
| Public reader (baseline) | Catalog/detail/chapter routes, availability, SEO, accessibility baseline, performance budget, taxonomy, and annotations implemented locally. The Yokocho Lantern + Layout Rework replacement target is documented in `DESIGN.md` and tracked as `DEBT-FE-01` in `WORK.md`; Phase 1 (tokens, brand metadata, duplicate-CTA removal, dark default) shipped 2026-07-31 — see Frontend Design Phase 1 below. Layout/route rework remains pending. | `DESIGN.md` |
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

## 2026-07-31 Frontend Design Phase 1 (DEBT-FE-01)

Shipped the bounded Phase 1 slice of the Yokocho Lantern + Layout Rework target
(`docs/DESIGN.md`): token swap in `globals.css` (light + dark), semantic
`success`/`warning`/`info` + `--focus-ring` tokens wired to Tailwind, public
surfaces consume tokens (badge, rating stars, notification list, request/review
success states, contributions banner), root metadata brand "Dokushodo",
novel-detail duplicate Start Reading CTA suppressed (`ContinueReading
hasHeroCta`), public theme default dark (respects explicit
`prefers-color-scheme: light`). Layout Rework routes/nav/search and the asset
system remain pending in `WORK.md` as `DEBT-FE-01` Phase 2+; admin surfaces
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

## 2026-07-31 Frontend Phase 2 — FE-02 accessibility (DEBT-FE-01)

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

## 2026-07-31 Frontend Phase 2 — FE-03 navigation (DEBT-FE-01)

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
