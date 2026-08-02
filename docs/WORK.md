# Work

Single source for unfinished, blocked, deferred, and operator-acceptance work.
Resolved work belongs in [`HISTORY.md`](HISTORY.md), not this file.

## Current Decision

**NO-GO.** Local implementation is mature, but hosted security, monitoring,
alerting, browser/network acceptance, and rollback evidence remain incomplete.

## Execution Policy

- Launch blockers: `DEBT-075`, `DEBT-079`, ownership, recovery, alerts,
  monitoring, accessibility, performance, SEO, legal propagation, rollback.
- `DEBT-FE-01` FE-02+ is non-launch-blocking unless a changed slice touches
  the launch candidate.
- Deferred work stays disabled until its activation gate passes; no frontend
  surface is swapped before backend contract evidence exists.
- Every evidence record includes candidate commit, environment, UTC time,
  operator, exact command/URL, sanitized result, blocker, waiver, and expiry.
- Work closes only after evidence is recorded in `HISTORY.md`; passing local
  tests never substitutes for hosted/manual evidence.

## Launch Roadmap

Dependency-ordered plan. Each row closes only when its "Done when" evidence
exists and is recorded in `HISTORY.md`.

| Order | ID | Work | Dependency | Done when |
|---:|---|---|---|---|
| 1 | OWN-001 | Assign launch, rollback, monitoring, security, recovery, accessibility, performance, SEO, legal owners | None | All nine gates owned by single operator (email on file in operator record, not committed); legal owner = operator for now; no backup contacts — accepted as waiver-eligible single-operator risk, expiry at GO-001; no unowned gate |
| 2 | REL-001 | Freeze exact candidate | OWN-001 | Candidate commit/image tags, domains, environment, UTC time recorded |
| 3 | GH-001 | Finish GitHub controls | REL-001 | `main` protected; exact CI, CodeQL, and GitGuardian checks required; no force push/deletion; sanitized secret-scan incident/false-positive exercise recorded |
| 4 | DEBT-079A | Deploy always-on candidate | REL-001 | Migrations one-shot succeeds; immutable images run; production config validated |
| 5 | DEBT-079B | Hosted auth/security smoke | DEBT-079A | OAuth, cookies, CSRF, CORS, hosts, roles, disabled users, admin/reader boundaries pass |
| 6 | DEBT-075A | Verify hosted PostgreSQL/R2 workflow | DEBT-079A | Managed-services workflow passes against isolated targets |
| 7 | DEBT-075B | Current-head recovery drill | DEBT-075A | DB dump and object snapshot restored into isolated targets; schema, checksums, counts, content, catalog rebuild pass |
| 8 | DEBT-118 | Activate and verify SMTP | DEBT-079A | Domain/SPF/DKIM/DMARC, auth mail, bounce/error handling, redaction, limits, `noop` rollback proven |
| 9 | DEBT-075C | Real operator alert | DEBT-118 | Stale/failure alert delivered; threshold, cooldown, redaction, escalation proven |
| 10 | DEBT-079C | External monitoring | DEBT-079A, OWN-001 | Scheduled runs, dashboard, operator delivery, escalation ownership proven |
| 11 | DEBT-FE-01A | FE-01 manual acceptance | DEBT-079A | Keyboard, screen reader, 200% zoom, reduced motion, focus, contrast verified on shipped tokens; see manual acceptance checklist below |
| 12 | DEBT-079D | Performance/SEO/legal acceptance | DEBT-079A | Budgets, canonical/robots/sitemap/structured data, HTTP 451 and CDN propagation pass |
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
lint/tests, and frontend-check all passed; Vercel preview deployment
completed.

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

## Active Work

| ID | Work | Status | Completion evidence required |
|---|---|---|---|
| DEBT-075 | Managed-service recovery and scheduling closure | Blocked on operator evidence | Real stale/failure SMTP alert; successful hosted PostgreSQL/R2 workflow. Tooling complete: backup stale alert, restore freshness max age, runtime-role verifier, rollback gate. |
| DEBT-079 | Hosted production acceptance | Ongoing | Domains, OAuth, cookies, CORS/CSRF, host validation, storage boundaries, monitoring, rollback, and reliability verified on always-on topology. Tooling complete: authenticated smoke, external monitor, rollback compatibility gate, parser/YAML/router/diff, security review, GitGuardian scan. |
| DEBT-FE-01 | Frontend design rework (Yokocho Lantern + Layout Rework) | FE-01 through FE-10 + review moderation contract shipped; operator-gated remainder open | Review visibility/moderation contract shipped (status pending/published/rejected, admin moderation, public listing, audit); `/account/reviews`, novel-detail community reviews, admin Reviews page all active. Remaining: manual accessibility acceptance (DEBT-FE-01A); approved asset inventory; admin-curated featured rotation; chapter added/failure metadata; stable author identity; expanded library status/progress/update contracts. No gated surface is faked. |

## Active Work Plans

Bounded execution plans for active rows. Each plan step lists exact tooling and
evidence; nothing below is completion evidence by itself.

### DEBT-075 — Managed recovery and scheduling

#### A. Managed-service verification

Existing tooling: `.github/workflows/managed-services-verification.yml`,
`backend/tests/integration/test_managed_postgres.py`,
`backend/tests/integration/test_r2_snapshot_integration.py`.

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
`backend/src/novelai/storage/backends/s3_snapshot.py`,
`deploy/compose.yml` (`restore-db` service), `docs/OPERATIONS.md` restore
procedure.

1. Trigger a fresh object snapshot and encrypted PostgreSQL dump.
2. Verify manifest, last commit, lengths, SHA-256, and backup freshness.
3. Restore storage into an isolated prefix.
4. Restore the DB into a disposable PostgreSQL 17 database whose name contains
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

### DEBT-FE-01 — Frontend design rework

Keep the full rework out of one giant change. Bounded slices, one per
PR/change, each with exact tests:

| ID | Slice | Dependency |
|---|---|---|
| FE-02 | FE-01 accessibility: persistent token regression test covers 34 checks across both modes at WCAG AA 4.5:1 + two-layer primary-button focus treatment shipped; manual browser checks (keyboard, screen reader, zoom, reduced motion) pending operator | FE-01 |
| FE-03 | Desktop header inline nav, mobile bottom tab bar, Account/More hub, reader chrome suppression — shipped (typecheck, 766 tests, build pass) | FE-02 |
| FE-04 | Shared search overlay, keyboard behavior, request cancellation, local recent searches — shipped (typecheck, 781 tests, build, backend 156 tests pass); original-title search added to catalog DB + storage fallback | FE-03 |
| FE-05 | Browse/catalog layout, URL filter state, taxonomy/source canonical routes — shipped (typecheck, 790 tests, build, backend public-router 123 tests pass); authors route remains deferred pending stable identity/alias contract | FE-04 |
| FE-06 | Homepage rails and honest featured-novel selection — rails, Continue Reading/guest state, catalog-derived genres, `/random`, real `updated_at` sort, single-CTA eligible Spotlight shipped (typecheck, 769 tests, build, backend public-router 125 tests pass); manual admin-curated rotation still needs an approved persistence/API contract | FE-05 |
| FE-07 | Novel-detail sticky layout, URL tabs, chapter controls, single CTA — supported UI shipped (typecheck, 776 tests, 48-route build); pending backend contracts: chapter added/failure metadata for New/Failed markers and public review-list pagination | FE-03 |
| FE-08 | Reader Aa panel, progress bar, resume position, quiet chrome — shipped (typecheck, 785 tests across 68 files, 48-route build); account progress + guest local-only persistence, keyboard navigation, strong end CTA | FE-03 |
| FE-09 | Library board/list and account shell — shipped (lint, typecheck, 813 tests across 71 files, 47-page build; prior branch CI); pending backend contracts: plan-to-read/dropped status mutation, bulk status update, progress/title/recent-update fields/filter/badge | FE-03 |
| FE-10 | `/faq`, `/news`, account reviews; `/random` and account overview already shipped — shipped (typecheck, lint, Vitest suite, 47+ page build, backend user-data router tests pass); `GET /api/user/reviews` added for the session user's own reviews; review moderation contract (status lifecycle, public listing, admin moderation, audit) implemented and merged | FE-03 |

Rules:

- One slice per PR/change; no slice bundled with unrelated work.
- No `/authors/[author-slug]` until a stable author-identity/alias backend
  contract is approved.
- No fake rankings, recommendations, community metrics, or contribution UI.
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

Close DEBT-FE-01A only after a pass is recorded for every row above.

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
| Recovery | Needs current run (tooling complete) | Current-head database restore and object snapshot restore into isolated targets. Backup-stale alert threshold, restore-freshness max age, and runtime-role verifier implemented locally. |
| Accessibility | Manual | Keyboard, screen reader, 200% zoom, reduced motion, focus, landmarks, contrast. |
| Performance | Manual | Real-network API p95, request count, cache, long chapter, annotations, route JS. |
| SEO | Manual | Hosted canonical, robots, sitemap, and structured-data validators. |
| Legal propagation | Manual | HTTP 451, sitemap exclusion, and CDN cache propagation. |
| Rollback | Blocked | Pause worker/scheduler, purge cache, disable reader, redeploy previous immutable version, rerun smoke. |
| Ownership | Assigned | All nine gates owned by single operator; email on file in operator record (not committed). Legal owner: operator (temporary). No rollback/monitoring backup — waiver-eligible single-operator risk: risk = alert/rollback response may not reach a second person; reason = solo operation; mitigation = escalate via hosting provider support line on incident; owner = operator; approver = operator; expiry = GO-001. No unowned gate. |

`GO` requires zero unwaived blockers. A waiver records risk, reason, mitigation,
owner, approver, and expiry. Security bypass, private-content exposure, broken
takedown enforcement, unrecoverable loss, or missing rollback cannot be informal waivers.

## Active Specifications

Only genuinely unfinished specs remain under `.agents/kiro/specs/`:

- `launch-readiness-checklist`: operator acceptance above.

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

### DEBT-RANK-01 — Rankings

Keep the honest placeholder until a data contract exists.

1. Approve the ranking formula and eligible events.
2. Define anti-manipulation and replay/idempotency rules.
3. Exclude owner/admin/test traffic.
4. Define update cadence and stale-data display.
5. Validate against fixtures and abuse cases.
6. Only then replace the static `/ranking` placeholder.

### DEBT-CONTRIB-01 — Contribution credentials

Do not reuse owner/admin credential flows directly.

1. Approve consent, ownership, revocation, quotas, and provider-specific
   rules.
2. Add separately encrypted contributor credentials.
3. Separate `requesting_user_id` from `credential_owner_user_id`.
4. Enforce provider isolation and least privilege.
5. Add validation, health, pause, revoke, removal, and deletion.
6. Add usage ledger, per-owner limits, cost ceilings, and audit.
7. Prevent raw credential readback.
8. Add moderation/abuse controls.
9. Run a security review.
10. Replace unavailable contribution surfaces only after the gate passes.

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
9. Deferred specs (`DEBT-SC-01`, `DEBT-QA-01`, `DEBT-REV-01`, `DEBT-COM-01`,
   `DEBT-RANK-01`, `DEBT-CONTRIB-01`) only after launch blockers close.

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
