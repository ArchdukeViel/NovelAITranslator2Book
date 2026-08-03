# Dokushodo - Tag

## Design Task
Design the tag preset page as the browse surface scoped to one tag.

## Product Context
Tag links land here from novel detail pages. It renders the browse page with a tag preset filter.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

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
