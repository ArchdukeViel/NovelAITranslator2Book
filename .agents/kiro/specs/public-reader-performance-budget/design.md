# design.md

# Design: Public Reader Performance Budget

## Overview

`public-reader-performance-budget` defines performance budgets and implementation safeguards for the public reader experience.

Public novel and chapter pages should load quickly, remain responsive on long chapters, and avoid unnecessary API, storage, JavaScript, image, and rendering costs. This spec adds measurable budgets, monitoring points, frontend rendering constraints, cache rules, and regression tests.

This is a public-readiness feature. It does not redesign the reader; it sets limits and guardrails so future features do not make the reader slow.

## Goals

* Define performance budgets for public reader pages.
* Limit frontend JavaScript and CSS cost.
* Reduce unnecessary API calls.
* Improve chapter and novel data loading behavior.
* Optimize cover images and reader assets.
* Add long-chapter rendering safeguards.
* Add caching strategy for public reader responses.
* Avoid glossary annotations, analytics, SEO, and error UI adding excessive overhead.
* Add tests or checks for budget regressions.
* Add documentation for performance expectations.

## Non-goals

* No full CDN deployment requirement.
* No complete frontend framework migration.
* No public reader redesign.
* No paid performance monitoring vendor requirement.
* No full offline reader mode.
* No complete virtualized book reader rewrite unless needed.
* No backend database tuning beyond public reader query path basics.
* No replacing existing storage architecture.

## Target surfaces

Required surfaces:

```text id="j0qqwq"
public novel list
public novel detail
public chapter reader
public search
public reader fallback/snapshot responses
public reader glossary annotations if enabled
public export/download entry points if visible
```

## Performance budgets

Recommended initial budgets:

```text id="15xo5q"
public novel list initial HTML/API response: < 800 ms p95 backend time
public novel detail initial HTML/API response: < 800 ms p95 backend time
public chapter API response: < 1000 ms p95 backend time
public reader total blocking time: < 300 ms target on mid-tier device
reader route JS initial chunk: < 180 KB gzipped target
reader route CSS: < 50 KB gzipped target
chapter text render after API success: < 300 ms for normal chapters
glossary annotation processing: < 100 ms for normal chapters
cover image LCP candidate: optimized and lazy/priority-controlled
```

These are starting budgets. Tune them based on actual architecture and measurement.

## Budget categories

Track budgets for:

```text id="x4qrsd"
backend API latency
frontend bundle size
rendering time
image weight
number of API requests
cache hit behavior
long chapter memory/rendering cost
third-party/script cost
```

## Backend API performance

Public reader endpoints should avoid unnecessary joins and repeated work.

Recommended rules:

```text id="0wwkme"
use public projection tables/files where available
avoid loading private/internal fields
avoid N+1 chapter queries
avoid repeated storage reads for same chapter
use bounded annotation lookup
apply request timeout budgets
return only fields needed by reader
```

API response should be shaped for rendering, not for admin editing.

## API request count

Recommended first-load request count:

### Public chapter page

```text id="b79puu"
1 request for chapter payload
0-1 request for reader settings if server/user settings exist
0-1 request for analytics fire-and-forget
0 extra requests for glossary annotations if already embedded
```

Avoid:

```text id="k3dl38"
separate request per paragraph
separate request per glossary term
separate request per chapter metadata field
blocking analytics before render
blocking export/freshness calls on reader load
```

## Frontend bundle budget

Public reader should not load heavy admin-only code.

Rules:

```text id="8tjr10"
admin components must not be in public reader route bundle
charts/analytics dashboard code must not load on reader pages
export admin UI code must not load on reader pages
large editor/glossary management code must not load on reader pages
optional features should be lazy-loaded
```

Recommended code splitting:

```text id="tuw6qj"
reader shell
reader settings panel lazy if heavy
glossary tooltip code lightweight or lazy
admin-only pages split from public bundle
analytics client tiny and non-blocking
```

## Chapter rendering performance

Long chapters can cause slow rendering.

Recommended safeguards:

```text id="m2xlk1"
avoid per-character React components
split by paragraphs/blocks
memoize processed reader blocks
avoid re-processing annotations on every render
defer optional annotation processing if needed
avoid expensive layout effects over entire chapter
avoid rendering hidden duplicate chapter content
```

For very long chapters:

```text id="b2a3qm"
render by blocks
consider progressive rendering
consider windowing only if it does not harm accessibility/SEO
cap annotation count from backend
skip invalid annotations early
```

## Glossary annotation performance

Glossary annotations should not make the reader slow.

Rules:

```text id="b2y4xf"
annotations are embedded in chapter response where available
group annotations by block
sort once
avoid nested/overlapping expensive rendering
do not create one heavy tooltip instance per annotation if avoidable
skip annotation processing when user preference disables highlights
respect backend annotation maximum per chapter
```

Recommended frontend cap:

```text id="6ujp1d"
PUBLIC_READER_MAX_RENDERED_ANNOTATIONS=500
```

If exceeded:

```text id="i23tb1"
render first safe subset or disable annotation highlights for the chapter
show no intrusive warning to normal readers
log development-only safe warning
```

## Image optimization

Public images should be optimized.

Required image categories:

```text id="5qgjlu"
novel cover images
Open Graph images
inline chapter images if supported
site/logo images
```

Rules:

```text id="p13q14"
use responsive image sizes
lazy-load below-the-fold images
use explicit width/height to reduce layout shift
avoid signed/private URLs
compress covers
prefer modern formats where supported
priority-load only the main LCP image
fallback for broken images
```

## Caching strategy

Public reader content should be cacheable when safe.

Recommended layers:

```text id="oedls2"
backend response cache
public projection cache
storage/object cache
HTTP cache headers
CDN/static cache if deployed
frontend request cache
```

Recommended cache policy:

```text id="zl5i3b"
published public chapter payloads can be cached
public novel metadata can be cached
unpublished/private/preview responses should not be publicly cached
takedown/tombstone must invalidate cache
glossary annotation setting changes must invalidate or version cache
SEO metadata/sitemap has separate cache policy
```

Suggested headers:

```text id="kg41ts"
Cache-Control: public, max-age=60, stale-while-revalidate=300
```

Use only when publication/takedown safety is guaranteed.

## Data size budgets

Response payloads should be bounded.

Recommended limits:

```text id="jsgnfg"
public novel list page size capped
chapter payload includes only active chapter
glossary annotations capped
reader blocks compact
do not include admin metadata
do not include raw diagnostics
do not include full novel chapter list when only current/adjacent chapters are needed unless required
```

For chapter navigation, include only:

```text id="jizg2x"
previous chapter summary
current chapter
next chapter summary
minimal chapter list if selector requires it
```

## Third-party script policy

Public reader should avoid heavy third-party scripts.

Rules:

```text id="na16r6"
no blocking third-party analytics
no admin monitoring scripts on public reader unless necessary
load optional scripts after main content
prefer server-side or first-party analytics baseline
```

## Performance measurement

Recommended measurement points:

```text id="7hdljp"
public_reader.api_latency_ms
public_reader.payload_size_bytes
public_reader.cache_hit
public_reader.render_duration_ms
public_reader.annotation_processing_ms
public_reader.image_lcp_candidate_size_bytes
public_reader.route_js_size_bytes
```

These can integrate with operational metrics if already implemented, but do not need a full dashboard in this spec.

## Regression checks

Add budget checks where practical:

```text id="zohhl8"
bundle size check for public reader route
API payload size test fixture
long chapter render test
annotation processing test
image metadata checks
cache header tests
N+1 query guard where testable
```

## Error/fallback performance

Error and empty states should be lightweight.

Rules:

```text id="4kv38l"
error boundary fallback should not load heavy components
empty state should not load charts/admin code
degraded notices should not block content render
retry logic should avoid request storms
```

## Accessibility and SEO constraints

Performance optimizations must not break accessibility or SEO.

Rules:

```text id="8jqiy3"
do not virtualize content in a way that hides it from assistive tech unless accessible alternative exists
do not remove semantic headings/landmarks
do not block metadata generation
do not lazy-load above-the-fold text
do not require JavaScript for basic public SEO metadata where SSR exists
```

## Rollout plan

1. Measure current public reader performance.
2. Define initial budgets in config/docs.
3. Split public reader bundle from admin-heavy code.
4. Add API payload and request-count guards.
5. Optimize images.
6. Add chapter rendering safeguards.
7. Add annotation processing safeguards.
8. Add public reader cache rules.
9. Add regression tests/checks.
10. Verify:

    * reader loads fast for normal chapters.
    * long chapters remain responsive.
    * public route bundle stays within budget.
    * private/unpublished content is never cached publicly.
