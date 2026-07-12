# requirements.md

# Requirements: Public Reader Performance Budget

## Introduction

The public reader needs measurable performance budgets and safeguards so public novel and chapter pages stay fast, responsive, and safe as features are added. This includes frontend bundle limits, API latency, payload size, image optimization, caching, long-chapter rendering, glossary annotation overhead, and regression checks.

## Requirement 1: Performance budget definition

### User story

As a maintainer, I want explicit performance budgets so performance regressions can be detected and discussed.

### Acceptance criteria

1. WHEN this spec is implemented THEN public reader performance budgets SHALL be documented.
2. WHEN budgets are documented THEN they SHALL include backend API latency targets.
3. WHEN budgets are documented THEN they SHALL include frontend bundle size targets.
4. WHEN budgets are documented THEN they SHALL include rendering responsiveness targets.
5. WHEN budgets are documented THEN they SHALL include image size/loading expectations.
6. WHEN budgets are documented THEN they SHALL include payload size or response shape expectations.
7. WHEN actual architecture cannot meet a budget yet THEN the exception SHALL be documented with a follow-up task.

## Requirement 2: Public reader API latency

### User story

As a reader, I want novel and chapter pages to load quickly.

### Acceptance criteria

1. WHEN public novel list API is requested THEN it SHOULD complete within the configured latency budget.
2. WHEN public novel detail API is requested THEN it SHOULD complete within the configured latency budget.
3. WHEN public chapter API is requested THEN it SHOULD complete within the configured latency budget.
4. WHEN public reader fallback/snapshot API is used THEN it SHOULD complete within the configured latency budget.
5. WHEN optional annotation lookup is slow THEN it SHALL not block beyond the configured optional feature timeout.
6. WHEN API latency exceeds budget in tests or measurement THEN the regression SHALL be visible.
7. WHEN public APIs fail due to timeout THEN they SHALL return safe errors according to existing error handling policy.

## Requirement 3: API request count

### User story

As a reader, I want the public chapter page to avoid many blocking network requests.

### Acceptance criteria

1. WHEN a public chapter page loads THEN it SHOULD use one primary chapter payload request.
2. WHEN glossary annotations are enabled THEN they SHOULD be included in the primary response or loaded non-blockingly.
3. WHEN analytics are enabled THEN analytics SHALL not block the first reader render.
4. WHEN export/freshness/admin-only data exists THEN it SHALL not be fetched on normal public reader load unless visible and needed.
5. WHEN reader settings are local-only THEN no settings API request SHALL be required.
6. WHEN tests or instrumentation count requests THEN unnecessary extra blocking requests SHALL be flagged.

## Requirement 4: Public reader bundle budget

### User story

As a reader, I want the public reader to load only the JavaScript needed for reading.

### Acceptance criteria

1. WHEN public reader route bundle is built THEN admin-only code SHALL not be included intentionally.
2. WHEN metrics/admin analytics/chart code exists THEN it SHALL not load on public reader routes.
3. WHEN glossary editor/admin code exists THEN it SHALL not load on public reader routes.
4. WHEN export admin UI code exists THEN it SHALL not load on public reader routes.
5. WHEN optional heavy features are needed THEN they SHOULD be lazy-loaded.
6. WHEN bundle size exceeds budget THEN the build or report SHOULD flag the regression.
7. WHEN reader route loads THEN core chapter text rendering SHALL not depend on heavy optional chunks.

## Requirement 5: CSS and render-blocking asset budget

### User story

As a reader, I want styles to load quickly without blocking reading unnecessarily.

### Acceptance criteria

1. WHEN public reader page loads THEN critical CSS SHALL be bounded.
2. WHEN admin-only styles exist THEN they SHOULD not be required for public reader pages.
3. WHEN custom fonts are used THEN font loading SHALL not indefinitely block text rendering.
4. WHEN third-party CSS exists THEN it SHALL not be loaded on reader pages unless needed.
5. WHEN CSS budget is exceeded THEN the regression SHOULD be visible in build/report.
6. WHEN fonts fail to load THEN readable fallback fonts SHALL be used.

## Requirement 6: Chapter rendering performance

### User story

As a reader, I want long chapters to remain responsive.

### Acceptance criteria

1. WHEN a normal chapter renders THEN it SHALL render within the configured render budget where practical.
2. WHEN a long chapter renders THEN the UI SHALL remain usable and avoid obvious freezes where practical.
3. WHEN chapter text is rendered THEN the frontend SHALL avoid per-character component rendering.
4. WHEN reader blocks exist THEN rendering SHOULD operate by block or paragraph.
5. WHEN optional processing fails or is too slow THEN chapter text SHALL remain visible.
6. WHEN tests render a long chapter fixture THEN render performance SHALL be measured or guarded.
7. WHEN performance safeguards require progressive rendering THEN accessibility and SEO constraints SHALL be considered.

## Requirement 7: Glossary annotation performance

### User story

As a reader, I want glossary highlights to be useful without making chapters slow.

### Acceptance criteria

1. WHEN glossary annotations are disabled by user preference THEN annotation processing SHALL be skipped where practical.
2. WHEN glossary annotations are enabled THEN annotations SHALL be grouped and processed efficiently.
3. WHEN block annotations exist THEN processing SHALL group by block before rendering.
4. WHEN annotation count exceeds frontend-safe limit THEN the frontend SHALL degrade gracefully.
5. WHEN invalid annotations exist THEN they SHALL be filtered without expensive repeated work.
6. WHEN annotations are rendered THEN the system SHOULD avoid one heavy tooltip instance per annotation if avoidable.
7. WHEN tests process many annotations THEN processing time or complexity SHALL be guarded.

## Requirement 8: Image optimization

### User story

As a reader, I want cover and chapter images to load efficiently without layout shift.

### Acceptance criteria

1. WHEN novel cover images are displayed THEN they SHALL use optimized public-safe URLs.
2. WHEN images are below the fold THEN they SHOULD be lazy-loaded.
3. WHEN an image is likely the LCP candidate THEN it MAY be priority-loaded.
4. WHEN images are rendered THEN width and height or aspect ratio SHOULD be specified to reduce layout shift.
5. WHEN responsive image support exists THEN appropriate sizes SHALL be used.
6. WHEN image URL is generated THEN it SHALL not be a signed/private URL.
7. WHEN image fails to load THEN a lightweight fallback SHALL be shown.
8. WHEN tests inspect image metadata THEN private URLs and missing dimensions SHOULD be flagged where practical.

## Requirement 9: Public reader caching

### User story

As a reader, I want repeated public content loads to be fast while unpublished content remains protected.

### Acceptance criteria

1. WHEN a published public chapter response is safe to cache THEN caching SHOULD be applied.
2. WHEN a published public novel metadata response is safe to cache THEN caching SHOULD be applied.
3. WHEN content is unpublished THEN it SHALL not be served from public cache.
4. WHEN content is private or preview-only THEN it SHALL not be publicly cached.
5. WHEN content is taken down or tombstoned THEN relevant public cache SHALL be invalidated or bypassed.
6. WHEN glossary annotation settings change THEN affected cached reader responses SHALL be invalidated or versioned.
7. WHEN cache headers are emitted THEN they SHALL match publication safety policy.
8. WHEN tests run THEN cache headers/invalidation behavior SHALL be covered where practical.

## Requirement 10: Payload size and response shape

### User story

As a reader, I want APIs to return only the data needed for reading.

### Acceptance criteria

1. WHEN public chapter payload is returned THEN it SHALL not include admin-only fields.
2. WHEN public chapter payload is returned THEN it SHALL not include raw prompts or diagnostics.
3. WHEN public chapter payload is returned THEN it SHALL not include unrelated chapters unless needed for navigation.
4. WHEN chapter navigation metadata is returned THEN it SHOULD be minimal.
5. WHEN glossary annotations are returned THEN they SHALL be capped by backend policy.
6. WHEN public novel list is returned THEN page size SHALL be capped.
7. WHEN payload size exceeds budget in tests/fixtures THEN the regression SHOULD be visible.

## Requirement 11: Third-party and optional script cost

### User story

As a reader, I want the reader page to avoid unnecessary scripts.

### Acceptance criteria

1. WHEN analytics are enabled THEN analytics script/client SHALL not block first content render.
2. WHEN admin monitoring or dashboard scripts exist THEN they SHALL not load on public reader pages unless explicitly needed.
3. WHEN optional scripts are needed THEN they SHOULD load after critical reader content.
4. WHEN third-party scripts fail THEN reader content SHALL still render.
5. WHEN tests or build analysis run THEN public reader script dependencies SHOULD be inspectable.

## Requirement 12: Performance measurement hooks

### User story

As a maintainer, I want measurement hooks so reader performance can be monitored and debugged.

### Acceptance criteria

1. WHEN public reader API responds THEN latency SHOULD be recorded by existing metrics if available.
2. WHEN public reader payload is generated THEN payload size MAY be recorded or test-checked.
3. WHEN reader route renders THEN frontend render timing MAY be recorded in development or metrics.
4. WHEN annotation processing occurs THEN processing duration MAY be measured in development or metrics.
5. WHEN cache is used THEN cache hit/miss SHOULD be observable.
6. WHEN measurements are logged THEN they SHALL not include private content.
7. WHEN metrics infrastructure is absent THEN this spec SHALL still add tests/checks where practical.

## Requirement 13: Error and degraded state performance

### User story

As a reader, I want fallback states to load quickly and not make failures worse.

### Acceptance criteria

1. WHEN an error boundary fallback renders THEN it SHALL be lightweight.
2. WHEN an empty state renders THEN it SHALL not load heavy admin or chart components.
3. WHEN degraded reader notice appears THEN it SHALL not block chapter text rendering.
4. WHEN retry is available THEN retry logic SHALL avoid request storms.
5. WHEN optional feature fails THEN fallback SHALL avoid repeatedly re-running expensive failing work.
6. WHEN tests simulate failures THEN fallback rendering SHALL remain lightweight where practical.

## Requirement 14: Accessibility and SEO preservation

### User story

As a reader or crawler, I want performance optimizations to preserve accessibility and SEO.

### Acceptance criteria

1. WHEN long chapter rendering is optimized THEN semantic reader structure SHALL remain intact.
2. WHEN content is progressively rendered THEN keyboard and screen-reader access SHALL remain acceptable.
3. WHEN public chapter page is rendered with SEO support THEN metadata SHALL not depend on heavy client-side work where SSR is available.
4. WHEN images are lazy-loaded THEN above-the-fold meaningful content SHALL remain visible.
5. WHEN virtualized rendering is introduced THEN accessibility and SEO impact SHALL be reviewed.
6. WHEN tests or manual review run THEN performance changes SHALL not remove headings, landmarks, or canonical metadata.

## Requirement 15: Test and regression coverage

### User story

As a maintainer, I want performance checks so future changes do not silently slow the reader.

### Acceptance criteria

1. WHEN tests run THEN they SHOULD include public chapter payload shape checks.
2. WHEN tests run THEN they SHOULD include public novel list page size checks.
3. WHEN tests run THEN they SHOULD include long chapter render fixture.
4. WHEN tests run THEN they SHOULD include many-annotation fixture.
5. WHEN tests run THEN they SHOULD include cache header/invalidation tests where practical.
6. WHEN build runs THEN public reader bundle size SHOULD be reported or checked.
7. WHEN image components are tested THEN public/private URL and dimension behavior SHOULD be covered.
8. WHEN performance budgets cannot be automated THEN a manual checklist SHALL be documented.

## Requirement 16: Completion verification

### User story

As an operator, I want a clear verification path so the public reader is considered performant only after core flows meet budget expectations.

### Acceptance criteria

1. WHEN a normal public chapter loads THEN it SHALL stay within documented request-count expectations.
2. WHEN public reader bundle is inspected THEN admin-heavy code SHALL not be included.
3. WHEN a long chapter fixture is rendered THEN the page SHALL remain usable.
4. WHEN many annotations are present THEN annotation processing SHALL not block the reader beyond documented limits or shall degrade gracefully.
5. WHEN cover images are inspected THEN they SHALL use public-safe optimized URLs and dimensions.
6. WHEN published public content is requested repeatedly THEN cache behavior SHALL improve repeat performance where configured.
7. WHEN unpublished/private/takedown content exists THEN it SHALL not be served from public cache.
8. WHEN budget checks are inspected THEN regressions SHALL be visible through tests, build reports, or documented manual checks.
