# design.md

# Design: Public Glossary Annotations Setting

## Overview

`public-glossary-annotations-setting` adds configuration and admin controls for enabling or disabling glossary annotations in the public reader.

The backend annotation wiring exposes `glossary_annotations` in public chapter responses, and the frontend rendering spec highlights them. This spec adds the control layer: global setting, optional per-novel override, and safe behavior when annotations are disabled.

This prevents glossary annotation exposure from being all-or-nothing in code and gives operators control over rollout, privacy, performance, and per-title readiness.

## Goals

* Add global public glossary annotation setting.
* Add optional per-novel public glossary annotation setting.
* Make public chapter API respect these settings.
* Avoid annotation lookup when annotations are disabled.
* Add admin controls for global/per-novel settings.
* Preserve existing reader behavior when disabled.
* Add tests for enabled, disabled, inherited, and override behavior.
* Keep settings additive and safe for old novels.

## Non-goals

* No frontend tooltip/highlight rendering. That belongs to `frontend-glossary-annotation-rendering`.
* No backend annotation matching. That belongs to `public-reader-glossary-annotations-wiring`.
* No glossary editor redesign.
* No glossary term approval workflow changes.
* No public user preference. Reader-local preference belongs to frontend rendering.
* No analytics dashboard.
* No annotation performance cache redesign.
* No automatic glossary quality scoring.

## Setting model

Recommended setting layers:

```text id="06fyx9"
global setting
per-novel setting
```

Recommended effective setting logic:

```text id="m0q4qj"
if global setting is disabled -> annotations disabled for all public chapters
if global setting is enabled and per-novel setting is enabled -> annotations enabled
if global setting is enabled and per-novel setting is disabled -> annotations disabled for that novel
if global setting is enabled and per-novel setting is inherit/null -> annotations enabled by global default
```

Alternative policy:

```text id="8s4x9g"
global setting can be default, per-novel can override enabled/disabled
```

Recommended V1 policy:

```text id="d5t7la"
global disabled is a hard kill switch
global enabled allows per-novel enable/disable/inherit
```

This gives operators an emergency off switch.

## Global setting

Recommended config key:

```text id="yamxw6"
PUBLIC_GLOSSARY_ANNOTATIONS_ENABLED=true
```

If the app already has a database-backed settings table, store:

```text id="7o8mpk"
public_glossary_annotations_enabled
```

Recommended behavior:

```text id="ycvd2e"
false -> public chapter API returns glossary_annotations: []
true -> per-novel setting determines behavior
```

If both environment config and DB setting exist:

```text id="h3w8nx"
environment/config false should act as deployment kill switch
DB setting can only enable annotations when deployment config allows it
```

## Per-novel setting

Recommended field on novel/publication settings:

```text id="8c2tyz"
public_glossary_annotations_mode
```

Recommended values:

```text id="8kpbv3"
inherit
enabled
disabled
```

Alternative boolean if tri-state is not convenient:

```text id="shs7om"
public_glossary_annotations_enabled: true | false | null
```

Recommended default:

```text id="vpftja"
inherit
```

This avoids changing behavior unexpectedly for old novels when the global setting changes.

## Effective setting service

Add a small service:

```text id="9qcyva"
PublicGlossaryAnnotationSettingsService
```

Recommended methods:

```text id="iu4ahx"
is_globally_enabled()
get_novel_mode(novel_id)
get_effective_enabled(novel_id)
set_global_enabled(enabled)
set_novel_mode(novel_id, mode)
```

The public reader should call:

```text id="ja77od"
get_effective_enabled(novel_id)
```

before annotation lookup.

## Public chapter API behavior

When annotations are disabled:

```json id="2r0v4r"
{
  "glossary_annotations": []
}
```

Rules:

```text id="p02gqs"
do not call PublicGlossaryAnnotationsService.find_annotations()
return empty list
do not expose disabled reason publicly unless response contract already supports it
preserve existing chapter response
```

When annotations are enabled:

```text id="hrgnva"
call annotation service
return safe annotations
still apply glossary visibility filtering
still fail open to [] if annotation lookup fails
```

The setting must not bypass approval/visibility rules. Enabled means “allowed to look up safe annotations,” not “expose all glossary data.”

## Admin controls

Recommended global admin page location:

```text id="37wrz8"
/admin/settings
```

or:

```text id="wvamhf"
/admin/settings/public-reader
```

Recommended per-novel location:

```text id="udx6qh"
/admin/novels/{novel_id}/settings
```

or existing novel admin settings page.

Global control:

```text id="x7fcki"
Public glossary annotations: On/Off
```

Per-novel control:

```text id="zf02zt"
Glossary annotations for public reader:
- Inherit global setting
- Enabled
- Disabled
```

Show effective state:

```text id="4y3qp5"
Effective: Enabled
Effective: Disabled by global setting
Effective: Disabled for this novel
```

## Admin APIs

Recommended endpoints:

```http id="x2ebz2"
GET /admin/settings/public-reader
PATCH /admin/settings/public-reader
GET /admin/novels/{novel_id}/public-reader-settings
PATCH /admin/novels/{novel_id}/public-reader-settings
```

Example global response:

```json id="m4ymtj"
{
  "public_glossary_annotations_enabled": true,
  "deployment_allows_public_glossary_annotations": true
}
```

Example per-novel response:

```json id="3yuwaw"
{
  "novel_id": "novel_123",
  "public_glossary_annotations_mode": "inherit",
  "effective_public_glossary_annotations_enabled": true,
  "effective_reason": "global_enabled"
}
```

Example update:

```json id="awzgc9"
{
  "public_glossary_annotations_mode": "disabled"
}
```

## Caching

The effective setting can be cached briefly.

Recommended cache key:

```text id="7h68xc"
public_glossary_annotations_effective:{novel_id}
```

Recommended TTL:

```text id="pv958a"
30-60 seconds
```

When settings change:

```text id="91h6am"
invalidate global setting cache
invalidate per-novel setting cache
invalidate or bypass public chapter response cache if annotation content is embedded
```

If public chapter responses are cached with annotations included, cache keys must account for effective annotation setting or be invalidated on setting change.

## Public reader cache compatibility

If public chapter response cache exists, setting changes must not leave stale annotation state.

Options:

```text id="p5fbjp"
include effective annotation setting/version in cache key
invalidate affected public chapter cache on setting change
serve annotations outside cached core chapter response
```

Recommended V1:

```text id="vfqj0u"
invalidate public reader cache on global setting changes
invalidate affected novel public reader cache on per-novel setting changes
```

If invalidation is expensive, include a settings version in the cache key.

## Audit logging

Changing public exposure settings should be auditable.

Recommended admin audit events:

```text id="d0vqz9"
public_glossary_annotations.global_updated
public_glossary_annotations.novel_updated
```

Safe audit fields:

```text id="ufo404"
admin_user_id
novel_id
previous_value
new_value
created_at
```

Do not log glossary definitions or chapter text.

## Security and privacy

Rules:

```text id="55e3qg"
admin-only setting updates
global disabled acts as hard kill switch
per-novel enabled does not bypass term approval/visibility
public API returns [] when disabled
public API does not expose private disabled reasons unless safe
settings changes are audited
cache invalidation prevents stale exposure
```

## Migration and defaults

Recommended migration:

```text id="6xkolo"
add public_glossary_annotations_mode to novel/publication settings
default inherit
```

If using generic settings table:

```text id="wlcig7"
insert global key public_glossary_annotations_enabled with default true or false according to rollout policy
```

Recommended rollout default:

```text id="zhexmt"
global default false in production until annotation wiring/rendering is verified
global default true in development/test if useful
per-novel default inherit
```

Choose the default based on launch readiness.

## Error handling

Expected behavior:

```text id="1jzeny"
settings lookup fails in public reader -> fail closed and return []
admin settings load fails -> show safe error
admin settings update fails -> show safe error and do not change UI optimistically unless rollback works
invalid mode -> validation error
cache invalidation fails -> setting update succeeds but logs warning, or fails if cache consistency policy requires it
```

For privacy, public reader should fail closed: if the app cannot determine whether annotations are enabled, return no annotations.

## Testing strategy

Tests should cover:

```text id="p4nb38"
global enabled
global disabled
per-novel inherit
per-novel enabled
per-novel disabled
global kill switch overrides per-novel enabled
public reader returns [] when disabled
annotation service not called when disabled
annotation service called when enabled
settings lookup failure returns []
admin settings authorization
admin setting validation
cache invalidation on setting change
public reader cache does not serve stale annotations after disable
audit log created on setting update
```

## Rollout plan

1. Inspect existing settings system.
2. Add global setting.
3. Add per-novel setting.
4. Add effective setting service.
5. Wire public chapter API to check setting before annotation lookup.
6. Add admin APIs.
7. Add admin UI controls.
8. Add cache invalidation.
9. Add audit logging.
10. Add tests.
11. Verify:

    * disabled setting returns `glossary_annotations: []`.
    * enabled setting returns annotations.
    * global kill switch overrides per-novel enable.
    * cache does not leak annotations after disable.
