# requirements.md

# Requirements: Public Reader SEO Discovery Baseline

## Introduction

The public reader needs baseline SEO and discovery support so public novel and chapter pages can be indexed and shared safely. The system must generate public-safe metadata, canonical URLs, Open Graph/Twitter tags, robots controls, `robots.txt`, and sitemap entries without exposing private or unpublished content.

## Requirement 1: SEO configuration

### User story

As an operator, I want SEO behavior configured centrally so public metadata and sitemap URLs use the correct site identity.

### Acceptance criteria

1. WHEN SEO is enabled THEN the system SHALL generate SEO metadata for public reader pages.
2. WHEN SEO is disabled THEN the system MAY omit optional SEO metadata while preserving basic page rendering.
3. WHEN public site URL is configured THEN canonical URLs and sitemap URLs SHALL use it.
4. WHEN public site name is configured THEN page titles and Open Graph site name SHALL use it.
5. WHEN public site URL is missing in production THEN the system SHALL surface a configuration warning or use a safe fallback according to project policy.
6. WHEN SEO config changes THEN future metadata and sitemap output SHALL use the new config.
7. WHEN tests run THEN config defaults and overrides SHALL be covered.

## Requirement 2: Canonical URLs

### User story

As a search engine or social crawler, I want canonical URLs so duplicate routes and query parameters do not split page identity.

### Acceptance criteria

1. WHEN a public novel page is rendered THEN it SHALL include a canonical URL.
2. WHEN a public chapter page is rendered THEN it SHALL include a canonical URL.
3. WHEN canonical URL is generated THEN it SHALL use public slugs where available.
4. WHEN canonical URL is generated THEN it SHALL not include query strings.
5. WHEN canonical URL is generated THEN it SHALL not include preview tokens.
6. WHEN canonical URL is generated THEN it SHALL not include session IDs or tracking parameters.
7. WHEN content is unpublished or private THEN canonical metadata SHALL not expose private canonical URLs.
8. WHEN routes change or slugs update THEN canonical URL generation SHALL use the current public route.

## Requirement 3: Page titles

### User story

As a reader or search result viewer, I want public pages to have clear titles.

### Acceptance criteria

1. WHEN a public novel page is rendered THEN title SHALL include public novel title and site name.
2. WHEN a public chapter page is rendered THEN title SHALL include chapter title, novel title, and site name.
3. WHEN novel title is missing THEN a safe fallback title SHALL be used.
4. WHEN chapter title is missing THEN a safe fallback chapter title SHALL be used.
5. WHEN title fields contain unsafe characters THEN they SHALL be escaped.
6. WHEN a page is unavailable/private/taken down THEN title SHALL not leak private unpublished title if policy requires hiding it.
7. WHEN tests inspect metadata THEN page title SHALL match expected format.

## Requirement 4: Meta descriptions

### User story

As a search result viewer, I want useful public descriptions for public novel and chapter pages.

### Acceptance criteria

1. WHEN a public novel summary exists THEN novel page meta description SHALL use a safe shortened version.
2. WHEN no public novel summary exists THEN meta description SHALL use a safe fallback.
3. WHEN a public chapter summary exists THEN chapter page meta description MAY use it.
4. WHEN chapter summary is missing THEN chapter page meta description MAY use novel summary or safe fallback.
5. WHEN descriptions are generated THEN they SHALL be bounded to a configured maximum length.
6. WHEN descriptions are generated THEN they SHALL not include unpublished text.
7. WHEN descriptions are generated THEN they SHALL not include raw prompts, provider errors, admin notes, or private glossary content.
8. WHEN description content contains HTML or unsafe characters THEN it SHALL be escaped or stripped safely.

## Requirement 5: Open Graph metadata

### User story

As a user sharing public pages, I want link previews to show the correct title, description, and image.

### Acceptance criteria

1. WHEN a public novel page is rendered THEN it SHALL include Open Graph title, description, URL, type, and site name.
2. WHEN a public chapter page is rendered THEN it SHALL include Open Graph title, description, URL, type, and site name.
3. WHEN a public cover image exists and is safe THEN Open Graph image SHOULD use it.
4. WHEN no safe cover image exists THEN Open Graph image SHALL use a site default or omit the image according to policy.
5. WHEN Open Graph image is generated THEN it SHALL not be a signed URL.
6. WHEN Open Graph image is generated THEN it SHALL not reference private storage paths.
7. WHEN Open Graph content contains unsafe characters THEN it SHALL be escaped.
8. WHEN page is noindex/private/unpublished THEN Open Graph metadata SHALL not leak private content.

## Requirement 6: Twitter card metadata

### User story

As a user sharing public pages on platforms that read Twitter card tags, I want useful social previews.

### Acceptance criteria

1. WHEN a public novel page is rendered THEN it SHOULD include Twitter card title and description.
2. WHEN a public chapter page is rendered THEN it SHOULD include Twitter card title and description.
3. WHEN a safe image exists THEN Twitter card image SHOULD use it.
4. WHEN no safe image exists THEN Twitter card image MAY use a default site image.
5. WHEN configured Twitter site handle exists THEN metadata MAY include it.
6. WHEN Twitter metadata is generated THEN it SHALL not expose private storage URLs, signed URLs, or unpublished content.
7. WHEN Twitter metadata content contains unsafe characters THEN it SHALL be escaped.

## Requirement 7: Robots directives

### User story

As an operator, I want indexable pages indexed and private/unavailable pages kept out of search results.

### Acceptance criteria

1. WHEN a published public novel page is rendered THEN robots directive SHALL allow indexing.
2. WHEN a published public chapter page is rendered THEN robots directive SHALL allow indexing.
3. WHEN a page is unpublished THEN robots directive SHALL be `noindex` or equivalent.
4. WHEN a page is private THEN robots directive SHALL be `noindex` or equivalent.
5. WHEN a page is a preview route THEN robots directive SHALL be `noindex,nofollow` or equivalent.
6. WHEN a page is taken down or tombstoned THEN robots directive SHALL be `noindex,nofollow`.
7. WHEN a page is an admin/auth/user-specific page THEN robots directive SHALL be `noindex,nofollow`.
8. WHEN a public error/unavailable page is rendered THEN robots directive SHALL be `noindex` or equivalent.

## Requirement 8: `robots.txt`

### User story

As a search engine crawler, I want `robots.txt` so crawl rules and sitemap location are discoverable.

### Acceptance criteria

1. WHEN `GET /robots.txt` is requested THEN the system SHALL return a valid robots text response.
2. WHEN public site URL is configured THEN `robots.txt` SHALL include sitemap URL.
3. WHEN admin routes exist THEN `robots.txt` SHALL disallow admin paths.
4. WHEN auth routes exist THEN `robots.txt` SHOULD disallow auth paths.
5. WHEN API routes should not be crawled THEN `robots.txt` SHALL disallow API paths.
6. WHEN preview routes exist THEN `robots.txt` SHALL disallow preview paths.
7. WHEN `robots.txt` is generated THEN it SHALL not include preview tokens or private URLs.
8. WHEN `robots.txt` is requested THEN content type SHALL be text/plain or project-standard equivalent.

## Requirement 9: Sitemap generation

### User story

As a search engine crawler, I want a sitemap containing public indexable URLs.

### Acceptance criteria

1. WHEN `GET /sitemap.xml` is requested THEN the system SHALL return a valid XML sitemap or sitemap index.
2. WHEN public novel pages are published and indexable THEN sitemap SHALL include them.
3. WHEN public chapter pages are published and indexable THEN sitemap SHALL include them.
4. WHEN public support/legal pages are indexable THEN sitemap MAY include them.
5. WHEN a novel is unpublished THEN sitemap SHALL exclude it.
6. WHEN a chapter is unpublished THEN sitemap SHALL exclude it.
7. WHEN content is private THEN sitemap SHALL exclude it.
8. WHEN content is taken down or tombstoned THEN sitemap SHALL exclude it.
9. WHEN sitemap entries include `lastmod` THEN values SHALL be based on real update/publication timestamps.
10. WHEN timestamps are unknown THEN `lastmod` SHALL be omitted rather than invented.
11. WHEN sitemap grows beyond standard limits THEN the system SHALL use a sitemap index or pagination strategy.

## Requirement 10: Sitemap privacy and safety

### User story

As an operator, I want sitemap generation to avoid leaking private or unpublished content.

### Acceptance criteria

1. WHEN sitemap is generated THEN it SHALL use only public URLs.
2. WHEN sitemap is generated THEN it SHALL not include database-only internal IDs if public slugs exist.
3. WHEN sitemap is generated THEN it SHALL not include private preview URLs.
4. WHEN sitemap is generated THEN it SHALL not include query strings.
5. WHEN sitemap is generated THEN it SHALL not include signed URLs.
6. WHEN sitemap is generated THEN it SHALL not include unpublished/takedown title metadata.
7. WHEN publication state cannot be determined safely THEN the URL SHALL be excluded.
8. WHEN tests run THEN sitemap exclusion rules SHALL be verified.

## Requirement 11: Optional structured data

### User story

As a search engine, I may benefit from structured data describing public novels and chapters.

### Acceptance criteria

1. WHEN structured data is implemented THEN public novel pages MAY include safe Book JSON-LD.
2. WHEN structured data is implemented THEN public chapter pages MAY include safe chapter/article JSON-LD.
3. WHEN structured data is generated THEN it SHALL include only public-safe fields.
4. WHEN structured data is generated THEN it SHALL not include private notes, prompts, diagnostics, or unpublished text.
5. WHEN structured data contains user-controlled text THEN it SHALL be JSON-escaped safely.
6. WHEN structured data is not implemented THEN other SEO baseline requirements SHALL still be satisfied.

## Requirement 12: Metadata cache and invalidation

### User story

As an operator, I want SEO metadata and sitemap generation cached safely without keeping removed content discoverable.

### Acceptance criteria

1. WHEN SEO metadata is cached THEN cache SHALL be invalidated or expire after configured TTL.
2. WHEN sitemap is cached THEN cache SHALL be invalidated or expire after configured TTL.
3. WHEN novel is published/unpublished THEN affected SEO metadata and sitemap cache SHALL be invalidated or updated.
4. WHEN chapter is published/unpublished THEN affected SEO metadata and sitemap cache SHALL be invalidated or updated.
5. WHEN content is taken down or tombstoned THEN affected sitemap/metadata cache SHALL be invalidated immediately where practical.
6. WHEN slug changes THEN canonical and sitemap cache SHALL be invalidated or updated.
7. WHEN cache invalidation fails THEN the system SHALL log a safe warning and prefer excluding unsafe content where possible.

## Requirement 13: Error handling and fallbacks

### User story

As a reader, I want public pages to render even if optional SEO metadata generation has problems.

### Acceptance criteria

1. WHEN SEO metadata generation fails for optional fields THEN the page SHALL still render with safe fallback metadata.
2. WHEN description generation fails THEN the system SHALL use fallback description.
3. WHEN image metadata generation fails THEN the system SHALL use default image or omit image.
4. WHEN sitemap generation fails due to dependency failure THEN the system SHALL return safe error or stale cached sitemap according to policy.
5. WHEN robots.txt generation fails THEN the system SHALL return safe conservative rules where practical.
6. WHEN errors are logged THEN they SHALL not include private content or secrets.
7. WHEN public users see an error page THEN it SHALL not expose SEO internals.

## Requirement 14: Security and privacy

### User story

As an operator, I want SEO metadata to never leak private content.

### Acceptance criteria

1. WHEN metadata is generated THEN it SHALL not include private or unpublished content.
2. WHEN metadata is generated THEN it SHALL not include raw prompts.
3. WHEN metadata is generated THEN it SHALL not include provider diagnostics or errors.
4. WHEN metadata is generated THEN it SHALL not include private glossary definitions.
5. WHEN metadata is generated THEN it SHALL not include signed URLs.
6. WHEN metadata is generated THEN it SHALL not include storage credentials or private paths.
7. WHEN canonical URLs are generated THEN they SHALL not include preview tokens.
8. WHEN unavailable/takedown/private pages are rendered THEN they SHALL be noindex.
9. WHEN sitemap is generated THEN only indexable public pages SHALL be included.

## Requirement 15: Test coverage

### User story

As a maintainer, I want tests for SEO/discovery behavior so public and private content rules do not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover novel page title and description.
2. WHEN tests run THEN they SHALL cover chapter page title and description.
3. WHEN tests run THEN they SHALL cover canonical URLs.
4. WHEN tests run THEN they SHALL cover Open Graph metadata.
5. WHEN tests run THEN they SHALL cover Twitter card metadata where implemented.
6. WHEN tests run THEN they SHALL cover robots directives for indexable and non-indexable pages.
7. WHEN tests run THEN they SHALL cover `robots.txt`.
8. WHEN tests run THEN they SHALL cover sitemap includes published content.
9. WHEN tests run THEN they SHALL cover sitemap excludes unpublished/private/takedown content.
10. WHEN tests run THEN they SHALL cover safe escaping of metadata.
11. WHEN tests run THEN they SHALL cover no signed URLs/private paths in images.
12. WHEN tests run THEN they SHALL cover cache invalidation or TTL behavior where practical.
13. WHEN structured data is implemented THEN tests SHALL cover safe JSON-LD.

## Requirement 16: Completion verification

### User story

As an operator, I want a clear verification path so SEO baseline is complete only when public pages are discoverable and private pages are protected.

### Acceptance criteria

1. WHEN a published novel page is inspected THEN it SHALL include title, description, canonical URL, robots index directive, and Open Graph metadata.
2. WHEN a published chapter page is inspected THEN it SHALL include title, description, canonical URL, robots index directive, and Open Graph metadata.
3. WHEN `robots.txt` is requested THEN it SHALL include sitemap location and disallow private/admin routes.
4. WHEN `sitemap.xml` is requested THEN it SHALL include published public novels and chapters.
5. WHEN unpublished/private/takedown content exists THEN it SHALL not appear in sitemap.
6. WHEN unpublished/private/takedown page is rendered or requested THEN it SHALL be noindex or unavailable according to policy.
7. WHEN metadata is inspected THEN it SHALL not include raw prompts, diagnostics, signed URLs, private glossary data, or private paths.
8. WHEN content is unpublished after being published THEN sitemap/metadata cache SHALL stop exposing it after invalidation or configured TTL.
