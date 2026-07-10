# design.md

# Design: Public Reader SEO Discovery Baseline

## Overview

`public-reader-seo-discovery-baseline` adds baseline SEO and discovery support for public novel and chapter pages.

The public reader needs stable metadata so search engines, link previews, and social sharing can understand public content. This spec adds canonical URLs, page titles, descriptions, Open Graph/Twitter metadata, robots controls, sitemap generation, and safe handling for unpublished/taken-down/private content.

This is feature polish and public-readiness work. It should be implemented after public reader availability and public path rules are stable.

## Goals

* Add SEO metadata for public novel pages.
* Add SEO metadata for public chapter pages.
* Add canonical URLs.
* Add Open Graph and Twitter card metadata.
* Add robots/noindex behavior for unavailable/private/unpublished/takedown pages.
* Generate sitemap entries for public novels and chapters.
* Add `robots.txt`.
* Add safe metadata fallbacks.
* Avoid exposing private/unpublished content through metadata or sitemap.
* Add tests for metadata, sitemap, canonical URLs, and privacy rules.

## Non-goals

* No full marketing site redesign.
* No paid SEO automation.
* No structured content spam generation.
* No third-party SEO vendor integration.
* No search index implementation inside the app.
* No analytics tracking changes.
* No public glossary pages unless already implemented.
* No automatic translation quality scoring for SEO snippets.

## Public SEO surfaces

Recommended public surfaces:

```text id="7n2x6w"
/novels
/novels/{novel_slug}
/novels/{novel_slug}/chapters/{chapter_slug}
/sitemap.xml
/robots.txt
```

Optional:

```text id="7q9s6f"
/sitemap-index.xml
/sitemaps/novels.xml
/sitemaps/chapters-{page}.xml
```

Use current route names if different.

## Canonical URL strategy

Every indexable public page should have one canonical URL.

Recommended canonical URL examples:

```text id="udxah2"
https://example.com/novels/example-novel
https://example.com/novels/example-novel/chapters/chapter-1
```

Rules:

```text id="7neyi4"
canonical URLs use public slugs, not database IDs
canonical URLs do not include tracking query params
canonical URLs do not include preview tokens
canonical URLs do not include session IDs
canonical URLs use configured public site origin
canonical URLs are stable across frontend rendering
```

Recommended config:

```text id="22hnj6"
PUBLIC_SITE_URL=https://example.com
PUBLIC_SITE_NAME=NovelAI Translator
PUBLIC_SEO_ENABLED=true
```

## Page title strategy

Recommended page titles:

### Novel page

```text id="e3tchh"
{Novel Title} | {Site Name}
```

### Chapter page

```text id="d8td0g"
{Chapter Title} - {Novel Title} | {Site Name}
```

### Novel list page

```text id="zg7hot"
Novels | {Site Name}
```

Fallbacks:

```text id="rgefd1"
Untitled Novel
Untitled Chapter
```

Do not include private/internal notes in titles.

## Description strategy

Descriptions should be safe and concise.

Recommended sources, in priority order:

### Novel page

```text id="q1pzxs"
public novel summary
short public synopsis
safe generated excerpt from public summary
site fallback description
```

### Chapter page

```text id="xh7xxe"
public chapter summary if available
public novel summary
safe short excerpt from public translated text if policy allows
site fallback description
```

Do not expose:

```text id="zxki59"
unpublished text
private notes
raw source text if not public
raw prompts
admin diagnostics
provider errors
private glossary definitions
```

Recommended max length:

```text id="98bgou"
150-170 characters for meta description
```

## Open Graph metadata

Recommended tags:

```html id="7xuy17"
<meta property="og:site_name" content="NovelAI Translator" />
<meta property="og:type" content="article" />
<meta property="og:title" content="Chapter Title - Novel Title" />
<meta property="og:description" content="Safe public description." />
<meta property="og:url" content="https://example.com/novels/example/chapters/chapter-1" />
<meta property="og:image" content="https://example.com/og/default.jpg" />
```

Novel pages can use:

```text id="d91jzd"
og:type: book
```

or:

```text id="gh3fqv"
og:type: article
```

depending on project convention.

Image priority:

```text id="rx6pqu"
public novel cover image
safe generated/default cover card
site default Open Graph image
```

Never use private images, broken storage URLs, or signed URLs as OG images.

## Twitter card metadata

Recommended tags:

```html id="ex9ne5"
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="Chapter Title - Novel Title" />
<meta name="twitter:description" content="Safe public description." />
<meta name="twitter:image" content="https://example.com/og/default.jpg" />
```

Optional:

```text id="jzhnpc"
twitter:site
twitter:creator
```

Only include if configured.

## Robots behavior

Recommended index policy:

```text id="m4xptg"
published novel page -> index, follow
published chapter page -> index, follow
novel list page -> index, follow
preview page -> noindex, nofollow
private/unpublished/takedown page -> noindex, nofollow
error/unavailable page -> noindex, nofollow
admin pages -> noindex, nofollow
auth pages -> noindex, nofollow
search result pages -> noindex, follow or noindex, nofollow by policy
```

Recommended meta tag:

```html id="i0woqq"
<meta name="robots" content="index,follow" />
```

For blocked pages:

```html id="3y8lvn"
<meta name="robots" content="noindex,nofollow" />
```

## `robots.txt`

Recommended public endpoint:

```http id="mxien7"
GET /robots.txt
```

Example:

```text id="wpd9lj"
User-agent: *
Allow: /
Disallow: /admin
Disallow: /login
Disallow: /register
Disallow: /api
Disallow: /preview
Sitemap: https://example.com/sitemap.xml
```

Adjust route names to project routes.

`robots.txt` must not list private content paths or preview tokens.

## Sitemap generation

Recommended endpoint:

```http id="gjc3j7"
GET /sitemap.xml
```

For larger sites, use sitemap index:

```http id="zn7h4l"
GET /sitemap.xml
GET /sitemaps/novels.xml
GET /sitemaps/chapters-1.xml
```

Sitemap entries should include only public indexable URLs.

Recommended sitemap URL entry:

```xml id="5gzz8i"
<url>
  <loc>https://example.com/novels/example-novel</loc>
  <lastmod>2026-07-10T00:00:00Z</lastmod>
  <changefreq>weekly</changefreq>
  <priority>0.8</priority>
</url>
```

Recommended included pages:

```text id="kme40p"
public novel list page
published novel detail pages
published chapter pages
public static legal/support pages if appropriate
```

Excluded pages:

```text id="mvzjrm"
unpublished novels
unpublished chapters
private novels
draft chapters
preview pages
admin pages
auth pages
user-specific pages
search results unless explicitly allowed
takedown/tombstoned content
```

## Last modified values

Recommended `lastmod` source priority:

### Novel page

```text id="7t6dkz"
public projection updated_at
latest published chapter updated_at
novel metadata updated_at
publication updated_at
```

### Chapter page

```text id="ogoh7a"
public chapter projection updated_at
translated chapter updated_at
publication updated_at
```

If unknown, omit `lastmod` rather than inventing.

## Structured data

Optional baseline JSON-LD can be added.

Novel page:

```json id="j6776x"
{
  "@context": "https://schema.org",
  "@type": "Book",
  "name": "Novel Title",
  "description": "Safe public description.",
  "url": "https://example.com/novels/example-novel"
}
```

Chapter page:

```json id="krpcrp"
{
  "@context": "https://schema.org",
  "@type": "Chapter",
  "name": "Chapter Title",
  "isPartOf": {
    "@type": "Book",
    "name": "Novel Title"
  }
}
```

Structured data is optional. If implemented, it must use only public-safe fields.

## Rendering architecture

If the frontend is server-rendered or supports metadata loaders, generate SEO metadata server-side.

Recommended components/services:

```text id="a1p95y"
SeoMetadataService
CanonicalUrlBuilder
SitemapService
RobotsService
PublicSeoPolicy
PublicSeoMetadataComponent
```

If the frontend is a single-page app without SSR, metadata may not be visible to crawlers. In that case, this spec should add server-rendered metadata where the framework supports it, or document the limitation.

## Public SEO policy service

Add a central policy helper:

```text id="h844lg"
PublicSeoPolicy
```

Recommended methods:

```text id="0bhcnh"
is_indexable_public_novel(novel)
is_indexable_public_chapter(novel, chapter)
get_robots_directive(context)
build_canonical_url(route, params)
```

This prevents sitemap, metadata, and robots logic from drifting.

## Takedown and unpublish behavior

If content is unpublished or taken down:

```text id="j3m9f1"
remove from sitemap
return noindex for any fallback/error page
do not expose title/summary if takedown policy requires hiding it
invalidate cached SEO metadata
invalidate cached sitemap if needed
```

If route still returns a public-safe not-found page:

```text id="a7ue5v"
use noindex,nofollow
do not include original private metadata
```

## Cache behavior

SEO metadata and sitemap generation can be cached.

Recommended config:

```text id="px9jja"
SEO_METADATA_CACHE_TTL_SECONDS=300
SITEMAP_CACHE_TTL_SECONDS=900
ROBOTS_CACHE_TTL_SECONDS=3600
```

Cache invalidation triggers:

```text id="035x1n"
novel publish/unpublish
chapter publish/unpublish
novel metadata update
chapter title update
translation update
public slug update
takedown/tombstone update
cover image update
```

If invalidation is difficult, use short TTL and ensure takedown/unpublish can bypass or purge cache.

## Security and privacy

Rules:

```text id="ho4ek4"
never include unpublished/private content in sitemap
never include preview tokens in canonical URLs
never include signed URLs in metadata images
never include raw prompts or diagnostics in descriptions
never include private glossary terms in metadata
never expose internal IDs in canonical URLs if public slugs exist
noindex unavailable/private/takedown pages
```

## Testing strategy

Tests should cover:

```text id="5ke6yq"
novel page title/meta description
chapter page title/meta description
canonical URL
Open Graph tags
Twitter card tags
robots index for published pages
robots noindex for unpublished/private/takedown pages
sitemap includes published novels/chapters
sitemap excludes unpublished/private/takedown content
robots.txt content
safe fallback metadata
metadata escaping
no signed URL in og:image
cache invalidation after publish/unpublish
```

## Rollout plan

1. Inspect public routes and rendering framework metadata support.
2. Add SEO config.
3. Add canonical URL builder.
4. Add SEO policy service.
5. Add novel/chapter metadata generation.
6. Add Open Graph/Twitter tags.
7. Add robots directives.
8. Add sitemap endpoint.
9. Add robots.txt endpoint.
10. Add optional structured data.
11. Add cache/invalidation.
12. Add tests.
13. Verify:

    * public pages have correct metadata.
    * sitemap contains only indexable public URLs.
    * private/unpublished/takedown content is excluded.
    * canonical URLs are stable and safe.
