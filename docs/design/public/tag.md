# Dokushodo - Tag

## Design Task
Design the tag preset page as the browse surface scoped to one tag.

## Product Context
Tag links land here from novel detail pages. It renders the browse page with a tag preset filter.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Present every novel carrying the selected tag in a scoped, browsable grid.

## Audience and Access
All visitors; tag is a catalog-level scope.

## Primary Action
Opening a novel card from the filtered grid.

## Information Hierarchy
- Page title with the tag name
- Active preset chip showing the tag filter
- Standard toolbar, results grid, and pagination

## Desktop Composition
- Same composition as browse with the tag preset chip in the toolbar
- Unfiltered browse link beside the chip

## Mobile Composition
- Same structure as browse on mobile
- Preset chip sits in the filter summary row

## Page Anatomy
- Public header
- Page heading block
- Toolbar with preset chip
- Results grid
- Public footer

## Key Components
- Preset chip
- Search field
- Filter and sort controls
- Novel card
- Pagination

## Representative Content
- Tag name as the page title
- Preset chip reading Tag: followed by the tag name
- Browse all novels link to clear the preset

## Normal Settled State
A tag-titled grid with one quiet chip marking the scope.

## Alternate Visual States
- Empty tag with the empty illustration and a browse all novels action
- Loading skeleton grid

## Interaction Cues
- The preset chip is removable and keyboard operable
- Card hover raises border emphasis

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- brand-mark.png from the Dokushodo brand asset pack
- Gradient book covers generated from novel title and author
- empty.png illustration for empty states where listed

## Preserve Exactly
- Tag name in the title exactly as it appears on novel cards
- Chip label format Tag: name

## Avoid
- Tag cloud or decorative tag graphics
- Invented tag definitions

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
