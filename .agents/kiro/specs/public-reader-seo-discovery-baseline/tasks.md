# tasks.md

# Tasks: Public Reader SEO Discovery Baseline

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect public route names for novel list, novel detail, and chapter reader.
  * [ ] 0.2 Inspect frontend rendering framework metadata support.
  * [ ] 0.3 Inspect server-side rendering/static generation behavior if any.
  * [ ] 0.4 Inspect public novel/chapter publication checks.
  * [ ] 0.5 Inspect takedown/tombstone behavior.
  * [ ] 0.6 Inspect public slug generation and canonical route helpers.
  * [ ] 0.7 Inspect cover image/public asset storage behavior.
  * [ ] 0.8 Inspect cache behavior for public reader responses.
  * [ ] 0.9 Inspect existing tests for public reader pages/routes.
  * [ ] 0.10 Identify metadata fields that are public-safe.

* [ ] 1. Define SEO policy and config

  * [ ] 1.1 Add `PUBLIC_SEO_ENABLED`. (REQ-1)
  * [ ] 1.2 Add `PUBLIC_SITE_URL`. (REQ-1)
  * [ ] 1.3 Add `PUBLIC_SITE_NAME`. (REQ-1)
  * [ ] 1.4 Add default SEO description config if needed. (REQ-4)
  * [ ] 1.5 Add default Open Graph image config if needed. (REQ-5)
  * [ ] 1.6 Add Twitter site handle config if needed. (REQ-6)
  * [ ] 1.7 Add SEO metadata cache TTL config. (REQ-12)
  * [ ] 1.8 Add sitemap cache TTL config. (REQ-12)
  * [ ] 1.9 Validate required production SEO config. (REQ-1)

* [ ] 2. Add canonical URL builder

  * [ ] 2.1 Add helper to build public site absolute URLs. (REQ-2)
  * [ ] 2.2 Build canonical URL for novel page. (REQ-2)
  * [ ] 2.3 Build canonical URL for chapter page. (REQ-2)
  * [ ] 2.4 Use public slugs where available. (REQ-2)
  * [ ] 2.5 Strip query strings, preview tokens, session IDs, and tracking parameters. (REQ-2)
  * [ ] 2.6 Handle slug changes by using current public route values. (REQ-2)
  * [ ] 2.7 Add tests for canonical URL generation and unsafe parameter exclusion. (REQ-2, REQ-15)

* [ ] 3. Add public SEO policy service

  * [ ] 3.1 Add `PublicSeoPolicy` or equivalent helper. (REQ-7, REQ-10)
  * [ ] 3.2 Add `is_indexable_public_novel()`. (REQ-7, REQ-9)
  * [ ] 3.3 Add `is_indexable_public_chapter()`. (REQ-7, REQ-9)
  * [ ] 3.4 Add preview/private/unpublished/takedown noindex logic. (REQ-7, REQ-14)
  * [ ] 3.5 Add publication-state-unknown exclusion behavior for sitemap. (REQ-10)
  * [ ] 3.6 Add tests for indexable and non-indexable states. (REQ-7, REQ-10, REQ-15)

* [ ] 4. Add metadata text helpers

  * [ ] 4.1 Add safe title builder for novel pages. (REQ-3)
  * [ ] 4.2 Add safe title builder for chapter pages. (REQ-3)
  * [ ] 4.3 Add safe description builder for novel pages. (REQ-4)
  * [ ] 4.4 Add safe description builder for chapter pages. (REQ-4)
  * [ ] 4.5 Add description truncation to configured length. (REQ-4)
  * [ ] 4.6 Strip or escape HTML/unsafe characters. (REQ-3, REQ-4)
  * [ ] 4.7 Exclude private notes, prompts, diagnostics, and glossary content. (REQ-4, REQ-14)
  * [ ] 4.8 Add tests for normal, missing, long, HTML, and unsafe metadata inputs. (REQ-3, REQ-4, REQ-14, REQ-15)

* [ ] 5. Add public novel page metadata

  * [ ] 5.1 Wire metadata generation into public novel page. (REQ-3, REQ-4)
  * [ ] 5.2 Add page title. (REQ-3)
  * [ ] 5.3 Add meta description. (REQ-4)
  * [ ] 5.4 Add canonical URL. (REQ-2)
  * [ ] 5.5 Add robots directive. (REQ-7)
  * [ ] 5.6 Add Open Graph tags. (REQ-5)
  * [ ] 5.7 Add Twitter card tags if implemented. (REQ-6)
  * [ ] 5.8 Add safe fallback metadata. (REQ-13)
  * [ ] 5.9 Add tests for published, missing summary, unsafe content, and unavailable states. (REQ-3, REQ-4, REQ-5, REQ-7, REQ-15)

* [ ] 6. Add public chapter page metadata

  * [ ] 6.1 Wire metadata generation into public chapter page. (REQ-3, REQ-4)
  * [ ] 6.2 Add page title. (REQ-3)
  * [ ] 6.3 Add meta description. (REQ-4)
  * [ ] 6.4 Add canonical URL. (REQ-2)
  * [ ] 6.5 Add robots directive. (REQ-7)
  * [ ] 6.6 Add Open Graph tags. (REQ-5)
  * [ ] 6.7 Add Twitter card tags if implemented. (REQ-6)
  * [ ] 6.8 Avoid exposing unpublished chapter text in descriptions. (REQ-4, REQ-14)
  * [ ] 6.9 Add tests for published, missing title, missing description, unsafe content, and unavailable states. (REQ-3, REQ-4, REQ-5, REQ-7, REQ-15)

* [ ] 7. Add Open Graph image handling

  * [ ] 7.1 Select public novel cover image when safe. (REQ-5)
  * [ ] 7.2 Fall back to default site OG image. (REQ-5)
  * [ ] 7.3 Ensure image URL is absolute. (REQ-5)
  * [ ] 7.4 Ensure image URL is not signed. (REQ-5, REQ-14)
  * [ ] 7.5 Ensure image URL does not expose private storage path. (REQ-5, REQ-14)
  * [ ] 7.6 Handle missing/broken image metadata safely. (REQ-13)
  * [ ] 7.7 Add tests for cover image, fallback image, signed URL rejection, and private path rejection. (REQ-5, REQ-14, REQ-15)

* [ ] 8. Add robots directives

  * [ ] 8.1 Add index/follow directive for published novel pages. (REQ-7)
  * [ ] 8.2 Add index/follow directive for published chapter pages. (REQ-7)
  * [ ] 8.3 Add noindex directive for unpublished pages. (REQ-7)
  * [ ] 8.4 Add noindex directive for private pages. (REQ-7)
  * [ ] 8.5 Add noindex/nofollow directive for preview pages. (REQ-7)
  * [ ] 8.6 Add noindex/nofollow directive for takedown/tombstone pages. (REQ-7)
  * [ ] 8.7 Add noindex/nofollow directive for admin/auth/user-specific pages where frontend controls metadata. (REQ-7)
  * [ ] 8.8 Add tests for all robot directive states. (REQ-7, REQ-15)

* [ ] 9. Add `robots.txt`

  * [ ] 9.1 Add `GET /robots.txt` route. (REQ-8)
  * [ ] 9.2 Return text/plain content type. (REQ-8)
  * [ ] 9.3 Include sitemap URL. (REQ-8)
  * [ ] 9.4 Disallow admin routes. (REQ-8)
  * [ ] 9.5 Disallow auth routes where appropriate. (REQ-8)
  * [ ] 9.6 Disallow API routes where appropriate. (REQ-8)
  * [ ] 9.7 Disallow preview routes. (REQ-8)
  * [ ] 9.8 Ensure no preview tokens/private URLs appear. (REQ-8)
  * [ ] 9.9 Add tests for content, content type, sitemap URL, and disallow rules. (REQ-8, REQ-15)

* [ ] 10. Add sitemap service

  * [ ] 10.1 Add `SitemapService` or equivalent. (REQ-9)
  * [ ] 10.2 Query published public novels. (REQ-9)
  * [ ] 10.3 Query published public chapters. (REQ-9)
  * [ ] 10.4 Exclude unpublished novels. (REQ-9, REQ-10)
  * [ ] 10.5 Exclude unpublished chapters. (REQ-9, REQ-10)
  * [ ] 10.6 Exclude private content. (REQ-9, REQ-10)
  * [ ] 10.7 Exclude takedown/tombstoned content. (REQ-9, REQ-10)
  * [ ] 10.8 Exclude preview/admin/auth/user-specific URLs. (REQ-10)
  * [ ] 10.9 Use canonical URL builder for sitemap URLs. (REQ-2, REQ-9)
  * [ ] 10.10 Add tests for inclusion/exclusion rules. (REQ-9, REQ-10, REQ-15)

* [ ] 11. Add sitemap XML endpoint

  * [ ] 11.1 Add `GET /sitemap.xml`. (REQ-9)
  * [ ] 11.2 Return valid XML. (REQ-9)
  * [ ] 11.3 Include public novel URLs. (REQ-9)
  * [ ] 11.4 Include public chapter URLs. (REQ-9)
  * [ ] 11.5 Include safe `lastmod` where known. (REQ-9)
  * [ ] 11.6 Omit invented `lastmod` where unknown. (REQ-9)
  * [ ] 11.7 Use sitemap index/pagination if URL count exceeds limits. (REQ-9)
  * [ ] 11.8 Add XML validation tests. (REQ-9, REQ-15)

* [ ] 12. Add optional structured data

  * [ ] 12.1 Decide whether JSON-LD is in scope. (REQ-11)
  * [ ] 12.2 Add Book JSON-LD for novel pages if implemented. (REQ-11)
  * [ ] 12.3 Add Chapter/Article JSON-LD for chapter pages if implemented. (REQ-11)
  * [ ] 12.4 Use only public-safe fields. (REQ-11)
  * [ ] 12.5 Escape JSON-LD safely. (REQ-11)
  * [ ] 12.6 Add tests for structured data safety if implemented. (REQ-11, REQ-15)

* [ ] 13. Add SEO/sitemap cache

  * [ ] 13.1 Add metadata cache if useful. (REQ-12)
  * [ ] 13.2 Add sitemap cache if useful. (REQ-12)
  * [ ] 13.3 Apply configured TTLs. (REQ-12)
  * [ ] 13.4 Invalidate on novel publish/unpublish. (REQ-12)
  * [ ] 13.5 Invalidate on chapter publish/unpublish. (REQ-12)
  * [ ] 13.6 Invalidate on takedown/tombstone. (REQ-12)
  * [ ] 13.7 Invalidate on slug changes. (REQ-12)
  * [ ] 13.8 Invalidate on cover image changes. (REQ-12)
  * [ ] 13.9 Add tests for TTL/invalidation where practical. (REQ-12, REQ-15)

* [ ] 14. Add error handling and safe fallbacks

  * [ ] 14.1 Use fallback title when title metadata fails. (REQ-13)
  * [ ] 14.2 Use fallback description when description metadata fails. (REQ-13)
  * [ ] 14.3 Use fallback image or omit image when image metadata fails. (REQ-13)
  * [ ] 14.4 Return safe sitemap error or stale cached sitemap on dependency failure according to policy. (REQ-13)
  * [ ] 14.5 Return conservative robots.txt rules on generation failure where practical. (REQ-13)
  * [ ] 14.6 Ensure errors do not expose private content or secrets. (REQ-13, REQ-14)
  * [ ] 14.7 Add tests for fallback behavior and safe errors. (REQ-13, REQ-15)

* [ ] 15. Add security and privacy hardening

  * [ ] 15.1 Verify metadata does not include unpublished content. (REQ-14)
  * [ ] 15.2 Verify metadata does not include prompts. (REQ-14)
  * [ ] 15.3 Verify metadata does not include provider diagnostics/errors. (REQ-14)
  * [ ] 15.4 Verify metadata does not include private glossary content. (REQ-14)
  * [ ] 15.5 Verify images do not use signed URLs. (REQ-14)
  * [ ] 15.6 Verify canonical URLs do not include preview tokens. (REQ-14)
  * [ ] 15.7 Verify sitemap only includes public indexable pages. (REQ-14)
  * [ ] 15.8 Add privacy/security tests for each category. (REQ-14, REQ-15)

* [ ] 16. Test coverage pass

  * [ ] 16.1 Test novel page metadata. (REQ-3, REQ-4, REQ-15)
  * [ ] 16.2 Test chapter page metadata. (REQ-3, REQ-4, REQ-15)
  * [ ] 16.3 Test canonical URLs. (REQ-2, REQ-15)
  * [ ] 16.4 Test Open Graph tags. (REQ-5, REQ-15)
  * [ ] 16.5 Test Twitter tags if implemented. (REQ-6, REQ-15)
  * [ ] 16.6 Test robots directives. (REQ-7, REQ-15)
  * [ ] 16.7 Test `robots.txt`. (REQ-8, REQ-15)
  * [ ] 16.8 Test sitemap includes published content. (REQ-9, REQ-15)
  * [ ] 16.9 Test sitemap excludes unpublished/private/takedown content. (REQ-9, REQ-10, REQ-15)
  * [ ] 16.10 Test safe escaping. (REQ-3, REQ-4, REQ-15)
  * [ ] 16.11 Test no signed URLs/private paths. (REQ-5, REQ-14, REQ-15)
  * [ ] 16.12 Test cache invalidation/TTL where practical. (REQ-12, REQ-15)
  * [ ] 16.13 Test structured data if implemented. (REQ-11, REQ-15)

* [ ] 17. Documentation

  * [ ] 17.1 Document SEO config keys. (REQ-1)
  * [ ] 17.2 Document canonical URL strategy. (REQ-2)
  * [ ] 17.3 Document title/description strategy. (REQ-3, REQ-4)
  * [ ] 17.4 Document Open Graph/Twitter behavior. (REQ-5, REQ-6)
  * [ ] 17.5 Document robots directives. (REQ-7)
  * [ ] 17.6 Document robots.txt behavior. (REQ-8)
  * [ ] 17.7 Document sitemap inclusion/exclusion rules. (REQ-9, REQ-10)
  * [ ] 17.8 Document cache invalidation. (REQ-12)
  * [ ] 17.9 Document privacy rules for metadata. (REQ-14)

* [ ] 18. Completion verification

  * [ ] 18.1 Inspect published novel page metadata. (REQ-16)
  * [ ] 18.2 Verify novel page has title, description, canonical URL, robots index, and Open Graph tags. (REQ-16)
  * [ ] 18.3 Inspect published chapter page metadata. (REQ-16)
  * [ ] 18.4 Verify chapter page has title, description, canonical URL, robots index, and Open Graph tags. (REQ-16)
  * [ ] 18.5 Request `/robots.txt` and verify sitemap location and private route disallows. (REQ-8, REQ-16)
  * [ ] 18.6 Request `/sitemap.xml` and verify published novels/chapters appear. (REQ-9, REQ-16)
  * [ ] 18.7 Verify unpublished/private/takedown content does not appear in sitemap. (REQ-9, REQ-10, REQ-16)
  * [ ] 18.8 Verify unavailable/private/takedown pages are noindex or unavailable. (REQ-7, REQ-16)
  * [ ] 18.9 Verify metadata contains no prompts, diagnostics, signed URLs, private glossary data, or private paths. (REQ-14, REQ-16)
  * [ ] 18.10 Unpublish previously published content and verify sitemap/metadata cache stops exposing it after invalidation or TTL. (REQ-12, REQ-16)
  * [ ] 18.11 Mark `public-reader-seo-discovery-baseline` complete only after public pages are discoverable and private content is excluded.
