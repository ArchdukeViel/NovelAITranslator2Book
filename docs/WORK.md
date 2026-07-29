# Work

Single source for unfinished, blocked, deferred, and operator-acceptance work.
Resolved work belongs in [`HISTORY.md`](HISTORY.md), not this file.

## Current Decision

**NO-GO.** Local implementation is mature, but hosted security, monitoring,
alerting, browser/network acceptance, and rollback evidence remain incomplete.

## Active Work

| ID | Work | Status | Completion evidence required |
|---|---|---|---|
| DEBT-075 | Managed-service recovery and scheduling closure | Blocked on operator evidence | Real stale/failure SMTP alert; successful hosted PostgreSQL/R2 workflow. |
| DEBT-079 | Hosted production acceptance | Ongoing | Domains, OAuth, cookies, CORS/CSRF, host validation, storage boundaries, monitoring, rollback, and reliability verified on always-on topology. |
| DEBT-094 | Render Blueprint acceptance | Provider-account blocked | Complete account/payment gate, rerun Blueprint validation, record deployment evidence. Preview does not prove production. |
| DEBT-042 | Maintenance runtime status | Pending | One operator status view backed by `SchedulerRuntimeState`; every job shows schedule, last result, and next eligibility. |
| DEBT-117 | Reader missing-asset boundary | Pending reconciliation | Shared `ReaderAssetBoundary` across specified routes or direct proof current shared boundaries provide equivalent behavior. |

## Operator Acceptance

| Gate | Status | Required evidence |
|---|---|---|
| Hosted smoke and auth/security boundaries | Blocked | Candidate commit, domains, UTC time, commands/URLs, sanitized results. |
| Alerts and monitoring | Blocked | Real operator delivery, cooldown/redaction, dashboards, escalation path. |
| Recovery | Needs current run | Current-head database restore and object snapshot restore into isolated targets. |
| Accessibility | Manual | Keyboard, screen reader, 200% zoom, reduced motion, focus, landmarks, contrast. |
| Performance | Manual | Real-network API p95, request count, cache, long chapter, annotations, route JS. |
| SEO | Manual | Hosted canonical, robots, sitemap, and structured-data validators. |
| Legal propagation | Manual | HTTP 451, sitemap exclusion, and CDN cache propagation. |
| Rollback | Blocked | Pause worker/scheduler, purge cache, disable reader, redeploy previous immutable version, rerun smoke. |
| Ownership | Unassigned | Name launch, rollback, and monitoring owners. |

`GO` requires zero unwaived blockers. A waiver records risk, reason, mitigation,
owner, approver, and expiry. Security bypass, private-content exposure, broken
takedown enforcement, unrecoverable loss, or missing rollback cannot be informal waivers.

## Active Specifications

Only genuinely unfinished specs remain under `.agents/kiro/specs/`:

- `launch-readiness-checklist`: operator acceptance above.
- `maintenance-cron`: DEBT-042.
- `public-reader-graceful-degradation`: DEBT-117.

Task boxes are planning aids, not completion evidence. Architecture, current
code/tests, this file, and operator evidence determine status.

## Deferred

### Email delivery (DEBT-118)

Nonblocking while `AUTH_EMAIL_DELIVERY_MODE=noop`. Before enabling SMTP: verify
sending domain, SPF/DKIM/DMARC, provider, secret storage, delivery/bounces, rate
limits, redaction, and rollback to noop.

### Semantic cache and advisory LLM QA

Requires approved bounded spec covering evaluation fixtures, embedding/index
backend, idempotent writes, credential isolation, structured findings,
review-only initial behavior, cost controls, and disabled-by-default rollout.

### Community and contribution features

Folders/lists, rankings, and contributed provider credentials remain unavailable
until moderation, abuse controls, encrypted credential lifecycle, consent,
revocation, validation, usage ledger/limits, provider isolation, audit, and owner
approval exist.

## Explicitly Out of Scope

- Generated translated-novel downloads or manifests.
- Billing, organizations, or multi-admin teams.
- Fake APIs or frontend-only identity/security controls.
- Free preview as production reliability evidence.

## Closing Work

Move completed item summary to `HISTORY.md`, remove its active spec when no
future contract remains, update affected canonical docs, and attach exact test or
operator evidence. Do not preserve resolved debt entries here.
