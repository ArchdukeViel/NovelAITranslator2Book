# Dokushodo - Chapter Reader

## Design Task
Design the reading surface with theme, width, and typography controls.

## Product Context
The core reading experience. Reached from novel detail and continue-reading entry points. Browser chrome is suppressed on this route.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Keep the reader in the text with controls that are present but invisible until needed.

## Audience and Access
All visitors with a signed-in session for progress tracking; guests can read without saving progress.

## Primary Action
Turning the page via next chapter.

## Information Hierarchy
- Minimal top bar with back link and chapter title
- Reading pane with serif text
- Settings drawer for theme, width, and font size
- Previous and next chapter actions

## Desktop Composition
- Centered reading column with width options narrow, default, and wide
- Theme choices light, dark, and sepia
- Font size controls
- Progress bar along the top edge
- Previous chapter and Next chapter links at the end of the text

## Mobile Composition
- Full-height reading pane
- Top bar collapses to back link and title
- Settings open from a compact control
- Swipe or link navigation between chapters

## Page Anatomy
- Reader top bar
- Progress bar
- Reading pane
- Settings drawer
- Chapter footer navigation

## Key Components
- Back to novel link
- Chapter title
- Theme picker
- Width picker
- Font size controls
- Progress bar
- Previous and Next chapter links

## Representative Content
- Novel title and chapter title
- Previous chapter, Next chapter
- Theme labels: Light, Dark, Sepia
- Width labels: Narrow, Default, Wide

## Normal Settled State
Nothing but text on a calm background; the top bar is minimal and the settings drawer is closed.

## Alternate Visual States
- Sepia theme
- Dark theme with near-black background
- Settings drawer open over dimmed text
- First chapter with no previous link; last chapter with no next link

## Interaction Cues
- Controls fade or remain quiet until hover or focus
- Progress bar fills with the primary color
- Theme switch applies instantly
- Keyboard shortcuts for next and previous chapter where supported

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- brand-mark.png in the reader top bar

## Preserve Exactly
- Theme names exactly as listed
- Reading column widths
- Serif type for body text
- Chrome suppression on the route

## Avoid
- Ads, share buttons, or social widgets inside the reading pane
- Decorative illustration in the text column
- Auto-scroll or autoplay
- Emoji or icons inside the chapter body

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
