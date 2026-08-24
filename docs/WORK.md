# Work

Single source for unfinished, blocked, deferred, and operator-acceptance work.
Resolved work belongs in [`HISTORY.md`](HISTORY.md), not this file.

## Current Decision

**Implementation GO; production acceptance remains open.** The local R2-only
implementation and its backend/static verification are in place, but hosted
security, monitoring, alerting, browser/network acceptance, destructive
cutover evidence, and rollback/restore evidence remain incomplete.

### Recovery continuation — 2026-08-24 (historical recovery record; superseded by the completion slice below)

The synchronized root and deployment environments each passed 7 isolated R2
integration tests. An encrypted PostgreSQL backup was created in the
independent R2 target and restored into the isolated `restore-db` database;
verification reported 37 public tables, 0 invalid constraints, and matching
Alembic metadata. The latest independent R2 object snapshot was read back and
checksum-verified for 980 objects totaling 4,022,175 bytes. The real env files
now contain exactly one synchronized `DATABASE_BACKUP_URL`; the persisted
configuration created and restored the encrypted backup without a process
override. Hosted reader-scale,
provider-canary, full-queue, and production-readiness acceptance remain open.

### Async capacity and resource-efficiency completion slice — 2026-08-24

The authorized execution slice for the two active pipeline specifications is
complete. The bounded provider/R2 canary, independent snapshot and encrypted
restore, private 1k reader-stage execution with its quantified stop, and the
10k/100k dependency-safety decision are recorded in the current evidence
artifacts. The worker remains stopped and the original full queue remains
paused. This closes the specified local and operator-gated evidence work while
preserving the separate production-readiness boundary in the work register.

## Execution Policy

- Launch blockers: `DEBT-075`, `DEBT-079`, ownership, recovery, alerts,
  monitoring, accessibility, performance, SEO, legal propagation, rollback.
- `DEBT-FE-01` FE-02+ is non-launch-blocking unless a changed slice touches
  the launch candidate.
- Enabled feature slices must retain their backend contract, truthful empty
  states, and operator evidence; deferred work remains disabled until its own
  activation gate passes.
- Every evidence record includes candidate commit, environment, UTC time,
  operator, exact command/URL, sanitized result, blocker, waiver, and expiry.
- Work closes only after evidence is recorded in `HISTORY.md`; passing local
  tests never substitutes for hosted/manual evidence.

## R2-only Content Storage Cutover

The approved hard cutover is implemented locally under
[`R2-ONLY-CONFORMANCE.md`](R2-ONLY-CONFORMANCE.md). It replaces the historical
filesystem/S3-prefix content model with immutable R2 objects in `dokushodo`, exact
PostgreSQL artifact references, Redis/Valkey coordination, and disposable local
runtime state. It also includes incremental backup manifests, protected
garbage collection, and an operator-confirmed reset/repopulation workflow for
the three existing novel identities.

The implementation item is closed locally, but live acceptance is still
partial. At the 2026-08-22 checkpoint, the authorized Supabase migration and
fully paginated reset of both R2 buckets were completed, and all three novels
were repopulated under their existing identities through the authenticated R2
path. The populated legacy S3-compatible application settings were migrated to
the current `R2_*` names and validated for the root and production profiles.
A follow-up writer-frozen namespace migration then moved the 538 live
application objects to numeric `novels/<novel_id>/` prefixes, rewrote database
and nested manifest references, verified logical hashes, and removed the old
slug-prefixed source namespaces. After the bulk worker created seven
pre-existing slug-prefixed objects, the same application migration was rerun
after safe worker quiescence: 5 Kakuyomu objects and 2 Novel18 objects moved,
1 and 2 database references were rewritten, and all 7 old source objects were
deleted only after commit. The old prefixes are now empty and the full
post-migration audit contains only numeric namespaces. Public slugs and URLs
remain unchanged.
NCode chapters 1 and 2 now pass real Gemini translation through the durable
worker path, deterministic QA, R2 readback, and the public reader route. The
authorized three-novel bulk queue is now running or queued, with glossary-gate
bypass explicitly recorded and no cross-provider fallback. At the live
2026-08-22 22:46 UTC refresh, the PostgreSQL chapter projection was
`n2056dn`: 66 complete, 23 failed, 58 pending, and 1 translating;
`n3266mn`: 29 complete and 2 failed; and Kakuyomu: 9 complete, 78 failed, and
1 translating.
The Novel18 activity reached terminal failure on `paragraph_missing` and was
then requeued through `Container.activity_log` at retry count 2. The Kakuyomu
activity was recovered to pending after its expired lease. NCode later reached
a terminal PostgreSQL SSL EOF during final novel persistence and was requeued
through `Container.activity_log` at retry count 4, preserving the failed
attempt in retry history. The source-level lease-heartbeat correction and
blocking-event-loop regression test now pass. The stale worker was stopped
after its lease expired, the rebuilt worker was recreated with restart count
`0`, and the durable queue reclaimed NCode; live lease renewal was observed
after recreation. The runtime directory was renamed from `storage/runtime` to
`data/runtime` only after the active runtime write reached a safe checkpoint
boundary, and the recreated worker was verified with the
`data/runtime -> /app/data/runtime` bind. The old host path is absent, and no
runtime JSON or database row was manually edited.
At the current refresh NCode is running at retry count 4 with a renewed lease
deadline of `2026-08-22T22:50:36Z`, Kakuyomu is pending after recovery from an
expired lease, and Novel18 is failed at retry count 3 with
`paragraph_missing`. The last read-only R2 inventory at 20:23 UTC reports 872
application objects / 3,299,655 bytes and zero backup objects. The rebuilt worker has one
live container/process and restart count `0`; five restarts caused by
transient Supabase DNS failures belong to the superseded worker instance.
The post-migration per-prefix audit reports `novels/11/` 424 objects,
`novels/16/` 248 objects, and `novels/17/` 200 objects, with no nonnumeric or
other prefix; direct database references to the two old source namespaces are
zero.
Bulk translation and the
remaining published chapter reads,
production telemetry, and backup/restore remain explicit acceptance gates. A
live duplicate audit found
two older unpublished PostgreSQL rows (IDs 18 and 19) for source URLs already
represented by canonical active rows (IDs 11, 16, and 17); after reference
verification those stale rows and their tag associations were removed. The R2
prefix cleanup now snapshots paginated keys before deletion; its focused suite
passes 8 tests, and a stopped synthetic Phase 6 seed was fully cleaned without
leaving R2 objects or database rows. Production-scale telemetry remains open.
The conformance ledger now records the measured per-novel R2 shape; logical
uncompressed bytes and compression savings are measured by a read-only
full-object verifier. Repeated-crawl counters, deduplicated asset savings, and
backup reuse remain unmeasured rather than inferred from object counts. Focused
takedown and public-isolation coverage passes 150 tests; hosted CDN/public
origin propagation remains an operator acceptance gate. The focused R2
catalog/cutover suite also passes 10 tests, including unchanged-recrawl no-op
and incremental-backup reuse behavior.
The live Supabase performance advisor's missing `novel_requests.chapter_id`
foreign-key index was resolved by migration `c9d1e3f5a7b9`; remaining unused-
index notices are informational. A Cloudflare control-plane audit independently
confirmed that exactly `dokushodo` and `dokushodo-backup` exist with the
intended lifecycle policies; recovery remains disabled by operator decision.
The runtime storage factory now exposes only explicit R2 client names and no
generic filesystem/S3 selection or compatibility alias remains.
The earlier authorized attempt to create separate R2 snapshot credentials
through the connected Cloudflare API returned `9109 Unauthorized`. The
operator subsequently supplied separate source-read and backup-write
credentials, rotated the application credentials, and the ignored root `.env`
was synchronized with `deploy/.env`; the six active R2 credential assignments
now match. The 2026-08-24 recovery continuation verified the independent
backup target and an isolated encrypted database restore. The repository
inventory path and an isolated
source-read client then successfully listed the application bucket, while the
backup-target credential listed the empty backup bucket; no object was written
or deleted. After service recreation with the rotated application credentials,
the public catalog, rankings, published details, translated chapter 1, Novel18
isolation, and singular legacy-route rejection passed. Target write permission,
target write permission and restore evidence now pass in the bounded local
drill; production readiness remains open. The local readiness probe is still
503 because disk is unhealthy and the worker probe is degraded.
A translation workload audit estimated 267 provider chunks across the 267
imported chapters. The replacement environment key is now imported into the
unified `provider_credentials` registry as one encrypted, active, valid,
owner-job-eligible row; no user-contribution rows exist. The current persisted
translated-artifact counts are Kakuyomu 17/88, Novel18 29/31, and NCode 60/148
while the bulk queue continues. The configured RPM/TPM/RPD values are local
admission guards; upstream account/project limits must still be verified in
Google AI Studio before production-volume work.

The legacy `contributor_credentials` table is absent. The unified registry
preserves owner and user identity on each row while independent eligibility
flags prevent a user key from entering owner-only work and prevent an owner
key from entering the contributor pool unless an owner explicitly shares it.

## Novel Detail Stage B Decision (2026-08-19)

The public novel detail redesign keeps the existing Overview, Chapters, and
Reviews contract and makes the first viewport reading-first. Recommendations
remain deferred because the current public catalog API has no bounded related-
novel contract. Do not add a fourth tab, behavioral language, popularity
metrics, or a client-side catalog download to simulate one. A future related-
novel slice needs an approved public contract with deterministic exclusions,
stable ordering, and bounded work before it reaches the page.

## Launch Roadmap

Dependency-ordered plan. Each row closes only when its "Done when" evidence
exists and is recorded in `HISTORY.md`.

| Order | ID | Work | Dependency | Done when |
|---:|---|---|---|---|
| 1 | OWN-001 | Assign launch, rollback, monitoring, security, recovery, accessibility, performance, SEO, legal owners | None | All nine gates owned by single operator (email on file in operator record, not committed); legal owner = operator for now; no backup contacts — accepted as waiver-eligible single-operator risk, expiry at GO-001; no unowned gate |
| 2 | REL-001 | Freeze exact candidate | OWN-001 | Candidate commit/image tags, domains, environment, UTC time recorded |
| 3 | GH-001 | Finish GitHub controls | REL-001 | `main` protected; exact CI, CodeQL, and GitGuardian checks required; no force push/deletion; sanitized secret-scan incident/false-positive exercise recorded |
| 4 | DEBT-079A | Deploy always-on candidate | REL-001 | Migrations one-shot succeeds; immutable images run; production config validated (COMPLETED 2026-08-17) |
| 5 | DEBT-079B | Hosted auth/security smoke | DEBT-079A | OAuth, cookies, CSRF, CORS, hosts, roles, disabled users, admin/reader boundaries pass (COMPLETED 2026-08-17) |
| 6 | DEBT-075A | Verify hosted PostgreSQL/R2 workflow | DEBT-079A | Managed-services workflow passes against isolated targets (COMPLETED 2026-08-17) |
| 7 | DEBT-075B | Current-head recovery drill | DEBT-075A | User-deferred for the current R2 cutover; do not claim DB/object restore evidence until separately authorized and recorded |
| 8 | DEBT-118 | Activate and verify SMTP | DEBT-079A | Domain/SPF/DKIM/DMARC, auth mail, bounce/error handling, redaction, limits, `noop` rollback proven |
| 9 | DEBT-075C | Real operator alert | DEBT-118 | Stale/failure alert delivered; threshold, cooldown, redaction, escalation proven |
| 10 | DEBT-079C | External monitoring | DEBT-079A, OWN-001 | Scheduled runs, dashboard, operator delivery, escalation ownership proven |
| 11 | DEBT-FE-01A | FE-01 manual acceptance | DEBT-079A | Keyboard, screen reader, 200% zoom, reduced motion, focus, contrast verified on shipped tokens; operator physical acceptance complete (COMPLETED 2026-08-17) |
| 12 | DEBT-079D | Performance/SEO/legal acceptance | DEBT-079A | Minimal real staging fixtures populated across 3 source adapters; adult gating proven; payload size budgets met; hosted latency budget blocked on remote network topology / WAN latency to Supabase SG & R2 (FAIL / BLOCKED 2026-08-17) |
| 13 | DEBT-079E | Rollback rehearsal | DEBT-075B, DEBT-079B | Worker/scheduler paused, reader disabled, cache purged, prior image compatibility checked, redeployed, smoke rerun |
| 14 | GO-001 | Final launch decision | All above | Zero unwaived blockers; launch/rollback/monitoring owners named |

## Candidate Freeze (REL-001)

Recorded 2026-07-31T17:13:13Z; re-frozen 2026-07-31T17:52:47Z on merged
`main` (PR #15 squash).

| Field | Value |
|---|---|
| Candidate commit (`main`) | `d4a4e8bf98ce4ed54555ffb637475206412f314e` (`d4a4e8b`) — PR #15 squash merge |
| Working tree | Clean |
| Image tag convention | `sha-<full commit SHA>` (`deploy.yml`) — this candidate: `sha-d4a4e8b…` |
| Environment | Production: always-on Docker Compose — Caddy, admin 8000, reader 8001, frontend 3000, PostgreSQL (Supabase), Redis, R2, SMTP (`DEPLOYMENT.md`) |
| Domains | PENDING — operator records hosted domain; `PRODUCTION_BASE_URL` GitHub secret |
| Candidate status | FROZEN (merged to `main`); `DEBT-079A` deploy blocked on domains |

## GitHub Controls Audit (GH-001)

Read-only audit 2026-07-31T17:13:13Z via
`gh api repos/ArchdukeViel/NovelAITranslator2Book/branches/main/protection`.

Present: branch protected; strict required checks (`docker-build`, `e2e-tests`,
`Analyze (actions)`, `Analyze (javascript-typescript)`, `Analyze (python)`);
enforce-admins; linear history; force-push/deletion blocked; conversation
resolution required.

Gaps:

- Required approving review count is `0` — set to `>= 1` (`DEPLOYMENT.md`
  requires PR review).
- `GitGuardian scan` is not in required status checks — add after it runs on a
  PR.
- Fork PRs intentionally skipped (secrets not passed to untrusted code);
  native GitGuardian scan on forks is a fork-owner action.

Resolved 2026-07-31T17:17:41Z: `PUT
/branches/main/protection` set `required_approving_review_count = 1` and added
`GitGuardian scan` to required status checks (verified via `gh api` GET —
contexts: `docker-build`, `e2e-tests`, `Analyze (actions)`,
`Analyze (javascript-typescript)`, `Analyze (python)`, `GitGuardian scan`).

Verified 2026-07-31T17:35:35Z on PR #15 (`feat/yokocho-phase1-docs`, base
`main`): `GitGuardian scan` passed for both push and pull_request runs;
`docker-build`, `e2e-tests`, `Analyze (actions)`,
`Analyze (javascript-typescript)`, `Analyze (python)`, CodeQL, backend
lint/tests, and frontend-check all passed; the hosted preview status was green
at that historical commit.

Revised 2026-08-11: `dependency-review` added to required status checks on `main` branch protection via GitHub API (`strict: true` preserved; contexts: `docker-build`, `e2e-tests`, 3× `Analyze (...)`, `GitGuardian scan`, `dependency-review`). Configured production pre-deployment gate in `deploy.yml` calling `managed-services-verification.yml` (`required: true`). Staging deployments bypass the check via an explicit `!cancelled() && (inputs.environment != 'production' || needs.managed-services-check.result == 'success')` condition.

Revised 2026-07-31T17:46:50Z: `required_approving_review_count` set to `0`
after a merge deadlock — GitHub forbids PR authors from approving their own
pull request and the repository's only write-access user is the PR author, so
review = 1 blocked every merge. All other gates unchanged and verified: PR
required, strict required checks (`docker-build`, `e2e-tests`,
`Analyze (actions|javascript-typescript|python)`, `GitGuardian scan`), CodeQL,
conversation resolution, linear history, no force push/deletion,
enforce-admins. Re-enable review requirements when a second write-access
reviewer exists. Remaining: sanitized incident/false-positive triage exercise
(operator).

Revised 2026-08-08: `main-protection` ruleset (id `20510996`,
`repos/.../rulesets/20510996`) updated to set `require_code_owner_review`
and `require_last_push_approval` to `false` after the same solo-operator
deadlock surfaced via the ruleset (.github/CODEOWNERS exists, but the only
write-access user cannot approve their own PR — verified on PR #41:
`mergeable_state=blocked` with every required check passing). All other
ruleset rules preserved: `deletion`, `pull_request`
(`required_approving_review_count=0`, `required_review_thread_resolution`,
`dismiss_stale_reviews_on_push`), `required_linear_history`,
`non_fast_forward`, enforcement `active` on `refs/heads/main`. PR #41
(`58da35c`, 63 commits) verified `mergeStateStatus=CLEAN` after the change;
merge intentionally deferred. Re-enable both flags when a second
write-access reviewer exists.

## Active Work

## Feature & Design Gaps / Deferred Work (Stitch Screen 1794eb02d11a407b9b6343d727670125)

The following items from the Stitch design spec `1794eb02d11a407b9b6343d727670125` are intentionally deferred or substituted because no backend contract / DB model exists yet:

| Stitch Design Feature | Current Status & Handling in Code | Backend / Contract Dependency |
| --- | --- | --- |
| **User Ticket Leaderboard ("HarvestRam - 4,944 Tickets")** | **Omitted / Deferred**. Replaced by honest `Most Chapters` catalog widget. | Requires user engagement/gamification model (`tickets`, `donations`, `patreon`). Anti-slop rule forbids fake data. |
| **Reader View Counts ("98.5k readers")** | **Omitted from detail/catalog surfaces**. Rankings use the implemented privacy-safe distinct novel-detail-view service; catalog cards still show `translated_count` ("X chapters translated") rather than popularity. | A separate detail-level view-count display contract is intentionally not exposed; ranking data is supplied by `public_novel.view` analytics events. |
| **Manual Admin Spotlight Rotation** | **Catalog Fallback**. Current Spotlight dynamically picks the latest ongoing novel with a synopsis and readable chapter. | Requires `admin_spotlights` or `featured_novels` table + admin curation UI. |
| **Author Detail Route (`/authors/[slug]`)** | **Deferred**. Author names render inline as text without links. | Requires stable `authors` table with author slug, alias mapping, and backend API endpoints. |

## Active Work Plans

Bounded execution plans for active rows. Each plan step lists exact tooling and
evidence; nothing below is completion evidence by itself.

### DEBT-075 — Managed recovery and scheduling

#### A. Managed-service verification

Existing tooling: `.github/workflows/managed-services-verification.yml`,
`backend/tests/integration/test_managed_postgres.py`,
`backend/tests/integration/test_r2_backup_integration.py`.

1. Configure isolated test DB, R2 source bucket/prefix, R2 backup target, and
   separate least-privilege credentials in provider secret storage.
2. Set `MANAGED_SERVICE_TESTS_ENABLED=true`.
3. Run the workflow against the candidate commit.
4. Record workflow URL, commit, UTC time, sanitized counts, and any failures.
5. Confirm source/app/backup credentials cannot perform each other's
   prohibited operations (read/write/delete scope check).

#### B. Current-head restore

Existing tooling:
`backend/src/novelai/services/scheduler_service.py::_run_database_restore_verification`,
`backend/src/novelai/storage/r2_backup.py`,
`deploy/compose.yml` (`restore-db` service), `docs/OPERATIONS.md` restore
procedure.

1. Trigger a fresh object snapshot and encrypted PostgreSQL dump.
2. Verify manifest, last commit, lengths, SHA-256, and backup freshness.
3. Restore storage into an isolated prefix.
4. Restore the DB into a disposable PostgreSQL 18 database whose name contains
   `restore`; never point verification at production.
5. Verify Alembic head, tables, constraints, row counts, representative
   queries, and content.
6. Rebuild catalog projections.
7. Run production smoke against the isolated recovery target.
8. Destroy disposable targets only after evidence is captured.

#### C. Alert closure

Existing tooling: `OperatorAlertService.send`,
`SMTPAuthEmailService`, `backend/tests/test_operator_alert_service.py`,
`backend/tests/test_email_service.py`.

1. Configure SMTP host and operator recipient in provider secret storage.
2. Trigger one real repeated failure until the failure threshold is reached.
3. Confirm exactly one redacted alert after threshold.
4. Trigger again inside cooldown; confirm suppression.
5. Trigger after cooldown; confirm delivery.
6. Trigger the stale-backup alert path.
7. Confirm application/provider logs contain no credentials, token URLs,
   recipient plaintext, internal paths, or traces.
8. Clear the fault and verify scheduler/recovery probes return healthy.

### DEBT-079 — Hosted production acceptance

#### A. Candidate and deployment

Existing tooling: `.github/workflows/deploy.yml`, `deploy/compose.yml`,
`docs/DEPLOYMENT.md`.

1. Select immutable commit/image tags; record domains and exact environment.
2. Verify production config rejects insecure/default settings.
3. Run migration one-shot before services start.
4. Verify admin, reader, worker, frontend, DB, Redis, and R2 roles.
5. Confirm no migration runs inside long-lived containers.

#### B. Hosted smoke and auth/security boundaries

Run authenticated production smoke:

```powershell
deploy/scripts/deploy-smoke.ps1 -BaseUrl "https://<production-domain>" -Production
```

`NOVELAI_SMOKE_SESSION_COOKIE` is ephemeral and never enters evidence. Manual
checks: Google OAuth callback and email/password flow; Secure/SameSite cookie
behavior; CSRF rejection and success paths; explicit CORS and allowed hosts;
owner/user/guest isolation; disabled-user login/session rejection; admin
routes unavailable through the reader process; public responses expose no
paths, hosts, storage keys, traces, credentials, or private details.

#### C. GitHub controls

Existing tooling: `.github/workflows/ci.yml`, `.github/workflows/gitguardian.yaml`,
`.github/workflows/production-monitor.yml`.

1. Protect `main`: PR required, review, resolved conversations, required CI +
   CodeQL + GitGuardian checks, no force push/deletion, owner-only bypass.
2. Verify required-check names match the current workflows (docs do not
   override workflows).
3. Exercise a sanitized test-secret/false-positive triage process without
   committing real secrets.
4. Record evidence via screenshots/API output that exposes no repository
   secrets.

#### D. Monitoring

1. Configure `PRODUCTION_BASE_URL`.
2. Dispatch `production-monitor.yml` and observe scheduled executions over an
   agreed window.
3. Trigger a controlled public failure.
4. Confirm failed workflow run, real operator notification, dashboard
   visibility, and escalation.
5. Restore service; confirm recovery notification/state.
6. Treat GitHub schedule as best-effort, never the sole uptime monitor.

#### E. Manual acceptance

Accessibility: keyboard-only pass; screen-reader landmarks/names/status;
200% zoom and 320px width; reduced motion; focus return/traps; contrast
against actual Yokocho Lantern tokens; primary-button two-layer focus
treatment.

Performance: catalog p95 <= 500 ms and <= 250 KiB; novel p95 <= 300 ms and
<= 100 KiB; chapter p95 <= 750 ms and <= 1 MiB; public first-load JS
<= 250 KiB; long chapter, annotations, cache headers, request counts.

SEO/legal: canonical URLs; robots/sitemap/Open Graph/structured-data
validators; 404 and HTTP 451 excluded from sitemap; HTTP 451 stays `no-store`;
CDN propagation after takedown.

#### F. Rollback rehearsal

1. Snapshot current data.
2. Pause worker and scheduler.
3. Disable public reader.
4. Purge CDN/application cache.
5. Check previous image against current schema (rollback blocking gate).
6. Redeploy previous immutable image only if the compatibility gate passes.
7. Re-run health, auth, reader, takedown, storage, and recovery smoke.
8. If incompatible, keep current image and execute the documented
   forward-fix.
9. Record rollback duration and responsible owner.

#### G. Cross-source hierarchy persistence and long-running crawl acceptance

The backend contract for persisted section hierarchy is now explicit: source
metadata owns optional section fields, raw chapter identity remains stable,
and a reconciliation creates a complete immutable generation before pointer
activation. Reused chapters and their image assets are copied into the new
generation; failed staging preserves the prior active pointer. Long-running
scrape and onboarding-resume requests enqueue durable activities and must be
accepted through activity status plus persisted-generation evidence, not an
open HTTP request.

Acceptance evidence still requires a live persisted representative from
Syosetu, Novel18, and Kakuyomu, including grouped/flat public behavior,
idempotent repeat reconciliation, no body-translation or glossary invalidation
from metadata-only hierarchy changes, and rollback after an injected staging
failure. This subsection records the contract and gate; it is not completion
evidence by itself.

### DEBT-FE-01 — Frontend design rework

Keep the full rework out of one giant change. Bounded slices, one per
PR/change, each with exact tests:

| ID | Slice | Dependency |
|---|---|---|
| FE-02 | FE-01 accessibility: persistent token regression test covers 34 checks across both modes at WCAG AA 4.5:1 + two-layer primary-button focus treatment shipped; manual browser checks (keyboard, screen reader, zoom, reduced motion) pending operator | FE-01 |
| FE-03 | Desktop header inline nav, mobile bottom tab bar, Account/More hub, reader chrome suppression — shipped (typecheck, 766 tests, build pass) | FE-02 |
| FE-04 | Shared search overlay, keyboard behavior, request cancellation, local recent searches — shipped (typecheck, 781 tests, build, backend 156 tests pass); original-title search added to catalog DB + storage fallback | FE-03 |
| FE-05 | Browse/catalog layout, URL filter state, taxonomy/source canonical routes — shipped (typecheck, 790 tests, build, backend public-router 123 tests pass); authors route remains deferred pending stable identity/alias contract | FE-04 |
| FE-06 | Homepage rails and honest featured-novel selection — rails, Continue Reading/guest state, catalog-derived genres, `/random`, real `updated_at` sort, single-CTA eligible Spotlight shipped (typecheck, 769 tests, build, backend public-router 125 tests pass); 2026-08-04 editorial hero upgrade (asymmetric cover card, source title, metadata row, genre chips) + honest NEW chips (14-day `added_at` freshness) shipped (847 tests); manual admin-curated rotation still needs an approved persistence/API contract | FE-05 |
| FE-07 | Novel-detail reading-first hero, semantic URL tabs, truthful metadata, deterministic bookplate fallback, source section hierarchy, chapter search/order/anchors, one reading CTA, quiet report link, and closed request disclosure — Stage B implementation complete; Recommendations remain deferred pending a bounded related-novels contract | FE-03 |
| FE-08 | Reader Aa panel, progress bar, resume position, quiet chrome — shipped (typecheck, 785 tests across 68 files, 48-route build); account progress + guest local-only persistence, keyboard navigation, strong end CTA | FE-03 |
| FE-09 | Library board/list and account shell — shipped (lint, typecheck, 813 tests across 71 files, 47-page build; prior branch CI); pending backend contracts: plan-to-read/dropped status mutation, bulk status update, progress/title/recent-update fields/filter/badge | FE-03 |
| FE-10 | `/faq`, `/news`, account reviews; `/random` and account overview already shipped — shipped (typecheck, lint, Vitest suite, 47+ page build, backend user-data router tests pass); `GET /api/user/reviews` added for the session user's own reviews; review moderation contract (status lifecycle, public listing, admin moderation, audit) implemented and merged | FE-03 |

Rules:

- One slice per PR/change; no slice bundled with unrelated work.
- No `/authors/[author-slug]` until a stable author-identity/alias backend
  contract is approved.
- No fake rankings, recommendations, or community metrics. Contributor UI must
  remain API-backed and truthful; community editing is still out of scope.
- Preserve `docs/DESIGN.md`; update its status only with owner direction.

#### DEBT-FE-01A manual acceptance checklist (operator-evidence only)

This is **manual operator evidence** — cannot be closed by automated tests.
Verify each item in a real browser against the candidate commit on the
`live`/`deployed` URL. Record findings (pass/fail, screenshot reference,
viewport used). All shipped FE-01..FE-10 slices are in scope, including the
new community review list `/novels/[slug]?tab=reviews`,
`/account/reviews`, and `/admin/reviews`.

| # | Item | Viewport / env |
|---|---|---|
| 1 | Keyboard-only: Tab reaches every interactive element (nav links, buttons, star rating, "Load more", delete button, admin Publish/Reject) in DOM order; no keyboard traps. | Desktop 1536×900, Chrome |
| 2 | Screen reader (NVDA/VoiceOver): all interactive elements have accessible names/labels; review rating stars described ("5 stars"); status badges read as their label. | macOS VoiceOver, Safari |
| 3 | 200% zoom: layout, tables, review cards, and forms remain usable; no horizontal scroll that breaks content. | Chrome zoom 200% |
| 4 | 320px width (mobile): tab bar, More hub, and review surfaces reflow; no clipped content. | iOS Simulator 320px |
| 5 | Reduced motion (`prefers-reduced-motion: reduce`): no auto-animation or layout shift; focus indicator transitions disabled. | Chrome devtools |
| 6 | Visible focus indicator: primary-button two-layer focus ring (offset + theme color) visible on all interactive elements. | Dark + light mode |
| 7 | Color contrast: all status badges, text, buttons, and focus rings meet WCAG AA 4.5:1 in light and dark modes — including new "Published"/"Pending"/"Not published" badge colors and star ratings. | axe or manual check |
| 8 | Community review cards: rating star pattern, body text, and date are readable and labeled; "Load more" button announces loading state. | Desktop + mobile |
| 9 | New `/admin/reviews` table: sortable headers, checkbox selection, Publish/Reject buttons, confirm dialog — all keyboard/mouse operable; audit-notice acknowledged. | Desktop |
| 10 | Forced colors mode (Windows High Contrast): borders, focus rings, status badges, and input boundaries remain visible. | Windows High Contrast |
| 11 | Real-device mobile testing: tab bar, bottom sheets, gesture-bar safe areas, and reader controls functional on actual iOS/Android browsers. | Physical phone / tablet |

Status: COMPLETED 2026-08-17 (Automated AX & responsive suite passed; operator attested physical mobile and native screen-reader acceptance).

Per-slice validation:

```powershell
npm run typecheck --prefix frontend
npm run test --prefix frontend -- --run
npm run build --prefix frontend
graphify update . --no-cluster
```

## Operator Acceptance

| Gate | Status | Required evidence |
|---|---|---|
| Hosted smoke and auth/security boundaries | Blocked | Candidate commit, domains, UTC time, commands/URLs, sanitized results. |
| Secret scanning | Partial (hosted scans passed) | PR #12 proved successful GitGuardian push and same-repo PR checks. Still require protected required-check configuration and sanitized incident/false-positive triage evidence. Fork PRs are intentionally skipped (secrets not passed to untrusted code). |
| Alerts and monitoring | Blocked (tooling complete) | Configure `PRODUCTION_BASE_URL`, prove scheduled external runs and real operator delivery, cooldown/redaction, dashboards, escalation, and ownership. |
| Recovery | Bounded local drill passed; persisted env verified | Current-head encrypted database restore and independent R2 snapshot readback passed in isolated targets. Backup-stale alert threshold, restore-freshness max age, runtime-role verifier, and exactly-once `DATABASE_BACKUP_URL` synchronization are verified. |
| Accessibility | Pass (COMPLETED 2026-08-17) | Keyboard, screen reader, 200% zoom, reduced motion, focus, landmarks, contrast verified via automated test suite and operator physical device attestation. |
| Performance | Partial / Fail (AUDITED 2026-08-17) | Catalog API p95 on hosted staging exceeds hard budget (reader direct p95=1001.60ms, Tailscale HTTPS p95=916.33ms vs <= 500ms budget; driven by cross-region Supabase pooler + object-store metadata-list latency in the pre-cutover measurement). Novel detail and Chapter APIs NOT RUN on hosted staging (no published novel/chapter fixture in DB). First-load JS passes (169.8 KiB <= 250 KiB). |
| SEO | Staging Pass / Production Deferred (AUDITED 2026-08-17) | Staging robots.txt, sitemap.xml, Open Graph / Twitter metadata, canonical URLs verified on staging hostname; production domain SEO validation deferred until public domain cutover. |
| Legal propagation | Pass (AUDITED 2026-08-17) | HTTP 451 legal takedown verified (Cache-Control: no-store, no private info leak); sitemap exclusion & 404 contracts verified; CDN purge deferred to public edge. |
| Rollback | Blocked | Pause worker/scheduler, purge cache, disable reader, redeploy previous immutable version, rerun smoke. |
| Ownership | Assigned | All nine gates owned by single operator; email on file in operator record (not committed). Legal owner: operator (temporary). No rollback/monitoring backup — waiver-eligible single-operator risk: risk = alert/rollback response may not reach a second person; reason = solo operation; mitigation = escalate via hosting provider support line on incident; owner = operator; approver = operator; expiry = GO-001. No unowned gate. |

`GO` requires zero unwaived blockers. A waiver records risk, reason, mitigation,
owner, approver, and expiry. Security bypass, private-content exposure, broken
takedown enforcement, unrecoverable loss, or missing rollback cannot be informal waivers.

## Active Specifications

Only genuinely unfinished specs remain under `.agents/specs/`:

- `launch-readiness-checklist`: operator acceptance above; all five
  implementation tasks remain pending and were not executed by this slice.

The completed `workspace-and-quality-hardening` specification is resolved and
recorded in `HISTORY.md`, alongside the pipeline async and resource-efficiency
specifications; none are listed here as active work.

The remaining active specification is an approved planning record. Its task
checkboxes remain pending until implementation and verification evidence is
recorded.

Task boxes are planning aids, not completion evidence. Architecture, current
code/tests, this file, and operator evidence determine status.

## Deferred Work Plans

Deferred features stay disabled until their activation gate passes. Each plan
names the current baseline, the gate, and the ordered steps.

### DEBT-118 — Email delivery (SMTP)

Nonblocking while `AUTH_EMAIL_DELIVERY_MODE=noop`. Existing baseline:
`SMTPAuthEmailService`, `NoopAuthEmailService`, `backend/tests/test_email_service.py`.

1. Verify sending domain ownership plus SPF, DKIM, and DMARC.
2. Store SMTP credentials only in provider secret storage.
3. Keep `noop` until the acceptance window opens.
4. Test verification/reset delivery, expiry, malformed-token, replay,
   timeout, bounce, and rate-limit behavior.
5. Verify application/provider logs omit tokens, credentials, message body,
   private recipient data, host internals, and traces.
6. Trigger one real stale/failure operator alert and verify cooldown.
7. Revert to `noop`, confirm authentication remains usable, then document
   rollback.
8. Enable `smtp` only after owner sign-off and evidence record.

### DEBT-SC-01 — Semantic cache

Current fact: `SEMANTIC_CACHE_*` settings exist, but no proven semantic-cache
implementation. Exact translation cache already exists
(`build_translation_cache_key`, `TranslationCache`, `TranslationCacheService`).

1. First prove exact-cache insufficiency with fixed offline evaluation
   fixtures.
2. Approve a bounded spec covering embeddings, index, isolation,
   invalidation, idempotency, cost, and a false-hit ceiling.
3. Compare exact-cache baseline against the semantic candidate.
4. Reject semantic cache if measurable quality/cost benefit is absent.
5. If accepted, add a disabled-by-default implementation behind
   `SEMANTIC_CACHE_ENABLED`.
6. Require context, glossary, prompt, model, language, policy, and
   tenant/novel isolation guards.
7. Never auto-publish a semantic hit before evaluation proves it safe.
8. Add corruption, concurrency, invalidation, cost, and cross-novel
   isolation tests.

### DEBT-QA-01 — Advisory LLM QA

Current fact: default-off baseline exists
(`TranslationQAStage.run`, `evaluate_translation_quality_with_llm`,
`LLM_QA_*` settings, `backend/tests/test_llm_qa_parser.py`).

1. Audit current `needs_llm_retry` behavior against "review-only initial
   behavior."
2. Define a fixed labeled evaluation set and false-positive/false-negative
   limits.
3. Keep deterministic QA authoritative.
4. Store bounded structured findings only.
5. Never auto-publish, silently replace translation, or expose raw provider
   output.
6. Add per-run budget, maximum calls, timeout, and provider-failure behavior.
7. Keep disabled by default until owner accepts evaluation evidence.
8. Close only after cost and quality evidence exists.

### DEBT-REV-01 — Public/account reviews

Current baseline: moderation contract shipped. `ReviewService` supports
upsert/get/list/delete/list_user/list_published/list_all/moderate;
`public_novel.py` exposes published-only guest-visible reviews with cursor
pagination; `admin_reviews.py` handles owner moderation with audit; review
write/delete/moderate emit audit events. Remaining: privacy policy sign-off,
pseudonymity controls (currently no author identity is exposed publicly).

### DEBT-COM-01 — Community folders/lists

Plan only; no implementation yet.

1. Approve ownership and visibility rules.
2. Define private/unlisted/public states.
3. Define moderation, reporting, takedown, deletion, and export/privacy
   behavior.
4. Add abuse/rate limits and audit.
5. Start private lists first.
6. Public/community lists require separate owner approval after private-list
   evidence.

### Completed: public rankings (formerly DEBT-RANK-01)

Implemented as the current ranking contract. `GET /api/public/rankings` accepts
only `daily`, `weekly`, and `monthly`, with 24-hour, 7-day, and 30-day windows.
It counts distinct authenticated user ids and signed opaque anonymous viewer
digests from `public_novel.view` only; chapter views, IP addresses, and All Time
claims are excluded. The homepage tabs, Trending widget, and `/ranking` page
consume this response and show truthful disabled/no-data states.

Evidence: `PublicRankingService`, `public_rankings.py`, anonymous viewer-token
tests, distinct-view/period/retention tests in
`backend/tests/test_public_rankings.py`, and frontend ranking honesty/smoke
tests. The weekly metric is the first reliable Trending signal; ratings, saves,
and reviews remain future secondary signals.

### DEBT-120 — Unconnected Backend API Endpoints & Unconsumed Frontend Client Code

Phase 3 also made the ranking path projection-joined and success-cacheable:
the event aggregation uses the published `Novel` projection and composite
event-time/viewer indexes, avoids per-result storage summary calls, and exposes
bounded process-local cache metrics. The cache stores no disabled or empty
response, and production-volume query plans plus multi-reader cache behavior
remain acceptance work rather than fabricated completion evidence.

Full-stack audit finding (2026-08-03), remediation (2026-08-03):

1. **Split-Service vs Combined App Topology (RESOLVED)**: Production Compose (`deploy/Caddyfile`) routes `/api/public/*` to port 8001 (`main_reader.py`) and `/api/admin/*`, `/api/auth/*`, `/api/user/*` to port 8000 (`main_admin.py`). Public contact (`/api/public/contact/contact`), DMCA (`/api/public/dmca/dmca`), and analytics ingestion (`/api/public/analytics/*`) were registered in `app.py` but missing from `main_reader.py`; admin analytics/audit/takedown/reviews/users/metrics routers were missing from `main_admin.py`. All are now registered in their owning app. Analytics event ingestion is a public, anonymous, CSRF-free write and lives ONLY in the reader; a duplicate registration previously (and incorrectly) added to `main_admin.py` was removed.
2. **Route ownership regression protection (RESOLVED)**: `backend/tests/test_microservice_split.py` now asserts strict ownership — the reader must serve public contact/DMCA/analytics-events, the admin must reject `/api/public/*`, the admin must serve all 26 admin/auth/user-client paths, and the combined app minus (admin ∪ reader) is empty (0 stranded endpoints). Verified: 185 combined endpoints = 175 admin + 12 reader, no `/api/public` in admin, no `/api/admin` in reader; all 26 public/user/auth and 77 admin client paths match deployed topology.
3. **Dead client code (RESOLVED)**: Removed from `frontend/lib/api.ts` the 12 legacy `api` methods with zero callers in app/components/hooks and no test/docs references (`progress`, `readerNovel`, `readerChapter`, `runNextActivity`, `updateActivityStatus`, `sourceHealthDetail`, `validateProviderApiKey`, `clearProviderApiKey`, `refreshRuntimeState`, `createRequest`, `scrapeNow`, `translateNow`); removed `authApi.csrf` from `frontend/lib/public-api.ts` (internal CSRF path, not the exported method); removed now-unused `ReaderNovel`, `ReaderChapter`, `NovelProgress` from `frontend/lib/api-types.ts` (`ModelState` kept — it is used).
4. **Audit claims corrected as stale**: The original audit listed `adminApi.analyticsSummary`, `adminApi.updateUserActive`, `adminApi.updateUserRole`, `adminApi.revokeUserSessions`, `userReadingApi.listHistory`, `userReadingApi.recordHistory`, `userReadingApi.listMyReviews`, and hooks `useAuthMe`, `usePublicAuthState`, `useMyReviews`, `useRequests`, `useNotifications`, `useReadAllNotifications`, `useArchiveNotification`, `useReadNotification`, `useUpdateProgress`, `useHistory`, `useRecordHistory`, `useUnreadCount` as unused. Verified current state: all have live UI callers (54 call sites across account/history, account/notifications, account/reviews, account/requests, chapter reader, account overview, home, admin analytics, admin users pages and shared components). Those entries are not debt.

Completion criteria:
- ~~Register public contact, DMCA, and analytics endpoints in `main_reader.py`~~ — done, regression-locked.
- ~~Register admin analytics/audit/takedown/reviews/users/metrics routers in `main_admin.py`~~ — done, regression-locked.
- ~~Remove or connect orphaned API wrappers and hooks~~ — verified-orphan wrappers removed; claimed orphans re-verified as consumed.
- Remaining (not UI debt): 57 admin orchestration backend-only endpoints, 3 admin takedown moderation endpoints, 3 operator/monitoring endpoints, and 58 other backend/CLI/test endpoints have no frontend caller by design — they are invoked by workers, CLI, tests, or operator tooling.

### Completed: unified provider credentials (formerly DEBT-CONTRIB-01)

The approved readiness gate is complete for the credential lifecycle. Owner
managed keys and user contributions use one encrypted `provider_credentials`
registry, with one Gemini contribution per authenticated user in v1. Consent,
explicit-key validation, immediate activation on success, invalid-on-failure,
ownership isolation, replacement, pause/resume, permanent deletion, owner
emergency revoke, no-readback masking, provider isolation, per-credential
RPM/TPM/RPD reservation, and sanitized usage-ledger accounting are
implemented. `credential_owner_user_id` and `requesting_user_id` remain
separate throughout the translation pipeline.

The hardening follow-up adds row-locked deterministic pool selection,
per-credential Redis concurrency enforcement, per-user validation rate limits,
redacted validation feedback, replacement-race protection, explicit owner
environment import, independent owner/pool eligibility, and per-call audit
identity so concurrent chunks cannot cross-associate credential ownership or
ids. The legacy contributor credential table and service/model shims were
removed.

Evidence: local Alembic revisions `d4e6f8a2b1c3` and `e7f1a9c3b5d2`, remote
Supabase migrations `unify_provider_credential_registry` and
`secure_unified_credentials`, canonical provider service/model, user and owner
routers, translation-stage selection/ledger integration,
`backend/tests/test_contributor_credentials.py`, focused backend suite, and
live contribution hook/page tests. The one-time owner environment import is
stored encrypted and the live row is active/valid and owner-job eligible. No
user-contribution rows exist; the owner-scoped bulk verification is executing
through the same provider/ledger path and remains an evidence item until its
terminal chapter counts are recorded.

### Completed: public performance Phase 4

Readiness now uses a short configured TTL with single-flight refresh and a
non-mutating storage reachability probe. Full storage write/read/delete and S3
usage checks remain in owner diagnostics. Safe public catalog, summary, and
chapter projections use bounded process-local TTL/LRU caching with
version-aware keys and publish/reconciliation/takedown invalidation. Public
and server analytics events use a sanitized bounded asynchronous writer with
explicit queue-drop and worker-failure metrics; public content requests no
longer open a synchronous analytics database session.

Evidence: commit `33c5c05`, focused health/analytics/cache/public-route tests,
Ruff, Pyright, fresh backend/reader images, and live Caddy readiness with the
one-second probe configuration and no temporary override. Production percentile
readiness, slow-writer loss, populated ranking load, and multi-reader/shared
cache economics remain open acceptance work. The Phase 4 checkpoint recorded
the older storage-only `test_public_reader_availability.py` fixture as a
projection test gap; the later continuation repaired it without restoring
request-time storage fallback.

### Completed locally: public performance Phase 5

Long-running owner translation requests now enqueue durable translation
activities and return `202` with an activity id; the dedicated Compose worker
owns provider-backed execution while web services keep the in-process runner
disabled. Activity state, leases, claims, idempotency, retry state, and bounded
metadata now use the `activity_records` database table, with one-time legacy
queue import. Gemini owner/contributor admission has global in-flight and
token/request budgets, bounded deadline/backoff behavior, isolated reusable
clients, and sanitized provider timing/usage accounting. Translation-cache
maintenance uses an indexed SQLite WAL sidecar instead of recursive scans.

Evidence: migration `d9f3a1b7c5e2`, `ActivityDatabaseBackend`, dedicated worker
Compose service, provider/quota/cache implementations, `102` expanded focused
backend tests, `69` activity/router/health tests, `40` focused frontend tests,
Ruff, Pyright, frontend lint/typecheck/build, successful local PostgreSQL
migration, healthy production Compose recreation, route/Markdown audit, and
Graphify refresh. The full backend command timed out after `904 s`; the full
frontend Vitest command timed out after about `243 s`; the Phase 5 checkpoint
also recorded two known public-reader projection fixture failures. The later
continuation repaired the availability fixture and passes all `22` tests. Phase
5 is complete locally, while enqueue p95 under concurrent public probes and
production-like provider load/failure behavior remain runtime acceptance work.

### Phase 6 acceptance: repeatable local sample, review gate open

The Phase 6 harness (`backend/tests/run_phase6_acceptance.py`) seeded and
cleaned a namespaced local fixture with 48 published novels, 1,428 chapters,
and 1,200 authenticated/anonymous novel-view events. Concurrent Caddy-routed
public samples returned `200` for health, catalog, detail, chapter, search,
ranking, and home routes with zero transport timeouts/errors. Caddy recorded no
`502`, connection-refused, or `5xx` events. A deliberately missing provider
configuration produced a durable sanitized failed activity with the expected
provider configuration error.

Browser verification covered guest home/ranking/detail/chapter routes and a
disposable authenticated public contribution page session. The first home
browser run found a clock-dependent React hydration error; the page now uses a
hydration-aware timestamp, and the rebuilt routes report zero application
console errors. Focused home tests pass (`29 tests`).

Phase 6 remains open for review. Direct-mode owner enqueue produced two
database-capacity `500` responses in an eight-request burst, while an isolated
transaction-mode control returned five `202` and three configured
translation-limit `429` responses with no database-capacity `500`s. A
controlled 1.2-second object-store protocol delay made ten concurrent readiness requests
return `503` with `storage=unhealthy` (p50 `1,351.488 ms`, p95 `1,382.913 ms`).
The protected base runtime remains `DB_CONNECTION_MODE=direct` and was not
changed. Production-equivalent R2 telemetry, PostgreSQL slowest-query/
query-count evidence, and representative worker/provider capacity remain
unclaimed. Temporary Phase 6 fixture data, overlays, and isolated volumes are
cleaned up after each run; the base Compose stack remains the runtime baseline.

The database-capacity error path is now classified locally: recognized
SQLAlchemy pool/server-capacity failures return sanitized retryable
`503 DATABASE_CAPACITY_EXHAUSTED` responses, while unrelated database errors
remain generic `500`s. After rebuilding the admin and reader images, a direct
direct-mode control repeated the eight-request enqueue burst with five `202`
and three configured `429` responses and zero capacity `500`s. This resolves
the unhandled application error path, but deployment-wide pooler budgeting and
production storage/query/provider evidence remain open.

A safe base-database snapshot reported `max_connections=60`,
`superuser_reserved_connections=3`, `active_connections=19`, and
`application_connections=13`; `pg_stat_statements` is unavailable. Compose
has backend, reader, and worker pool processes with ten-connection theoretical
ceilings, but that snapshot's configured aggregate budget was `20`. The source
validator now enforces the explicit process-count and migration/readiness/
operator-reserve calculation for direct/session mode. The protected base
runtime was rebuilt and restarted with direct-mode budget `32`; the actual
managed pooler and production storage/provider telemetry remain explicit Phase
6 review gates.

### Phase 6 continuation: F-32 resolved

The stale public-reader availability fixture now creates the published
`Novel`/`Chapter` projection through `CatalogService`, and its full focused
suite passes (`22 passed`). The projection-first read context also preserves
per-novel unavailable-policy metadata through migration `e5f7a9c1d3b2`.
Focused catalog tests (`51 passed`), the public-router suite (`133 passed`),
Ruff, Pyright, Graphify, and direct migration upgrade/downgrade smoke passed.
The remaining open work is operator/production evidence, not this local
fixture contract.

## Priority Recommendation

1. `OWN-001` — assign owners (unblocks every evidence record).
2. `REL-001` — freeze candidate.
3. `DEBT-079A` + `DEBT-079B` — deploy and hosted auth/security smoke.
4. `DEBT-075A` + `DEBT-075B` — hosted managed-service verification and
   current-head recovery drill.
5. `DEBT-118` + `DEBT-075C` — SMTP activation and real operator alert.
6. `DEBT-079C` + `DEBT-079D` + `DEBT-079E` — monitoring, manual acceptance,
   rollback rehearsal.
7. `FE-02` — FE-01 manual accessibility/contrast acceptance.
8. Remaining `DEBT-FE-01` slices.
9. Deferred specs (`DEBT-SC-01`, `DEBT-QA-01`, `DEBT-REV-01`, and
   `DEBT-COM-01`) only after launch blockers close.

Reason: launch blockers first. Deferred features add risk, cost, moderation,
and security burden without launch value.

## Explicitly Out of Scope

- Generated translated-novel downloads or manifests.
- Billing, organizations, or multi-admin teams.
- Fake APIs or frontend-only identity/security controls.
- Free preview as production reliability evidence.

## Closing Work

Move completed item summary to `HISTORY.md`, remove its active spec when no
future contract remains, update affected canonical docs, and attach exact test or
operator evidence. Do not preserve resolved debt entries here.
