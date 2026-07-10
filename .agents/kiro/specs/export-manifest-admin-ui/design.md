# design.md

# Design: Export Manifest Admin UI

## Overview

`export-manifest-admin-ui` adds an admin-facing interface for inspecting generated export artifacts and export manifests.

Admins should be able to see export history, identify stale or missing artifacts, inspect manifest metadata, and trigger a re-export when needed. This feature builds on export manifest/freshness work and gives operators a practical way to manage PDF/EPUB/HTML exports without manually inspecting storage or database records.

This is feature polish and operational UX. It is not a V1 launch blocker, but it is valuable once export freshness, export manifest storage, and PDF/EPUB export paths exist.

## Goals

* Add an admin export manifest list page.
* Show export history across novels and formats.
* Show freshness/staleness badges.
* Show missing/error/unknown export states.
* Add manifest detail view or drawer.
* Show safe artifact metadata such as format, generated time, size, checksum, freshness status, and source revisions.
* Add re-export action.
* Support filtering by novel, format, freshness status, and date.
* Support pagination.
* Use existing export manifest/admin APIs where available.
* Add tests for admin access, list rendering, details, stale badges, and re-export flow.

## Non-goals

* No export rendering engine rewrite.
* No PDF layout redesign.
* No scheduled freshness checker implementation. That belongs to `scheduled-export-freshness-check`.
* No export artifact deletion. That belongs to `maintenance-cron`.
* No full metrics dashboard. That belongs to `metrics-dashboard-baseline`.
* No public export history page.
* No non-admin export management UI.
* No direct manual database/storage editing from the UI.
* No exposing raw storage credentials, signed URLs, or private filesystem paths.

## Admin route

Recommended frontend route:

```text id="ypsksf"
/admin/exports
```

Optional detail route:

```text id="bci5bl"
/admin/exports/{export_id}
```

Alternative:

```text id="eb2v2u"
Use a detail drawer/modal on /admin/exports instead of a separate route.
```

## Backend API assumptions

Use existing admin export manifest endpoints where available.

Recommended endpoints:

```http id="7udq8r"
GET /admin/exports
GET /admin/exports/{export_id}
GET /admin/exports/latest
POST /admin/exports/{export_id}/re-export
```

If existing routes use different names, adapt to current project conventions.

Recommended list query params:

```text id="2bmpkq"
page
page_size
novel_id
format
freshness_status
created_after
created_before
sort
direction
```

Recommended list response:

```json id="5l7b5k"
{
  "items": [
    {
      "id": "export_123",
      "novel_id": "novel_456",
      "novel_title": "Example Novel",
      "format": "pdf",
      "status": "completed",
      "freshness_status": "stale",
      "stale_reason": "translation_changed",
      "generated_at": "2026-07-10T00:00:00Z",
      "freshness_checked_at": "2026-07-10T06:00:00Z",
      "artifact_size_bytes": 1234567,
      "manifest_version": 2
    }
  ],
  "page": 1,
  "page_size": 25,
  "total": 1
}
```

Recommended detail response:

```json id="2u7zvp"
{
  "id": "export_123",
  "novel_id": "novel_456",
  "novel_title": "Example Novel",
  "format": "pdf",
  "status": "completed",
  "generated_at": "2026-07-10T00:00:00Z",
  "artifact": {
    "exists": true,
    "size_bytes": 1234567,
    "checksum": "sha256:...",
    "storage_backend": "local",
    "safe_storage_key": "exports/novel_456/export_123/book.pdf"
  },
  "freshness": {
    "status": "stale",
    "checked_at": "2026-07-10T06:00:00Z",
    "stale_reason": "translation_changed",
    "translation_revision": 41,
    "current_translation_revision": 42,
    "glossary_revision": 8,
    "current_glossary_revision": 8,
    "export_template_version": "2026.07.01"
  },
  "manifest": {
    "version": 2,
    "format": "pdf",
    "metadata": {}
  }
}
```

## UI layout

Recommended layout:

```text id="00pud4"
Header
Summary cards
Filters
Export manifest table
Detail drawer/modal
Re-export confirmation dialog
```

### Summary cards

Recommended cards:

```text id="yxukcr"
Total exports
Fresh exports
Stale exports
Missing exports
Unknown/error exports
Last freshness check
```

If summary endpoint does not exist, derive visible-page counts only and label them clearly.

### Filters

Recommended filters:

```text id="re2enw"
Novel search/select
Format
Freshness status
Export status
Created date range
Sort order
```

Format values:

```text id="4esvm8"
pdf
epub
html
txt
json
```

Freshness values:

```text id="u8p2ce"
fresh
stale
missing
unknown
checking
error
```

Export status values should match existing export system, such as:

```text id="ycciz7"
pending
running
completed
failed
cancelled
```

### Table columns

Recommended columns:

```text id="c2saqt"
Novel
Format
Export status
Freshness
Stale reason
Generated at
Last checked
Size
Actions
```

Optional columns:

```text id="frma3n"
Manifest version
Artifact exists
Checksum short hash
Storage backend
Template version
Created by
```

## Freshness badges

Display clear status badges.

Recommended badge mapping:

```text id="qt73e3"
fresh -> Fresh
stale -> Stale
missing -> Missing
unknown -> Unknown
checking -> Checking
error -> Error
```

Stale reason labels:

```text id="d3dzwq"
translation_changed -> Translation changed
source_chapter_changed -> Source chapter changed
chapter_order_changed -> Chapter order changed
novel_metadata_changed -> Novel metadata changed
glossary_changed -> Glossary changed
export_template_changed -> Export template changed
export_profile_changed -> Export profile changed
publication_state_changed -> Publication changed
artifact_missing -> Artifact missing
manifest_missing -> Manifest missing
manifest_invalid -> Manifest invalid
storage_error -> Storage error
unknown -> Unknown
```

The UI should be understandable without requiring users to know internal enum names.

## Manifest detail view

The detail view should show:

```text id="11xzvi"
basic export identity
novel/chapter/export format info
artifact info
freshness status and stale reason
version/revision comparison
manifest JSON summary
safe storage metadata
created/generated timestamps
last freshness check timestamp
download/open action if artifact exists and policy allows
re-export action
```

Do not show:

```text id="u4k00c"
raw signed URLs
storage credentials
absolute private filesystem paths
provider API keys
raw source chapter text
raw translated chapter text
raw prompts
private user tokens
```

If raw manifest JSON is shown, it must be redacted and formatted safely.

## Re-export behavior

The re-export button should create a new export job or call the existing export service.

Recommended flow:

```text id="15zkng"
1. Admin clicks Re-export.
2. UI opens confirmation dialog.
3. Admin confirms.
4. Frontend calls re-export endpoint.
5. Backend validates admin authorization.
6. Backend enqueues export job or starts export through existing service.
7. UI shows success with activity/job link if available.
8. List refreshes or marks export as queued.
```

Recommended re-export request:

```json id="qlrtd0"
{
  "format": "pdf",
  "reason": "admin_reexport"
}
```

If re-exporting a stale manifest, use the latest current source/export inputs, not old stale source fingerprints.

Re-export should not overwrite existing artifacts unless existing export policy already does that. Prefer generating a new artifact/version.

## Download/open action

If admins can download artifacts from this page:

```text id="4ip3sn"
show Download only when artifact exists
respect existing download authorization
do not expose raw storage location
use existing signed download route if available
show disabled state for missing artifacts
show stale warning for stale artifacts if download is allowed
```

## State handling

### Loading state

Show table skeleton or loading indicator while fetching.

### Empty state

Show:

```text id="6l06hn"
No exports found.
```

If filters are active:

```text id="mrfztz"
No exports match the selected filters.
```

### Error state

Show safe error message:

```text id="0jg12j"
Could not load export manifests. Please try again.
```

Do not expose stack traces or internal storage errors.

### Re-export success

Show:

```text id="77jzdu"
Re-export started.
```

Include activity/job link if returned.

### Re-export failure

Show safe reason:

```text id="a0xbpk"
Could not start re-export.
```

## Authorization

Admin-only.

Rules:

```text id="g3qbng"
unauthenticated -> login or 401
authenticated non-admin -> 403
disabled admin -> blocked according to existing auth
admin -> list/detail/re-export allowed
```

If the project supports scoped admin permissions, use:

```text id="kgrft0"
exports:read
exports:write
exports:reexport
```

Otherwise, use existing admin role.

## API client design

Recommended frontend client methods:

```text id="cxh5ro"
listExportManifests(params)
getExportManifest(exportId)
getLatestExportManifest(params)
reExport(exportId, payload)
getExportFreshnessStatus()
```

The UI should not duplicate business logic. Freshness and stale reason should come from the backend.

## Compatibility with scheduled freshness

If `scheduled-export-freshness-check` exists, the admin UI should display persisted freshness status from that system.

If it does not exist yet:

```text id="692gud"
show unknown freshness
or show API-computed freshness if existing export API supports it
avoid pretending stale checks are scheduled
```

The UI should gracefully handle old exports without freshness metadata.

## Security and privacy

Rules:

```text id="2pcqpf"
admin-only access
redact manifest details
do not show signed URLs
do not show absolute private paths
do not show credentials
do not show raw prompts
do not show full source/translated text
respect export download authorization
do not allow arbitrary storage key reads
```

## Observability

Log safe admin actions:

```text id="9w1736"
admin_exports.list_viewed
admin_exports.detail_viewed
admin_exports.reexport_requested
admin_exports.reexport_failed
```

Safe fields:

```text id="jggu8f"
admin_user_id
export_id
novel_id
format
freshness_status
stale_reason
```

Do not log raw manifest JSON or signed URLs.

## Testing strategy

Frontend tests:

```text id="l9itq1"
admin export page renders
non-admin blocked
list loading state
list empty state
list error state
filters update query
fresh/stale/missing badges render
detail drawer renders manifest metadata
redacted fields not displayed
re-export confirmation
re-export success state
re-export failure state
pagination
```

Backend/API tests if endpoints are added or changed:

```text id="uzn2z7"
admin list authorization
admin detail authorization
re-export authorization
filtering and pagination
safe manifest redaction
stale status included
missing artifact represented
old manifest without freshness handled
re-export queues new job
```

## Rollout plan

1. Inspect existing export manifest APIs.
2. Add missing API fields for freshness/status if needed.
3. Add admin export list page.
4. Add filters and pagination.
5. Add freshness badges.
6. Add detail drawer/page.
7. Add redacted manifest display.
8. Add re-export action.
9. Add tests.
10. Verify:

    * admins can view export history.
    * stale/missing exports are visible.
    * manifest details are useful and safe.
    * re-export creates a new job/export.
    * non-admin access is blocked.
