# design.md

# Design: Scheduled Export Freshness Check

## Overview

`scheduled-export-freshness-check` adds background stale-export detection for generated export artifacts.

Currently, export freshness may only be computed when an export API is called. That means stale PDF/EPUB/HTML exports can remain invisible until a user requests them. This spec adds a scheduled freshness checker that periodically scans export artifacts and marks them as fresh, stale, missing, or unknown based on the latest source content, translation, glossary, export template, and publication state.

This is a should-have reliability/operations feature. It helps admins and users understand whether downloadable exports are current before someone tries to use them.

## Goals

* Add scheduled background export freshness checks.
* Detect stale export artifacts without waiting for API calls.
* Persist freshness status for export artifacts.
* Detect missing export files.
* Detect stale exports caused by translation/content changes.
* Detect stale exports caused by glossary revision changes where applicable.
* Detect stale exports caused by export template/profile changes.
* Preserve existing export behavior.
* Avoid expensive export regeneration in this spec unless an existing auto-regeneration mechanism already exists.
* Add tests for freshness calculation, scheduling, stale marking, missing artifacts, and API compatibility.

## Non-goals

* No full export regeneration system.
* No export queue redesign.
* No PDF rendering/layout rewrite.
* No export UI redesign.
* No CDN invalidation system unless already available.
* No backup retention cleanup. That belongs to `scheduled-backups-and-restore-drills` and `maintenance-cron`.
* No export artifact deletion. That belongs to `maintenance-cron`.
* No public reader projection redesign.
* No analytics dashboard work.

## Problem

Export artifacts can become stale after they are generated.

Examples:

```text id="eumwgi"
translation text changes
chapter order changes
novel metadata changes
chapter title changes
glossary revision changes
export template changes
export profile/settings change
public/private publication state changes
export artifact file is deleted or moved
storage/object storage loses the artifact
```

If freshness is only checked during export API calls, stale exports may remain marked as usable until a user requests them.

## Proposed architecture

Recommended components:

```text id="k6ofvb"
ExportFreshnessScheduler
ExportFreshnessService
ExportFreshnessRepository
ExportArtifactRepository
ExportManifestReader
ExportManifestWriter
StorageService
ActivityQueueService optional
```

High-level flow:

```text id="dbn5k1"
1. Scheduled freshness job starts.
2. Job acquires freshness-check lock.
3. Job scans export artifacts/manifests in batches.
4. For each export, it loads recorded export source versions.
5. It computes current source/content versions.
6. It compares recorded versions with current versions.
7. It checks whether the artifact file still exists.
8. It writes freshness status and stale reason.
9. It records run summary.
```

## Freshness status model

Recommended statuses:

```text id="6syn4o"
fresh
stale
missing
unknown
checking
error
```

Meanings:

```text id="jy9rrp"
fresh: artifact exists and recorded versions match current versions
stale: artifact exists but source/export inputs changed
missing: artifact record exists but file/object is missing
unknown: freshness could not be determined safely
checking: background checker is currently evaluating the artifact
error: checker failed while evaluating the artifact
```

Recommended stale reasons:

```text id="4kna7f"
translation_changed
source_chapter_changed
chapter_order_changed
novel_metadata_changed
glossary_changed
export_template_changed
export_profile_changed
publication_state_changed
artifact_missing
manifest_missing
manifest_invalid
storage_error
unknown
```

## Export version metadata

At export generation time, each artifact should record enough metadata to compare later.

Recommended manifest metadata:

```json id="c4498f"
{
  "format": "pdf",
  "artifact_path": "exports/novel-123/v5/book.pdf",
  "generated_at": "2026-07-10T00:00:00Z",
  "freshness": {
    "status": "fresh",
    "checked_at": "2026-07-10T00:00:00Z",
    "source_fingerprint": "sha256:...",
    "translation_revision": 42,
    "glossary_revision": 8,
    "export_template_version": "2026.07.01",
    "export_profile_hash": "sha256:...",
    "chapter_set_hash": "sha256:...",
    "publication_revision": 12
  }
}
```

Recommended artifact database fields, if exports are stored in DB:

```text id="w421vr"
freshness_status
freshness_checked_at
freshness_stale_reason
freshness_error_category
freshness_error_message
source_fingerprint
translation_revision
glossary_revision
export_template_version
export_profile_hash
chapter_set_hash
publication_revision
artifact_exists
artifact_size_bytes
artifact_updated_at
```

If the project does not have export artifact DB rows, store freshness metadata in the export manifest and optionally maintain a lightweight index.

## Freshness calculation

Freshness is determined by comparing recorded export-time metadata with current metadata.

Recommended checks:

```text id="4fu51q"
artifact exists
manifest exists and is valid
current translation revision equals export translation revision
current glossary revision equals export glossary revision when glossary affects export
current chapter set hash equals export chapter set hash
current novel metadata fingerprint equals export fingerprint
current export template version equals export template version
current export profile hash equals export profile hash
current publication revision equals export publication revision
```

If any required value differs, mark stale.

If a value cannot be computed due to temporary dependency failure, mark unknown or error, not fresh.

## Source fingerprint

If no revision fields exist, compute a fingerprint.

Recommended fingerprint inputs:

```text id="kmdz1d"
novel title
author/title metadata used in export
chapter IDs in export order
chapter titles
translated chapter content hashes
export format
export template version
export profile/settings
glossary revision if glossary terms are embedded in export
publication revision if export is public/downloadable
```

Do not store full chapter text in freshness metadata. Store hashes or revision numbers.

## Scheduled job behavior

Recommended schedule:

```text id="4tj9f6"
EXPORT_FRESHNESS_CHECK_ENABLED=true
EXPORT_FRESHNESS_CHECK_CRON=0 */6 * * *
EXPORT_FRESHNESS_CHECK_BATCH_SIZE=100
EXPORT_FRESHNESS_CHECK_LOCK_TTL_SECONDS=1800
EXPORT_FRESHNESS_CHECK_MAX_ARTIFACTS_PER_RUN=1000
```

Behavior:

```text id="xogzxm"
run on schedule
process artifacts in batches
skip currently generating exports
skip disabled formats
mark checking before evaluation if useful
persist status after each artifact or batch
record run summary
continue after per-artifact failures
```

## Manual trigger

Optional admin endpoint:

```http id="bh661m"
POST /admin/exports/freshness/check
```

Request:

```json id="q61x4o"
{
  "dry_run": true,
  "format": "pdf",
  "novel_id": "novel_123"
}
```

Manual trigger is useful for staging verification but not required if scheduled job and tests exist.

## Freshness run metadata

Recommended table/model: `export_freshness_runs`

Recommended fields:

```text id="unh01l"
id
status
started_at
finished_at
duration_ms
trigger
dry_run
artifacts_scanned
artifacts_fresh
artifacts_stale
artifacts_missing
artifacts_unknown
artifacts_error
error_message
metadata_json
created_at
updated_at
```

Recommended statuses:

```text id="e2zmm5"
running
succeeded
partially_succeeded
failed
skipped_locked
```

If a generic maintenance run system exists, this can be implemented as a maintenance task instead of a new table. However, export freshness should remain queryable.

## Locking

Only one export freshness check should run at a time.

Recommended lock strategies:

```text id="1bl2fs"
database advisory lock
database row lock
Redis lock
scheduler lock
```

If a lock is already held:

```text id="ufmo8r"
skip the new run
record skipped_locked
do not run duplicate scans
```

## API integration

Existing export APIs should include freshness status if they return artifact metadata.

Recommended artifact response field:

```json id="504nu8"
{
  "format": "pdf",
  "download_url": "/exports/exp_123/download",
  "freshness": {
    "status": "stale",
    "checked_at": "2026-07-10T06:00:00Z",
    "stale_reason": "translation_changed"
  }
}
```

If an export is stale, the API should not claim it is current.

Recommended behavior:

```text id="roznsz"
fresh -> allow normal download
stale -> allow download with stale marker, or require regeneration according to product policy
missing -> hide download or return controlled missing-artifact error
unknown/error -> show unknown status and allow safe retry/check
```

This spec should not require changing download policy unless current behavior is unsafe.

## Event-driven hints

Background scanning is the source of truth for this spec, but event-driven hints can improve freshness.

Optional stale markers can be applied when:

```text id="9fdkbo"
translation completes
chapter content changes
glossary revision changes
export template changes
novel metadata changes
chapter order changes
publication state changes
```

Event-driven marking can set likely stale status quickly. The scheduled checker later verifies.

## Regeneration behavior

This spec detects staleness. It does not require regeneration.

Optional future spec:

```text id="66wghf"
export-auto-regeneration
```

If existing regeneration exists, stale detection may enqueue regeneration only when already supported and configured.

Recommended config if auto-enqueue exists:

```text id="206qlh"
EXPORT_FRESHNESS_AUTO_REGENERATE=false
```

Default should be detection only.

## Safety and privacy

Freshness metadata must not store private content.

Never store:

```text id="fjv6mk"
full source chapter text
full translated chapter text
raw prompts
provider API responses
API keys
signed URLs
private user data unrelated to export ownership
```

Allowed:

```text id="8sszfq"
revision numbers
hashes
format keys
template versions
artifact IDs
safe stale reason codes
safe error categories
```

## Error handling

Expected behavior:

```text id="7bu1hz"
artifact missing -> mark missing
manifest missing -> mark unknown or missing depending on storage model
manifest invalid -> mark error or unknown
storage timeout -> mark unknown/error
database timeout -> fail run or mark unknown for affected batch
per-artifact failure -> record error and continue
lock unavailable -> skipped_locked
```

Raw exceptions should not appear in user-facing API responses.

## Observability

Structured logs:

```text id="y72jyw"
export_freshness.run_started
export_freshness.run_finished
export_freshness.artifact_checked
export_freshness.artifact_stale
export_freshness.artifact_missing
export_freshness.artifact_error
export_freshness.skipped_locked
```

Safe fields:

```text id="amlax1"
run_id
artifact_id
format
novel_id
status
stale_reason
duration_ms
error_category
```

Do not log full artifact signed URLs or private content.

## Admin/status endpoint

Recommended endpoint:

```http id="ylwrda"
GET /admin/exports/freshness/status
```

Recommended response:

```json id="mvk6ph"
{
  "enabled": true,
  "schedule": "0 */6 * * *",
  "last_run_status": "succeeded",
  "last_run_at": "2026-07-10T06:00:00Z",
  "summary": {
    "fresh": 120,
    "stale": 12,
    "missing": 1,
    "unknown": 3,
    "error": 0
  }
}
```

Admin-only.

## Testing strategy

Tests should cover:

```text id="605ezy"
fresh artifact remains fresh
translation revision change marks stale
chapter order change marks stale
glossary revision change marks stale when relevant
template version change marks stale
profile hash change marks stale
missing artifact marks missing
invalid manifest marks error/unknown
storage failure marks unknown/error
scheduled job scans in batches
lock prevents overlapping runs
API response includes freshness
download behavior remains safe
event-driven stale hint if implemented
dry-run does not mutate status
```

## Rollout plan

1. Inspect export artifact/manifest model.
2. Define freshness metadata fields.
3. Capture freshness metadata during export generation.
4. Add freshness calculation service.
5. Add scheduled checker.
6. Add run metadata or maintenance integration.
7. Add lock.
8. Update export API responses.
9. Add optional admin status/manual trigger.
10. Add tests.
11. Verify:

    * stale exports are detected without API call.
    * missing files are detected.
    * fresh exports stay fresh.
    * no private content is stored in freshness metadata.
