# design.md

# Design: Analytics Baseline

## Overview

`analytics-baseline` adds privacy-safe product analytics for understanding how users interact with the application.

This is different from operational metrics. `metrics-dashboard-baseline` tracks system health such as latency, errors, queue depth, and throughput. This spec tracks product usage such as public reader views, novel engagement, chapter reads, export clicks, search usage, and feature adoption.

The analytics layer must be intentionally limited, privacy-conscious, and low-risk. It should not collect raw source text, translated text, prompts, private glossary definitions, full IP addresses, or personally sensitive behavioral profiles.

## Goals

* Add a baseline analytics event model.
* Track public reader page views.
* Track novel and chapter engagement.
* Track export/download events.
* Track search/filter usage at a safe aggregate level.
* Track glossary annotation interaction events if enabled.
* Track notification interaction events if notification system exists.
* Support admin analytics summaries.
* Add privacy and retention controls.
* Keep analytics separate from operational metrics.
* Add tests for event recording, privacy redaction, authorization, and summaries.

## Non-goals

* No third-party analytics vendor requirement.
* No advertising attribution.
* No cross-site tracking.
* No fingerprinting.
* No per-user surveillance dashboard.
* No raw clickstream replay.
* No full BI warehouse implementation.
* No operational latency/error dashboard. That belongs to `metrics-dashboard-baseline`.
* No billing or subscription analytics.
* No recommendation engine.

## Analytics principles

Analytics must follow these rules:

```text id="q23s9h"
collect only useful product events
prefer aggregate-safe identifiers
avoid raw user content
avoid sensitive labels
avoid full URLs and query strings
limit retention
allow disabling analytics
separate public anonymous events from authenticated user events
do not block user requests if analytics recording fails
```

## Event model

Recommended table/model: `analytics_events`

Recommended fields:

```text id="97kjtm"
id
event_name
event_time
actor_type
actor_id_hash
session_id_hash
anonymous_id_hash
novel_id
chapter_id
source_type
source_id
route_template
referrer_category
device_category
locale
metadata_json
created_at
```

Recommended `actor_type` values:

```text id="2qh95l"
anonymous
user
admin
system
```

Use hashed IDs where possible for analytics. If internal raw IDs are already used in trusted admin tables, keep them internal and never expose them in public analytics outputs.

## Event names

Recommended baseline events:

```text id="ybhbeq"
public_reader.view
public_novel.view
public_chapter.view
reader.chapter_next
reader.chapter_previous
reader.progress_milestone
search.performed
export.requested
export.downloaded
glossary_annotation.opened
notification.opened
notification.action_clicked
account.signup_completed
```

Required baseline events:

```text id="pj04h1"
public_novel.view
public_chapter.view
export.requested
export.downloaded
search.performed
```

Optional events:

```text id="aakbfi"
glossary_annotation.opened
reader.progress_milestone
notification.opened
account.signup_completed
```

## Public reader analytics

Track public reader engagement without capturing private reading content.

Recommended events:

```text id="b8o6pk"
public_novel.view
public_chapter.view
reader.chapter_next
reader.chapter_previous
reader.progress_milestone
```

Safe fields:

```text id="4zl8ny"
novel_id
chapter_id
public_slug_hash if needed
route_template
device_category
locale
reader_mode
```

Do not store:

```text id="gl3cwn"
full chapter text
selected text
raw scroll stream
raw URL query
IP address
exact user-agent string
```

### Progress milestones

If progress tracking is needed, use coarse milestones:

```text id="u2fz2x"
25
50
75
100
```

Do not record every scroll event.

## Search analytics

Track search usage at an aggregate-safe level.

Recommended event:

```text id="i4k63r"
search.performed
```

Safe metadata:

```text id="uhdnli"
search_scope
result_count_bucket
filter_count
sort_key
```

Avoid storing raw search queries by default.

If query analytics are necessary later, use a separate opt-in and privacy review.

Recommended result count buckets:

```text id="gh37h7"
0
1-5
6-20
21-100
100+
```

## Export analytics

Track export usage.

Recommended events:

```text id="kdeedm"
export.requested
export.downloaded
export.failed
```

Safe metadata:

```text id="z58fbl"
format
freshness_status
source_type
status
error_category
```

Do not store raw artifact paths, signed URLs, local filesystem paths, or private storage keys.

## Glossary annotation analytics

If glossary annotation rendering exists, track only aggregate interaction.

Recommended event:

```text id="cx4kpb"
glossary_annotation.opened
```

Safe metadata:

```text id="a4mvbx"
novel_id
chapter_id
annotation_count_bucket
match_type
```

Avoid storing:

```text id="xlie0x"
display term
source term
definition
raw matched text
full annotation object
```

If term-level analytics are needed later, require a separate spec and privacy review.

## Notification analytics

If notification system exists, track basic interaction.

Recommended events:

```text id="1ajw4r"
notification.opened
notification.action_clicked
notification.marked_read
```

Safe metadata:

```text id="497f62"
event_type
severity
channel
```

Do not store notification body text.

## Session and identity

For anonymous public analytics, use a privacy-safe anonymous/session ID.

Recommended:

```text id="h962xo"
short-lived session ID hash
rotating anonymous ID hash
authenticated actor ID hash if user is logged in
```

Avoid:

```text id="06qppq"
raw IP address
exact user-agent fingerprinting
browser fingerprint
device fingerprint
third-party tracker IDs
cross-site tracking cookies
```

Recommended session expiration:

```text id="15k116"
30 minutes idle
24 hours maximum
```

## Client-side tracking

Frontend should use a small analytics client.

Recommended methods:

```text id="ewib16"
track(eventName, payload)
trackPageView(routeTemplate, metadata)
identifyAuthenticatedUser(userId) // hashed/server-side preferred
clearIdentity()
```

For V1, the client can POST events to backend:

```http id="bpf0yv"
POST /analytics/events
```

Public endpoint must validate and sanitize all input.

## Server-side tracking

Use server-side tracking for trusted events:

```text id="dv8ylk"
export requested
export downloaded
signup completed
notification created/opened where applicable
admin actions if not already in audit logs
```

Server-side tracking avoids relying only on browser behavior.

## Analytics ingestion API

Recommended public/authenticated endpoint:

```http id="unmymu"
POST /analytics/events
```

Example request:

```json id="29x0c3"
{
  "events": [
    {
      "event_name": "public_chapter.view",
      "event_time": "2026-07-10T00:00:00Z",
      "route_template": "/novels/{slug}/chapters/{chapter_slug}",
      "novel_id": "novel_123",
      "chapter_id": "chapter_456",
      "metadata": {
        "reader_mode": "public"
      }
    }
  ]
}
```

The backend must:

```text id="8m9rs2"
validate event names
sanitize metadata
drop unknown unsafe fields
rate limit public ingestion
apply retention
store only allowed fields
return success without exposing internals
```

## Admin analytics API

Recommended endpoints:

```http id="4u4ud8"
GET /admin/analytics/summary
GET /admin/analytics/events
```

`GET /admin/analytics/summary` should be the primary V1 endpoint.

Recommended query params:

```text id="h3x9mo"
window=24h|7d|30d
group_by=day|event_name|novel|format
```

Recommended summary response:

```json id="xktco9"
{
  "window": "7d",
  "generated_at": "2026-07-10T00:00:00Z",
  "totals": {
    "public_novel_views": 1200,
    "public_chapter_views": 8400,
    "export_requests": 120,
    "export_downloads": 90,
    "searches": 300
  },
  "top_novels": [
    {
      "novel_id": "novel_123",
      "title": "Example Novel",
      "views": 500
    }
  ],
  "export_formats": [
    {
      "format": "pdf",
      "requests": 70,
      "downloads": 60
    }
  ]
}
```

Raw event listing should be optional and admin-only. Prefer summaries.

## Admin analytics dashboard

Optional frontend route:

```text id="nfni36"
/admin/analytics
```

Recommended cards:

```text id="tr6wnw"
Novel views
Chapter views
Searches
Export requests
Export downloads
Top novels
Export formats
Glossary annotation opens
Notification clicks
```

Charts can be simple. This is a baseline, not a full BI suite.

## Privacy and retention

Recommended config:

```text id="27j3fo"
ANALYTICS_ENABLED=true
ANALYTICS_PUBLIC_INGESTION_ENABLED=true
ANALYTICS_RETENTION_DAYS=180
ANALYTICS_ANONYMOUS_ID_ROTATION_DAYS=30
ANALYTICS_STORE_RAW_QUERY=false
ANALYTICS_STORE_IP=false
```

Retention cleanup should integrate with `maintenance-cron`.

## Rate limiting and abuse protection

Public analytics ingestion can be abused.

Recommended controls:

```text id="fndvq6"
max events per request
max request body size
rate limit by session/IP hash
validate event names
drop oversized metadata
drop unknown event names
drop events too far in future/past
```

Do not let analytics ingestion create unbounded storage growth.

## Failure behavior

Analytics must never break core app behavior.

Expected behavior:

```text id="6w4fnd"
event recording succeeds -> stored
event recording validation fails -> event dropped or 400 for ingestion endpoint
analytics DB unavailable -> log safe warning and drop/queue event according to config
frontend analytics failure -> silently fail or development warning
admin summary failure -> safe error
```

## Security

Rules:

```text id="z16x0m"
admin analytics endpoints are admin-only
public ingestion cannot write arbitrary event names
public ingestion cannot store arbitrary metadata
no raw secrets in analytics
no raw source/translated text
no raw prompt text
no signed URLs
no per-user surveillance UI
```

## Testing strategy

Tests should cover:

```text id="mxi5js"
event recording
event validation
unsafe metadata stripping
public ingestion rate limits
reader view tracking
export request/download tracking
search tracking without raw query
glossary annotation event without term text
admin summary authorization
admin summary aggregation
retention cleanup hook
analytics failure isolation
```

## Rollout plan

1. Define allowed event names and schemas.
2. Add analytics config.
3. Add event model/migration.
4. Add analytics recorder service.
5. Add public ingestion endpoint.
6. Add server-side tracking for exports/search where appropriate.
7. Add frontend analytics client.
8. Track reader views.
9. Track export and search events.
10. Add admin summary API.
11. Add optional admin analytics page.
12. Add retention cleanup hook.
13. Add tests.
14. Verify:

    * analytics events are recorded.
    * admin summary shows useful aggregates.
    * unsafe fields are stripped.
    * analytics failure does not break user flows.
