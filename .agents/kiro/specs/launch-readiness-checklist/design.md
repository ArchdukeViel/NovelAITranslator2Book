# design.md

# Design: Launch Readiness Checklist

## Overview

`launch-readiness-checklist` is the final release gate for public launch.

It consolidates the completed specs into a single operator-facing go/no-go checklist. The goal is not to add major new features, but to verify that the system is ready to be used publicly: onboarding, crawling, translation, glossary behavior, public reader, exports, SEO, analytics, notifications, abuse protection, takedown handling, backups, health checks, production deployment, rollback, and documentation.

The result is a checklist document: `docs/operations/launch-checklist.md`.

This document should be completed last, after implementation of the preceding public-readiness and operations specs.

## Goals

* Create a final launch checklist.
* Verify core user flows end-to-end.
* Verify public reader safety and availability.
* Verify admin operations and auditability.
* Verify backups, restore drill, health checks, and maintenance.
* Verify production hardening.
* Verify security, privacy, rate limits, and takedown behavior.
* Verify accessibility, performance, SEO, and error states.
* Verify monitoring and rollback readiness.
* Document known issues and launch blockers.
* Provide a clear go/no-go decision process.

## Non-goals

* No new feature implementation.
* No redesign of existing workflows.
* No replacement for automated tests.
* No legal/compliance certification.
* No production incident response platform.
* No guarantee of zero bugs.
* No automatic launch approval.

## Launch readiness phases

Recommended phases:

```text id="ovdg8j"
1. Code complete
2. Test complete
3. Data/storage verified
4. Production config verified
5. Staging smoke test complete
6. Security/privacy review complete
7. Operational readiness complete
8. Go/no-go review
9. Launch
10. Post-launch monitoring
```

## Go/no-go categories

Use these categories:

```text id="rrqsv2"
core product flows
translation quality and glossary behavior
public reader
exports
admin operations
security and privacy
legal/takedown
performance and accessibility
SEO/discovery
analytics/metrics/notifications
backups and maintenance
production deployment
observability
documentation
known issues
rollback plan
```

Each category should have:

```text id="k6xxy1"
status
owner
evidence link or note
blockers
follow-up issues
go/no-go decision
```

## Status values

Recommended checklist status values:

```text id="5eiqby"
not_started
in_progress
passed
passed_with_notes
blocked
waived
not_applicable
```

Definitions:

```text id="8vf071"
passed: verified and ready
passed_with_notes: acceptable known issue documented
blocked: launch cannot proceed
waived: intentionally accepted risk with owner approval
not_applicable: does not apply to current launch scope
```

## Blocker policy

A blocker is any issue that can cause:

```text id="xbjlzr"
private/unpublished content exposure
taken-down content exposure
admin privilege bypass
auth/session failure
data loss
backup failure with no accepted exception
production startup failure
public reader unusable
translation pipeline unusable
unbounded job creation or abuse path
secrets exposure
no rollback path
```

Launch should not proceed with blockers.

## Core product flow checklist

Verify:

```text id="7u4acu"
create/import novel
crawl/fetch chapters
scrape chapter content
apply glossary-first onboarding where expected
run translation job
persist translated chapters
view activity progress
handle failed chapters safely
render translated chapter in reader
publish public content
view public novel/chapter
generate/export artifacts
```

Each core flow should be tested with at least one realistic novel fixture.

## Translation and glossary checklist

Verify:

```text id="fqop0i"
JP→EN prompt policy is current
translation prompt tests pass
glossary terms are injected where expected
glossary diagnostics are collected
glossary annotations are public-safe
annotation setting works globally and per novel
glossary revision invalidation works if implemented
translation failures produce safe errors
manual review path works if required
```

## Public reader checklist

Verify:

```text id="z4gjtv"
published public novel loads
published public chapter loads
unpublished content is not accessible
private content is not accessible
taken-down content is not accessible
reader fallback/degraded mode works
reader empty/error states are safe
glossary annotations render only when enabled
public reader cache respects publication/takedown state
public reader accessibility baseline passes
public reader performance budget is acceptable
```

## Export checklist

Verify:

```text id="o8fi7w"
PDF exporter registered
export generation works
export manifest is recorded
export freshness is checked
stale/missing export states display correctly
admin export manifest UI works
public downloads do not expose private paths
taken-down content cannot be downloaded publicly
```

## Admin operations checklist

Verify:

```text id="9br1ux"
admin user management works
admin audit log viewer works
admin health page works
admin metrics page works if enabled
admin analytics page works if enabled
admin backup/status page works if enabled
admin maintenance status works if enabled
admin takedown workflow works
admin-only routes block non-admin users
```

## Security and privacy checklist

Verify:

```text id="qgzir4"
auth required for protected routes
admin authorization enforced
sessions can be revoked
disabled users cannot access protected routes
CORS is production-safe
CSRF protection or equivalent exists
rate limits enabled
secrets not exposed
logs redact sensitive data
analytics does not collect raw private content
audit logs redact unsafe fields
public APIs do not expose admin/private fields
```

## Legal/takedown checklist

Verify:

```text id="rva2ci"
DMCA/takedown intake works
admin can review requests
admin can apply takedown
public content is blocked after takedown
sitemap excludes taken-down content
SEO uses noindex/unavailable behavior
exports are blocked after takedown
cache invalidation works
audit events are recorded
private legal details are not public
```

## Performance checklist

Verify:

```text id="g6zfhq"
public reader request count acceptable
public reader bundle within budget or exception documented
long chapter fixture remains usable
many-annotation fixture degrades safely
cover images are optimized
public cache improves repeat requests
fallback/error states are lightweight
```

## Accessibility checklist

Verify:

```text id="zl47yg"
keyboard-only reader flow works
skip links work
reader settings usable without mouse
chapter navigation usable without mouse
glossary annotations accessible by keyboard
headings and landmarks are understandable
error/empty/loading states are accessible
200% zoom usable
reduced motion respected
```

## SEO/discovery checklist

Verify:

```text id="uyfcj4"
public novel pages have metadata
public chapter pages have metadata
canonical URLs are correct
Open Graph/Twitter metadata safe
robots.txt available
sitemap.xml available
unpublished/private/taken-down content excluded from sitemap
noindex applied where needed
```

## Observability checklist

Verify:

```text id="9tr64h"
structured logs enabled
request IDs propagated
health/live works
health/ready works
admin health works
metrics baseline works
scheduler/worker status visible
backup status visible
rate-limit/abuse events logged safely
frontend error logging configured or intentionally disabled
```

## Backup and maintenance checklist

Verify:

```text id="lm4yt3"
scheduled backups configured
backup target reachable
backup retention configured
backup status visible
restore drill completed or scheduled with accepted exception
maintenance cron configured
old temp/activity/cache/export data cleanup works
scheduler runtime state persists
```

## Production deployment checklist

Verify:

```text id="m46411"
production config validation passes
required secrets configured
debug mode disabled
secure cookies enabled
CORS restricted
trusted proxy settings correct
security headers present
database migrations applied
workers running
schedulers locked/safe
storage public/private paths correct
public site URL correct
rollback documented
kill switches documented
```

## Evidence

For each checklist item, capture evidence:

```text id="lk3rp5"
test command output
screenshot
admin page URL
log excerpt
health response
manual QA note
issue link
deployment job link
commit hash
```

Evidence should not contain secrets or private content.

## Launch decision

Recommended final decision format:

```text id="dd4o8p"
Launch decision: GO / NO-GO
Date:
Release version:
Commit:
Approver:
Blockers:
Accepted risks:
Rollback owner:
Monitoring owner:
```

## Post-launch monitoring

For the first launch window, monitor:

```text id="m6fdtv"
public reader errors
translation job failures
queue depth
worker health
database errors
storage errors
rate-limit spikes
takedown/legal submissions
backup failures
frontend errors
latency and cache hit rate
```

Recommended launch window:

```text id="k9jvcm"
first 2 hours after launch
first 24 hours after launch
first 7 days after launch
```

## Rollback trigger examples

Rollback or disable features if:

```text id="gnhp9i"
public reader exposes private content
auth/admin access is broken
secrets exposed
database migration corrupts data
translation jobs flood queue
public reader error rate spikes severely
storage access fails broadly
takedown enforcement fails
backup system fails with no mitigation
```

## Rollout plan

1. Create launch checklist document/page.
2. Assign owners for each category.
3. Run automated test suite.
4. Run staging smoke tests.
5. Run security/privacy review.
6. Run performance/accessibility checks.
7. Verify production config.
8. Verify backups and rollback.
9. Hold go/no-go review.
10. Launch only if no blockers remain.
11. Monitor post-launch and record incidents/follow-ups.
