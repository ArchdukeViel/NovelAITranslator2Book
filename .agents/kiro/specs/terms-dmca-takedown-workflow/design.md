# design.md

# Design: Terms DMCA Takedown Workflow

## Overview

`terms-dmca-takedown-workflow` adds an operational workflow for handling legal/takedown requests against public content.

The earlier `contact-support-legal-pages` spec adds public legal/contact pages and intake surfaces. This spec adds the backend/admin workflow behind takedown handling: submission capture, admin review, status tracking, evidence/notes, public content tombstones, cache invalidation, sitemap removal, audit logging, and safe notifications.

This is a legal/operations feature. It should protect public content routes from continuing to serve content after a valid takedown decision while avoiding accidental exposure of private legal details.

## Goals

* Add takedown request records.
* Support public takedown/DMCA submission intake.
* Support admin review workflow.
* Track request status and decisions.
* Attach takedown decisions to novel/chapter/public content.
* Add public tombstone/unavailable behavior.
* Remove taken-down content from sitemap and indexable metadata.
* Invalidate public reader caches and SEO caches.
* Notify content owners/admins where applicable.
* Audit all sensitive takedown actions.
* Add tests for intake, admin workflow, publication blocking, cache invalidation, sitemap exclusion, and redaction.

## Non-goals

* No legal advice automation.
* No automatic legal determination.
* No public dispute portal unless explicitly added later.
* No full case-management system.
* No payment/refund handling.
* No automatic copyright matching.
* No external legal vendor integration.
* No permanent deletion requirement.
* No replacement for manual legal review.

## Workflow states

Recommended takedown request statuses:

```text id="umom2y"
submitted
triaged
needs_more_info
under_review
accepted
rejected
withdrawn
counter_notice_received
restored
closed
```

Recommended content enforcement states:

```text id="me0qmn"
none
pending_review
temporarily_hidden
takedown_active
restored
```

The request status tracks the legal/admin process. The enforcement state controls public content availability.

## Data model

Recommended table/model: `takedown_requests`

Fields:

```text id="g0ult1"
request_id
request_type
status
submitter_name
submitter_email
submitter_organization optional
claimant_name
claimant_organization
contact_email
subject
description
allegedly_infringing_urls_json
original_work_description
original_work_urls_json
good_faith_statement
accuracy_statement
signature
target_type
novel_id
chapter_id
matched_public_urls_json
admin_notes_json
decision_reason
decision_by_user_id
decision_at
created_at
updated_at
closed_at
metadata_json
```

Recommended `request_type` values:

```text id="7hb0qh"
dmca
copyright
trademark
privacy
abuse
other
```

Recommended table/model: `content_takedown_states`

Fields:

```text id="sqlk3i"
request_id
target_type
novel_id
chapter_id
public_url
state
reason_code
applied_by_user_id
applied_at
restored_by_user_id
restored_at
expires_at
metadata_json
created_at
updated_at
```

Recommended `target_type` values:

```text id="efp7cp"
novel
chapter
export
public_asset
unknown_url
```

Recommended `reason_code` values:

```text id="34rglh"
dmca
copyright
trademark
privacy
abuse
manual_admin
other
```

## Public intake

Use existing legal/contact page if present:

```text id="q6sy1b"
/dmca
/report-error
/contact
```

Recommended endpoint:

```http id="f2p6rr"
POST /support/takedown
```

Request fields:

```text id="mwt5oh"
request_type
submitter_name
submitter_email
submitter_organization optional
claimant_name optional
claimant_organization optional
allegedly_infringing_urls
original_work_description
original_work_urls optional
description
good_faith_statement
accuracy_statement
signature
```

Public intake must be rate-limited and size-limited.

Do not expose internal target IDs publicly. The system can resolve public URLs to target IDs server-side after submission.

## Intake validation

Validation should require:

```text id="x2jp35"
valid contact email
at least one allegedly infringing URL or clear description
description/reason
signature or typed name for DMCA-like requests
good-faith confirmation where required
accuracy confirmation where required
body size within limits
```

Do not reject solely because URL cannot be matched. Store as `unknown_url` or unmatched request for manual review.

## Admin review UI

Recommended admin route:

```text id="rbnsdt"
/admin/takedowns
```

Optional detail route:

```text id="820ygf"
/admin/takedowns/{request_id}
```

Admin list columns:

```text id="cl68d7"
Submitted at
Type
Submitter
Target
Status
Enforcement state
Assigned/reviewed by
Actions
```

Admin detail sections:

```text id="j5f0xu"
Request overview
Submitter/claimant
Reported URLs
Matched targets
Original work information
Statements/signature
Admin notes
Decision history
Enforcement actions
Audit events
```

## Admin actions

Recommended actions:

```text id="lw7s23"
triage
request more information
mark under review
accept takedown
reject takedown
apply temporary hide
apply takedown
restore content
close request
reopen request
record counter-notice
```

Actions should require owner authorization (require_role("owner")) and audit logging.

## Enforcement behavior

When content is taken down:

```text id="hpew3h"
public reader must stop serving content
public API must not return chapter text
public export/download must be disabled
public sitemap must exclude URLs
SEO metadata must be noindex or unavailable
public cache must be invalidated
search/discovery must exclude content
```

Recommended public response for taken-down content:

```text id="7qi9g4"
This content is unavailable due to legal restrictions.
```

Do not disclose claimant details, admin notes, internal legal reasoning, or private target metadata.

## Tombstone behavior

A tombstone is a public-safe unavailable state.

Recommended behavior:

```text id="uvgxt3"
for active takedown -> return HTTP 451 Unavailable For Legal Reasons
for unpublished/private -> keep existing not-found behavior
for restored -> return normal public content if still published
```

HTTP 451 is the active choice when the project wants explicit legal status.

Public response body must be generic.

## Cache and projection invalidation

When takedown is applied:

```text id="u1z9jv"
invalidate public reader cache
invalidate public projection cache if applicable
invalidate public chapter/novel API cache
invalidate sitemap cache
invalidate SEO metadata cache
invalidate export/download cache or mark exports unavailable
invalidate search index/cache if applicable
```

When content is restored:

```text id="wb8i0s"
rebuild or invalidate public projection
restore sitemap eligibility if content is published
restore public reader cache on next request
restore export/download only if policy allows
```

## Sitemap and SEO behavior

Taken-down content must:

```text id="c1zyrq"
be excluded from sitemap
render noindex if a page is shown
not expose title/summary if policy hides them
not use public cover/OG metadata if policy hides them
not expose canonical URL as indexable content
```

If using explicit tombstone page:

```html id="3qhh89"
<meta name="robots" content="noindex,nofollow" />
```

## Export behavior

If exports exist for content under takedown:

```text id="o1bbja"
disable public download
mark export as unavailable or stale/taken_down
exclude from public export lists
admin can still see artifact metadata if authorized
do not delete artifact automatically unless retention policy requires
```

Optional future action:

```text id="6tyev9"
export artifact quarantine
```

## Notifications

Recommended notifications:

```text id="fg4tev"
admin notification when takedown request submitted
content owner notification when request accepted/applied if owner model exists
submitter confirmation email if email system exists
submitter decision email if policy allows
```

Notification content must be safe and not expose private admin notes.

## Audit logging

Required audit events:

```text id="gmjf0l"
takedown.request_submitted
takedown.triaged
takedown.more_info_requested
takedown.accepted
takedown.rejected
takedown.applied
takedown.restored
takedown.closed
takedown.counter_notice_recorded
```

Safe audit fields:

```text id="4wm4mo"
request_id
target_type
target_id
public_url_hash
admin_user_id
previous_status
new_status
previous_enforcement_state
new_enforcement_state
reason_code
created_at
```

Do not log full legal descriptions, raw request body, private text, or sensitive claimant details unless audit retention policy explicitly allows it.

## Security and privacy

Rules:

```text id="e8xx3c"
public submitters cannot see internal review notes
public submitters cannot enumerate target IDs
admins cannot expose private notes in public response
taken-down content cannot be served from cache
unmatched URL submissions are stored for review
all admin decisions are audited
legal request data is protected admin-only
```

## Abuse protection

Public takedown intake must use:

```text id="k3cga4"
rate limit
body size limit
spam/honeypot optional
attachment restrictions if attachments exist
safe validation
```

Do not allow arbitrary file uploads in V1 unless already supported with scanning and size limits.

## Retention

Recommended config:

```text id="mz3t3n"
TAKEDOWN_REQUEST_RETENTION_DAYS=2555
TAKEDOWN_PUBLIC_STATUS_CODE=451
TAKEDOWN_INTAKE_ENABLED=true
TAKEDOWN_REQUIRE_SIGNATURE=true
TAKEDOWN_MAX_URLS_PER_REQUEST=25
TAKEDOWN_MAX_DESCRIPTION_LENGTH=10000
```

Retention should reflect legal policy. If uncertain, keep long retention and document.

## Error handling

Expected behavior:

```text id="2x1yhq"
invalid public submission -> validation errors
rate-limited submission -> safe retry-later response
admin action conflict -> safe conflict response
target already taken down -> idempotent success or clear conflict
restore target not published -> restored enforcement but public remains unavailable due to publication state
cache invalidation failure -> action fails or logs critical warning according to policy
```

Prefer idempotent enforcement actions where possible.

## Testing strategy

Tests should cover:

```text id="e38qek"
public submission validation
submission rate limiting
unmatched URL stored
admin list/detail authorization
status transitions
accept/reject workflow
apply takedown
restore content
public reader blocked after takedown
public API does not return text after takedown
sitemap excludes taken-down content
SEO noindex/tombstone behavior
cache invalidation
export download disabled
audit events
redaction of legal/private fields
```

## Rollout plan

1. Inspect existing legal pages and support submission endpoints.
2. Add takedown data models.
3. Add public intake endpoint.
4. Add admin takedown APIs.
5. Add admin takedown UI.
6. Wire enforcement into public reader/content availability.
7. Wire cache/sitemap/SEO invalidation.
8. Wire export/download availability.
9. Add notifications if available.
10. Add audit logging.
11. Add tests.
12. Verify taken-down content cannot be served publicly.
