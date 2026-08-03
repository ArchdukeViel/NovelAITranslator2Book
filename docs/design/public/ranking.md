# Dokushodo - Ranking

## Design Task
Design the ranking page with honest unavailable state and period tabs.

## Product Context
Rankings are not live yet. The page must look complete while stating plainly that it is not live.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

## Page Goal
Present the ranking structure without fabricating any data.

## Audience and Access
All visitors.

## Primary Action
None; the page is informational until rankings go live.

## Information Hierarchy
- Page title Ranking
- Period tabs: Daily, Weekly, Monthly, All Time
- Quiet not-live notice
- Empty ranking table placeholders

## Desktop Composition
- Title with a quiet badge reading Ranking is not live yet
- Tab bar for periods
- Ranking table with rank, cover, title, and score columns left empty or with placeholders

## Mobile Composition
- Compact title with the notice below
- Tabs scroll horizontally
- Placeholder rows with quiet skeletons

## Page Anatomy
- Public header
- Page heading block
- Period tabs
- Ranking table
- Public footer

## Key Components
- Notice badge
- Period tabs
- Ranking table
- Placeholder rows

## Representative Content
- Ranking
- Ranking is not live yet
- Daily, Weekly, Monthly, All Time

## Normal Settled State
A complete-looking page with one honest notice badge and empty table rows; no numbers anywhere.

## Alternate Visual States
- Loading skeleton rows
- Future live state with real ranked rows

## Interaction Cues
- Tabs are selectable but all periods show the same honest state
- No row interactions

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
- The exact notice wording
- Period tab labels
- No fabricated scores or ranks

## Avoid
- Fake rankings or placeholder novels
- Cheerful promo copy
- Charts or sparklines with invented data

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
