# design.md

# Design: Public Reader Graceful Degradation

## Overview

`public-reader-graceful-degradation` improves public reader resilience when dependencies temporarily fail.

The public reader should not immediately collapse into hard errors when the catalog database, storage backend, object storage, export/public snapshot store, or reader service flickers. This spec adds graceful degradation behavior through bounded timeouts, circuit breakers, safe fallback responses, and optional cached public snapshots.

This is a should-have operations spec. It is not a V1 launch blocker, but it becomes important once public traffic exists.

## Goals

* Add graceful fallback behavior for public reader endpoints.
* Add circuit breakers around unstable public-reader dependencies.
* Serve cached public reader snapshots when fresh enough and safe.
* Preserve existing publication and access-control rules.
* Avoid exposing private/unpublished content during fallback.
* Return clear public-safe degraded responses when fallback is unavailable.
* Add observability for degraded reader behavior.
* Add tests for dependency failure, fallback serving, circuit breaker behavior, and safety rules.

## Non-goals

* No complete public reader cache redesign.
* No new CDN integration requirement.
* No public glossary annotation rendering.
* No full metrics dashboard.
* No full alert notification system.
* No backup/restore implementation.
* No changing translation storage format unless required for snapshot compatibility.
* No serving stale private or unpublished content.

## Dependency surfaces

Public reader requests may depend on:

```text id="ji1bgr"
database/catalog lookup
published novel/chapter availability checks
translated chapter storage
reader block generation
public projection/snapshot storage
object storage
glossary annotation lookup
export/manifest lookup
cache layer
```

This spec should focus first on public reader chapter and novel endpoints.

Recommended endpoint categories:

```text id="x94wgr"
public catalog
public novel detail
public chapter reader
public reader assets
public exported/static snapshots
```

## Degradation levels

Recommended response states:

```text id="7id2eu"
normal
degraded
fallback
unavailable
```

Meaning:

```text id="y8fl3m"
normal: all required dependencies succeeded
degraded: one optional dependency failed but core response is available
fallback: primary dependencies failed, but safe cached snapshot was served
unavailable: primary dependencies failed and no safe fallback exists
```

The API may include a safe response metadata field:

```json id="yi18j2"
{
  "degraded": true,
  "degradation_reason": "served_cached_snapshot",
  "snapshot_generated_at": "2026-07-10T00:00:00Z"
}
```

For public pages, use safe user-facing messaging such as:

```text id="q9cbwv"
This chapter is temporarily unavailable. Please try again later.
```

Do not expose internal dependency names in public responses unless already acceptable.

## Circuit breaker design

Add circuit breakers around dependency calls that can flicker.

Recommended dependencies:

```text id="1xsy0y"
catalog_db
reader_storage
object_storage
public_snapshot_store
glossary_annotations
```

Circuit breaker states:

```text id="60dwn6"
closed
open
half_open
```

Recommended behavior:

```text id="ey2x0b"
closed: calls proceed normally
open: calls fail fast and fallback is attempted
half_open: limited probe calls are allowed to test recovery
```

Recommended config:

```text id="6y88jz"
PUBLIC_READER_CIRCUIT_BREAKER_ENABLED=true
PUBLIC_READER_CB_FAILURE_THRESHOLD=5
PUBLIC_READER_CB_RECOVERY_SECONDS=30
PUBLIC_READER_CB_HALF_OPEN_MAX_CALLS=2
PUBLIC_READER_DEPENDENCY_TIMEOUT_MS=1000
```

Circuit breaker state can be in-memory for V1, but should be safe for multi-instance deployments. If shared Redis/state exists, optional shared state can be added later.

## Timeout policy

Public reader endpoints should not hang indefinitely.

Recommended timeouts:

```text id="p9h4gm"
catalog lookup timeout
chapter storage read timeout
object storage read timeout
snapshot read timeout
glossary annotation lookup timeout
```

Example config:

```text id="mjj8ig"
PUBLIC_READER_TOTAL_TIMEOUT_MS=3000
PUBLIC_READER_CATALOG_TIMEOUT_MS=1000
PUBLIC_READER_STORAGE_TIMEOUT_MS=1500
PUBLIC_READER_SNAPSHOT_TIMEOUT_MS=1000
PUBLIC_READER_OPTIONAL_FEATURE_TIMEOUT_MS=500
```

Optional features such as glossary annotations should fail open and return the core chapter without annotations.

## Fallback snapshot strategy

If public snapshot/projection storage already exists, this spec should use it.

A public reader snapshot is a precomputed public-safe representation of a novel/chapter response.

Recommended snapshot contents:

```text id="vzmcng"
published novel ID/public slug
published chapter ID/public slug
title
chapter title
reader text or reader blocks
public metadata needed for reader
generated_at
source version / translated version
publication state at generation time
```

Never include:

```text id="932dyp"
private drafts
unpublished chapters
admin notes
raw provider prompts
private glossary data
user-specific data
secrets
```

Recommended snapshot key:

```text id="4bpclm"
public-reader/{novel_public_id}/{chapter_public_id}/snapshot.json
```

or:

```text id="345fkh"
public-reader/{novel_slug}/{chapter_slug}/snapshot.json
```

Use existing storage conventions if already defined.

## Snapshot freshness

Fallback snapshots should not be unboundedly stale unless configured.

Recommended config:

```text id="a2xzrt"
PUBLIC_READER_SNAPSHOT_FALLBACK_ENABLED=true
PUBLIC_READER_SNAPSHOT_MAX_AGE_HOURS=168
PUBLIC_READER_ALLOW_STALE_SNAPSHOT_ON_OUTAGE=true
```

Recommended freshness behavior:

```text id="r8tgo6"
fresh snapshot -> serve as fallback
stale snapshot and stale fallback allowed -> serve with degraded marker
stale snapshot and stale fallback not allowed -> unavailable
no snapshot -> unavailable
```

For public reader content, stale published content is often safer than outage, but only if the snapshot was generated from already-published content and has not been revoked/taken down.

## Publication and takedown safety

Fallback must not bypass publication checks.

The hardest case: database/catalog is down, so the app cannot verify whether a chapter is still published.

Recommended safety options:

### Option A: Snapshot contains signed/public projection state

A snapshot is only served if it belongs to a public projection generated by the publication pipeline and has not expired.

### Option B: Revocation/takedown denylist is available

Maintain a small durable public denylist or tombstone store that can be checked even during partial outages.

### Option C: Conservative fallback

If publication state cannot be verified and no safe public projection guarantee exists, do not serve fallback.

Recommended V1 behavior:

```text id="fpn0i9"
serve fallback only from public projection/snapshot store that is explicitly generated for public reader use
do not serve fallback from raw chapter storage
do not serve fallback for private/admin endpoints
respect tombstones/revocations if available
```

If a takedown or unpublish event occurs, public snapshots should be deleted or tombstoned.

## Fallback response behavior

### Public chapter endpoint

Normal path:

```text id="5a2d8p"
load catalog/public chapter
verify published
load reader content
load optional annotations
return response
```

Fallback path:

```text id="ayppch"
primary catalog/storage fails
circuit breaker records failure
attempt public snapshot lookup
validate snapshot safety and freshness
return snapshot response with degraded/fallback metadata
```

If no fallback:

```text id="w5tvmi"
return 503 public-safe temporary unavailable response
```

### Optional feature failure

Glossary annotations and similar optional features should not fail the reader.

```text id="zdd3i9"
annotation service fails -> return chapter with glossary_annotations: []
mark optional feature degraded only in safe metadata/logs
```

## Error taxonomy

Recommended public-reader degradation categories:

```text id="erfphg"
catalog_unavailable
database_timeout
storage_unavailable
object_storage_timeout
snapshot_unavailable
snapshot_stale
snapshot_invalid
circuit_open
optional_feature_failed
publication_state_unknown
takedown_tombstoned
unknown
```

Public users should see safe generic messages. Admin logs/status can include categories.

## Admin/dependency status

A full dashboard belongs to `metrics-dashboard-baseline`, but this spec may expose a simple admin status service or feed deep health.

Recommended service method:

```text id="1u5nui"
PublicReaderResilienceService.get_status()
```

Recommended status fields:

```text id="7m8d3a"
dependency circuit states
recent fallback count
recent unavailable count
last fallback_at
last dependency failure category
snapshot fallback enabled
snapshot max age
```

Optional endpoint:

```http id="2rgy1s"
GET /admin/public-reader/resilience
```

Admin-only.

## Caching integration

This spec should not duplicate cache systems.

It should integrate with:

```text id="zufwxr"
existing public reader cache
public projection hardening
storage projection layer
chapter response cache
CDN cache if present
```

Rules:

```text id="65g99t"
do not cache 503 responses for long periods
cache fallback responses only if marked and safe
respect existing cache invalidation on publish/unpublish/takedown
do not let stale cache resurrect deleted content
```

## Observability

Add structured logs:

```text id="6rljcl"
public_reader.degraded
public_reader.fallback_served
public_reader.fallback_unavailable
public_reader.circuit_opened
public_reader.circuit_half_open
public_reader.circuit_closed
public_reader.optional_feature_failed
```

Safe fields:

```text id="b27l3m"
novel_public_id
chapter_public_id
dependency
error_category
circuit_state
fallback_used
snapshot_age_seconds
duration_ms
```

Avoid logging full chapter text or private metadata.

## Security and privacy

Rules:

```text id="dxq4b8"
never serve raw private storage as fallback
never bypass publication/takedown rules
never include admin-only metadata
never expose stack traces publicly
never expose dependency credentials or storage paths
never expose private glossary data
```

## Testing strategy

Tests should cover:

```text id="6dqedi"
normal reader response unchanged
optional annotation failure returns chapter
database/catalog failure serves safe snapshot
storage failure serves safe snapshot
no snapshot returns 503
stale snapshot allowed/disallowed behavior
unpublished chapter does not fallback
takedown tombstone blocks fallback
circuit opens after threshold
circuit half-open recovery
timeouts trigger fallback
fallback response metadata
public error redaction
admin status authorization if endpoint exists
```

## Rollout plan

1. Inspect public reader endpoints and storage/cache architecture.
2. Identify existing public snapshot/projection storage.
3. Define degradation response metadata.
4. Add dependency timeout wrappers.
5. Add circuit breaker helper.
6. Add public snapshot fallback reader.
7. Wire fallback into public chapter endpoint.
8. Make optional features fail open.
9. Add publication/takedown safety checks.
10. Add observability logs.
11. Add admin status hook if useful.
12. Add tests.
13. Verify:

    * primary path unchanged.
    * safe snapshot served during storage/catalog outage.
    * unsafe/private/unpublished content is never served.
    * no fallback returns safe 503.
