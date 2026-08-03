# Dokushodo - Home

## Design Task
Design the landing page as a quiet catalog front door: a two-column editorial layout with a main discovery feed and a calm right-hand sidebar of catalog widgets, opened by a collapsible fixed left navigation sidebar.

## Product Context
The site root redirects here. It is the primary discovery surface and the first page most visitors see. The layout replicates the "Dokushodo - Fixed Sidebar & Transparent Logo" Stitch screen (project Minimalist Webnovel Portal, screen `1794eb02d11a407b9b6343d727670125`).

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels inspired by Japanese *Bunko-bon* (pocket-sized paperback) aesthetics. The visual style is Contemporary Minimalism with Tactile Editorial influences: a washi paper (#F9F6F0) background with sumi ink (#1A1A1A) text, EB Garamond serif typography for titles and reading content, Hanken Grotesk sans-serif for UI and metadata, shuji vermillion (#BD3E2C) reserved for primary focal actions and brand markers, and muted obsidian (#212529) for borders and secondary surfaces. Cards use Bunko-style vertical layout with subtle paper borders. The desktop shell pairs a slim top header (hamburger + transparent brand logo, inline nav, search overlay trigger, theme toggle, user menu) with a collapsible fixed left sidebar for site navigation, above a persistent footer with catalog, help, legal, and account links. Mobile features a compact header and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Imagery is limited to the transparent brand mark, gradient/bookplate covers generated from title and author, and restrained illustrations for empty, error, and maintenance states. Motion is subtle and short, never decorative. The platform tells the truth: it never invents views, reader counts, ratings, or spender leaderboards. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Move a visitor from first impression to a reading start in one or two clicks.

## Audience and Access
All visitors, signed in or signed out; the rail set and sidebar adapt to the session.

## Primary Action
Start Reading on the hero spotlight card.

## Information Hierarchy
- Hero spotlight featuring one novel from the catalog
- Discovery banner tiles: Random Novel and Request Novel
- Continue Reading rail, signed in only
- New Releases grid
- Recently Updated list
- Genre rails, one per major genre
- Surprise Me callout
- Right sidebar: Novel Ranking, Longest Series, Most Chapters
- Footer

## Desktop Composition
- Wide content column (max ~1600px) split into a 12-column grid: main feed spans 8 columns, sidebar spans 4 (3 at very wide)
- Fixed left sidebar (240px) hidden by default; it slides in from the header hamburger and is dismissed by the backdrop, the close control, or Escape
- Hero spotlight card at the top of the feed: eyebrow "Spotlight" in vermillion, serif title, source title, metadata, synopsis, genre chips, and a vermillion Start Reading button beside an asymmetric cover card
- Two half-width discovery banner tiles beneath the hero (Random Novel, Request Novel)
- New Releases as a 5-column Bunko card grid (2 columns on small screens) under a bordered section header with a "See More" control
- Recently Updated as a stacked list of rows (cover thumbnail, relative time, title, latest chapter) inside a bordered panel
- Genre rails and the Surprise Me callout at the foot of the feed
- Right sidebar widgets stacked vertically, each a bordered panel with a small "See More" control

## Mobile Composition
- The two-column grid collapses to a single stacked column: hero, banner tiles, Continue Reading, New Releases (2-column grid), Recently Updated, genre rails, Surprise Me, then the sidebar widgets
- Spotlight stacks: cover above copy, Start Reading full width
- New Releases grid stays 2 columns with compact Bunko cards
- The fixed bottom tab bar remains while content scrolls; the sidebar opens as a full-height overlay drawer

## Page Anatomy
- Public header (hamburger, brand, inline nav, search, theme, user)
- Collapsible fixed left sidebar
- Hero spotlight
- Discovery banner tiles
- Continue Reading rail
- New Releases grid
- Recently Updated list
- Genre rails
- Surprise Me callout
- Right sidebar widgets
- Public footer

## Key Components
- Spotlight card
- Bunko novel card
- Banner tile
- Recent update row
- Ranked sidebar item
- Trending/chapters sidebar item
- Fixed sidebar
- Public header
- Public footer

## Representative Content
- Start Reading
- Novel details
- Random Novel / Let chance decide
- Request Novel / Ask for a translation
- Continue Reading
- New Releases
- Recently Updated
- Genre names as rail titles
- Novel Ranking
- Longest Series
- Most Chapters
- See More
- Surprise Me
- View Full Catalog

## Normal Settled State
Calm two-column editorial layout; quiet Bunko cards on washi paper; one vermillion action per card region; sidebar widgets present only with real catalog data; nothing moves.

## Alternate Visual States
- Guest view with no Continue Reading rail
- Empty catalog with the empty illustration and a clear next step
- Loading state with quiet skeleton cards

## Interaction Cues
- Hover lifts Bunko cards with a vermillion border emphasis
- Start Reading uses the vermillion primary button
- The hamburger opens the fixed sidebar; backdrop, close control, and Escape dismiss it
- Every novel card, row, and widget item links to its novel detail page
- Sidebar and discovery tiles present as calm, quiet surfaces

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the sidebar drawer (Escape to close), the search overlay, and the mobile tab bar
- The sidebar toggle exposes `aria-expanded` and `aria-controls`; the drawer is labeled `Site navigation`
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- brand-mark.png from the Dokushodo brand asset pack (transparent logo)
- Gradient book covers generated from novel title and author
- empty.png illustration for empty states where listed

## Preserve Exactly
- Section and widget titles exactly as listed
- The spotlight is derived from the catalog and never labeled as curated
- Surprise Me behavior
- Quiet density with no decorative motion
- No invented metrics: never show views, reader counts, ratings, or spender leaderboards. Sidebar widgets are derived from real catalog fields (translated chapters, chapter count, added date) and use honest labels only.

## Avoid
- Hero carousels, autoplay, or rotating slides
- Fake curation labels or editorial claims
- Confetti or celebratory graphics
- More than one vermillion action per card region
- "Trending", "Top Spenders", "Most Read", or view/rating counts presented as if they were live metrics

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
