# Work

Single source for unfinished, blocked, deferred, and operator-acceptance work.
Resolved work belongs in [`HISTORY.md`](HISTORY.md), not this file.

## Current Decision

**NO-GO.** Local implementation is mature, but hosted security, monitoring,
alerting, browser/network acceptance, and rollback evidence remain incomplete.

## Active Work

| ID | Work | Status | Completion evidence required |
|---|---|---|---|
| DEBT-075 | Managed-service recovery and scheduling closure | Blocked on operator evidence | Real stale/failure SMTP alert; successful hosted PostgreSQL/R2 workflow. Tooling complete: backup stale alert, restore freshness max age, runtime-role verifier, rollback gate. |
| DEBT-079 | Hosted production acceptance | Ongoing | Domains, OAuth, cookies, CORS/CSRF, host validation, storage boundaries, monitoring, rollback, and reliability verified on always-on topology. Tooling complete: authenticated smoke, external monitor, rollback compatibility gate, parser/YAML/router/diff, security review, GitGuardian scan. |
| DEBT-094 | Render Blueprint acceptance | Provider-account blocked | Complete account/payment gate, rerun Blueprint validation, record deployment evidence. Preview does not prove production. |

## Operator Acceptance

| Gate | Status | Required evidence |
|---|---|---|
| Hosted smoke and auth/security boundaries | Blocked | Candidate commit, domains, UTC time, commands/URLs, sanitized results. |
| Secret scanning | Needs hosted run (tooling complete) | Successful GitGuardian push and same-repo PR checks, protected required-check configuration, sanitized incident/false-positive triage evidence. Fork PRs are intentionally skipped (secrets not passed to untrusted code). |
| Alerts and monitoring | Blocked (tooling complete) | Configure `PRODUCTION_BASE_URL`, prove scheduled external runs and real operator delivery, cooldown/redaction, dashboards, escalation, and ownership. |
| Recovery | Needs current run (tooling complete) | Current-head database restore and object snapshot restore into isolated targets. Backup-stale alert threshold, restore-freshness max age, and runtime-role verifier implemented locally. |
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
No backend, threshold, ranking, or rollout policy will be invented during
implementation. Owner approval of a bounded specification is required first.

### Community and contribution features

Folders/lists, rankings, and contributed provider credentials remain unavailable
until moderation, abuse controls, encrypted credential lifecycle, consent,
revocation, validation, usage ledger/limits, provider isolation, audit, and owner
approval exist.
Activation also requires approved product rules for ownership/visibility,
moderation workflow, ranking formula, manipulation resistance, consent, quotas,
and takedown/privacy behavior. Current contribution pages remain honest
unavailable-state surfaces, not implemented contribution infrastructure.

## Explicitly Out of Scope

- Generated translated-novel downloads or manifests.
- Billing, organizations, or multi-admin teams.
- Fake APIs or frontend-only identity/security controls.
- Free preview as production reliability evidence.

## Closing Work

Move completed item summary to `HISTORY.md`, remove its active spec when no
future contract remains, update affected canonical docs, and attach exact test or
operator evidence. Do not preserve resolved debt entries here.
