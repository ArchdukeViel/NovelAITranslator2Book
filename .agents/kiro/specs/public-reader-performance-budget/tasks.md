# tasks.md

# Tasks: Public Reader Performance Budget

## Task List

* [ ] 0. Preflight performance audit

  * [ ] 0.1 Inspect public reader routes and data-loading path.
  * [ ] 0.2 Inspect public novel list/detail API calls.
  * [ ] 0.3 Inspect public chapter API response shape.
  * [ ] 0.4 Inspect public reader frontend bundle composition.
  * [ ] 0.5 Inspect reader block/chapter rendering components.
  * [ ] 0.6 Inspect glossary annotation frontend processing.
  * [ ] 0.7 Inspect cover/chapter image handling.
  * [ ] 0.8 Inspect cache headers and backend response cache.
  * [ ] 0.9 Inspect public reader metrics/logging support.
  * [ ] 0.10 Inspect build/test tooling for bundle and performance checks.

* [ ] 1. Document initial performance budgets

  * [ ] 1.1 Define backend API latency targets. (REQ-1, REQ-2)
  * [ ] 1.2 Define public reader bundle size target. (REQ-1, REQ-4)
  * [ ] 1.3 Define CSS/render-blocking asset target. (REQ-1, REQ-5)
  * [ ] 1.4 Define chapter rendering target. (REQ-1, REQ-6)
  * [ ] 1.5 Define annotation processing target. (REQ-1, REQ-7)
  * [ ] 1.6 Define image loading expectations. (REQ-1, REQ-8)
  * [ ] 1.7 Define payload size/shape expectations. (REQ-1, REQ-10)
  * [ ] 1.8 Document known exceptions and follow-ups. (REQ-1)

* [ ] 2. Add public reader request-count guardrails

  * [ ] 2.1 Identify blocking requests on public chapter load. (REQ-3)
  * [ ] 2.2 Remove unnecessary separate metadata requests. (REQ-3)
  * [ ] 2.3 Ensure glossary annotations do not require per-term requests. (REQ-3)
  * [ ] 2.4 Ensure analytics is fire-and-forget/non-blocking. (REQ-3, REQ-11)
  * [ ] 2.5 Avoid export/admin/freshness requests on normal reader load. (REQ-3)
  * [ ] 2.6 Add tests or instrumentation to flag excessive blocking requests where practical. (REQ-3, REQ-15)

* [ ] 3. Optimize public reader API path

  * [ ] 3.1 Review public chapter query path for N+1 patterns. (REQ-2)
  * [ ] 3.2 Use public projections/snapshots where available. (REQ-2)
  * [ ] 3.3 Avoid loading private/admin fields. (REQ-10)
  * [ ] 3.4 Avoid repeated storage reads for same chapter. (REQ-2)
  * [ ] 3.5 Bound optional annotation lookup time. (REQ-2, REQ-7)
  * [ ] 3.6 Return only reader-needed fields. (REQ-10)
  * [ ] 3.7 Add latency/payload tests or benchmark fixture where practical. (REQ-2, REQ-10, REQ-15)

* [ ] 4. Enforce public payload shape

  * [ ] 4.1 Remove admin-only fields from public chapter payload. (REQ-10)
  * [ ] 4.2 Remove raw prompts and diagnostics from public payload. (REQ-10)
  * [ ] 4.3 Avoid returning unrelated full chapter data. (REQ-10)
  * [ ] 4.4 Keep chapter navigation metadata minimal. (REQ-10)
  * [ ] 4.5 Cap public novel list page size. (REQ-10)
  * [ ] 4.6 Ensure glossary annotations respect backend cap. (REQ-10)
  * [ ] 4.7 Add snapshot/schema tests for public payload shape. (REQ-10, REQ-15)

* [ ] 5. Split public reader bundle from admin code

  * [ ] 5.1 Inspect route-level imports for admin components. (REQ-4)
  * [ ] 5.2 Remove admin dashboard/chart imports from public reader path. (REQ-4)
  * [ ] 5.3 Remove glossary editor/admin imports from public reader path. (REQ-4)
  * [ ] 5.4 Remove export admin UI imports from public reader path. (REQ-4)
  * [ ] 5.5 Lazy-load optional heavy public features. (REQ-4)
  * [ ] 5.6 Add build report or bundle analyzer check for reader route. (REQ-4, REQ-15)
  * [ ] 5.7 Document bundle budget and how to inspect it. (REQ-4)

* [ ] 6. Reduce CSS and render-blocking asset cost

  * [ ] 6.1 Identify public reader CSS loaded on route. (REQ-5)
  * [ ] 6.2 Remove admin-only CSS from reader path where possible. (REQ-5)
  * [ ] 6.3 Ensure custom fonts have readable fallback behavior. (REQ-5)
  * [ ] 6.4 Avoid unnecessary third-party CSS. (REQ-5)
  * [ ] 6.5 Add CSS budget report/check where practical. (REQ-5, REQ-15)
  * [ ] 6.6 Add fallback font verification. (REQ-5)

* [ ] 7. Improve chapter rendering path

  * [ ] 7.1 Avoid per-character component rendering. (REQ-6)
  * [ ] 7.2 Render chapter by paragraph/block. (REQ-6)
  * [ ] 7.3 Memoize reader block transformations. (REQ-6)
  * [ ] 7.4 Avoid expensive layout effects over entire chapter. (REQ-6)
  * [ ] 7.5 Avoid rendering hidden duplicate content. (REQ-6)
  * [ ] 7.6 Add long-chapter fixture test. (REQ-6, REQ-15)
  * [ ] 7.7 Document progressive rendering/windowing tradeoffs if needed. (REQ-6, REQ-14)

* [ ] 8. Add glossary annotation performance safeguards

  * [ ] 8.1 Skip annotation processing when user disables highlights. (REQ-7)
  * [ ] 8.2 Group annotations by block. (REQ-7)
  * [ ] 8.3 Sort annotations once per stable input. (REQ-7)
  * [ ] 8.4 Filter invalid annotations early. (REQ-7)
  * [ ] 8.5 Add frontend rendered annotation cap. (REQ-7)
  * [ ] 8.6 Avoid heavy tooltip instance per annotation where possible. (REQ-7)
  * [ ] 8.7 Add many-annotation fixture test. (REQ-7, REQ-15)
  * [ ] 8.8 Add graceful degradation when cap is exceeded. (REQ-7)

* [ ] 9. Optimize public images

  * [ ] 9.1 Identify novel cover image component. (REQ-8)
  * [ ] 9.2 Ensure public-safe image URLs. (REQ-8)
  * [ ] 9.3 Add responsive sizes. (REQ-8)
  * [ ] 9.4 Add explicit width/height or aspect ratio. (REQ-8)
  * [ ] 9.5 Lazy-load below-the-fold images. (REQ-8)
  * [ ] 9.6 Priority-load only likely LCP image. (REQ-8)
  * [ ] 9.7 Add lightweight fallback for broken images. (REQ-8)
  * [ ] 9.8 Add tests/checks for dimensions, lazy behavior, fallback, and no signed/private URLs. (REQ-8, REQ-15)

* [ ] 10. Add public reader caching policy

  * [ ] 10.1 Define which public reader responses are cacheable. (REQ-9)
  * [ ] 10.2 Add cache headers for safe published public chapter responses. (REQ-9)
  * [ ] 10.3 Add cache headers for safe public novel metadata responses. (REQ-9)
  * [ ] 10.4 Prevent public caching for private/unpublished/preview responses. (REQ-9)
  * [ ] 10.5 Invalidate or bypass cache on takedown/tombstone. (REQ-9)
  * [ ] 10.6 Invalidate or version cache on glossary annotation setting changes. (REQ-9)
  * [ ] 10.7 Add tests for cache headers and safety exclusions. (REQ-9, REQ-15)

* [ ] 11. Add cache hit/miss observability where available

  * [ ] 11.1 Record public reader cache hit/miss if metrics exist. (REQ-12)
  * [ ] 11.2 Record public reader API latency if metrics exist. (REQ-12)
  * [ ] 11.3 Record safe payload size where practical. (REQ-12)
  * [ ] 11.4 Record annotation processing duration in development/metrics where practical. (REQ-12)
  * [ ] 11.5 Ensure measurements do not include private content. (REQ-12)
  * [ ] 11.6 Add tests or docs for measurement hooks. (REQ-12)

* [ ] 12. Guard third-party and optional scripts

  * [ ] 12.1 Ensure analytics client does not block first render. (REQ-11)
  * [ ] 12.2 Ensure admin monitoring/dashboard scripts do not load on reader pages. (REQ-11)
  * [ ] 12.3 Lazy-load optional scripts after critical content. (REQ-11)
  * [ ] 12.4 Ensure third-party script failure does not hide reader content. (REQ-11)
  * [ ] 12.5 Add build/dependency inspection check where practical. (REQ-11, REQ-15)

* [ ] 13. Make fallbacks lightweight

  * [ ] 13.1 Review error boundary fallback imports. (REQ-13)
  * [ ] 13.2 Ensure empty states do not import heavy admin/chart components. (REQ-13)
  * [ ] 13.3 Ensure degraded notices do not block chapter render. (REQ-13)
  * [ ] 13.4 Ensure retry logic has backoff or avoids request storms. (REQ-13)
  * [ ] 13.5 Prevent repeated expensive optional feature failures. (REQ-13)
  * [ ] 13.6 Add tests for fallback rendering and retry behavior where practical. (REQ-13, REQ-15)

* [ ] 14. Preserve accessibility and SEO

  * [ ] 14.1 Verify optimized reader still has semantic headings/landmarks. (REQ-14)
  * [ ] 14.2 Verify keyboard/screen-reader access after rendering changes. (REQ-14)
  * [ ] 14.3 Verify SEO metadata does not depend on heavy client-only work where SSR exists. (REQ-14)
  * [ ] 14.4 Verify lazy images do not hide above-the-fold meaningful content. (REQ-14)
  * [ ] 14.5 Review accessibility/SEO impact before any virtualization. (REQ-14)
  * [ ] 14.6 Add tests/manual checks for semantics and metadata preservation. (REQ-14, REQ-15)

* [ ] 15. Add performance regression tests/checks

  * [ ] 15.1 Add public chapter payload shape test. (REQ-15)
  * [ ] 15.2 Add public novel list page size test. (REQ-15)
  * [ ] 15.3 Add long chapter render fixture. (REQ-15)
  * [ ] 15.4 Add many-annotation fixture. (REQ-15)
  * [ ] 15.5 Add cache header/invalidation tests. (REQ-15)
  * [ ] 15.6 Add reader route bundle size report/check. (REQ-15)
  * [ ] 15.7 Add image safety/dimension tests. (REQ-15)
  * [ ] 15.8 Add manual performance checklist for non-automated budgets. (REQ-15)

* [ ] 16. Documentation

  * [ ] 16.1 Document performance budgets. (REQ-1)
  * [ ] 16.2 Document public reader API expectations. (REQ-2, REQ-3)
  * [ ] 16.3 Document bundle budget inspection. (REQ-4)
  * [ ] 16.4 Document long-chapter rendering safeguards. (REQ-6)
  * [ ] 16.5 Document glossary annotation performance rules. (REQ-7)
  * [ ] 16.6 Document image optimization rules. (REQ-8)
  * [ ] 16.7 Document public reader caching policy. (REQ-9)
  * [ ] 16.8 Document accessibility/SEO constraints. (REQ-14)
  * [ ] 16.9 Document manual verification process. (REQ-16)

* [ ] 17. Completion verification

  * [ ] 17.1 Load a normal public chapter and verify request count meets expectation. (REQ-3, REQ-16)
  * [ ] 17.2 Inspect reader bundle and verify admin-heavy code is not included. (REQ-4, REQ-16)
  * [ ] 17.3 Render long chapter fixture and verify page remains usable. (REQ-6, REQ-16)
  * [ ] 17.4 Render many-annotation fixture and verify processing stays bounded or degrades gracefully. (REQ-7, REQ-16)
  * [ ] 17.5 Inspect cover images for optimized public-safe URLs and dimensions. (REQ-8, REQ-16)
  * [ ] 17.6 Request published public content repeatedly and verify cache behavior where configured. (REQ-9, REQ-16)
  * [ ] 17.7 Verify unpublished/private/takedown content is not served from public cache. (REQ-9, REQ-16)
  * [ ] 17.8 Inspect budget checks/reports and verify regressions are visible. (REQ-15, REQ-16)
  * [ ] 17.9 Verify accessibility and SEO structure remains intact after optimization. (REQ-14, REQ-16)
  * [ ] 17.10 Mark `public-reader-performance-budget` complete only after public reader speed, responsiveness, cache safety, and regression checks are established.
