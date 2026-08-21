# Dokushodo - Ranking

## Design Task
Design the live ranking page with period tabs and truthful data availability states.

## Product Context
Rankings are derived from distinct novel-detail viewers retained by privacy-safe analytics. Daily, Weekly, and Monthly are the only periods; All Time is not offered.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Present API-backed distinct novel-detail-view rankings without fabricating any data.

## Audience and Access
All visitors.

## Primary Action
Select Daily, Weekly, or Monthly to request the corresponding ranking window.

## Information Hierarchy
- Page title Ranking
- Period tabs: Daily, Weekly, Monthly
- Metric label: Unique novel-detail views
- Ranked rows when data exists
- Loading, unavailable, and no-data states

## Desktop Composition
- Title with a quiet metric badge reading Unique novel-detail views
- Tab bar for periods
- Ranking list with rank, cover, title, and unique-view count

## Mobile Composition
- Compact title with the notice below
- Tabs scroll horizontally
- Rows show rank, title, cover treatment, and distinct viewer count

## Page Anatomy
- Public header
- Page heading block
- Period tabs
- Ranking table
- Public footer

## Key Components
- Metric/status badge
- Period tabs
- Ranking list
- Loading and empty-state treatment

## Representative Content
- Ranking
- Unique novel-detail views
- Daily, Weekly, Monthly

## Normal Settled State
A quiet ranked list when analytics has retained data, with counts labeled as distinct novel-detail viewers and no fabricated rows.

## Alternate Visual States
- Loading skeleton rows
- Analytics disabled state
- No retained data state
- Recoverable service error

## Interaction Cues
- Tabs request their corresponding 24-hour, 7-day, or 30-day period
- Ranked rows link to the current plural novel-detail route

## Data Contract
- The page consumes `GET /api/public/rankings?period=daily|weekly|monthly&limit=...`
- Rows use the API's `unique_views` metric, representing distinct novel-detail viewers
- Analytics-disabled, no-data, unavailable, and recoverable-error states remain explicit
- The weekly result powers the homepage Trending widget; All Time is not offered

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- brand-mark.png

## Preserve Exactly
- Current period labels and metric wording
- Empty/unavailable states remain explicit
- No fabricated scores, ranks, or All Time claims

## Avoid
- Fake rankings, placeholder novels, or chapter-count popularity
- Cheerful promo copy
- Charts or sparklines with invented data

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
