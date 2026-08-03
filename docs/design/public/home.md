# Dokushodo - Home

## Design Task
Design the landing page as a quiet catalog front door built from data rails.

## Product Context
The site root redirects here. It is the primary discovery surface and the first page most visitors see.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

## Page Goal
Move a visitor from first impression to a reading start in one or two clicks.

## Audience and Access
All visitors, signed in or signed out; the rail set adapts to the session.

## Primary Action
Start Reading on the hero spotlight card.

## Information Hierarchy
- Hero spotlight featuring one novel from the catalog
- Continue Reading rail, signed in only
- New Releases rail
- Recently Updated rail
- Genre rails, one per major genre
- Surprise Me tile
- Footer

## Desktop Composition
- Centered content column with a comfortable max width
- Hero spotlight card: gradient cover on the left, title, author, synopsis excerpt, and a Start Reading button on the right
- Rails below the hero, each with a section title and a horizontal row of novel cards
- Surprise Me tile as the final tile of the last rail

## Mobile Composition
- Spotlight stacks: cover above copy, Start Reading full width
- Rails scroll horizontally with a soft edge fade
- Bottom tab bar remains fixed while rails scroll

## Page Anatomy
- Public header
- Hero spotlight
- Content rails
- Surprise Me tile
- Public footer

## Key Components
- Spotlight card
- Novel card
- Rail section header
- Surprise Me tile
- Public header
- Public footer

## Representative Content
- Start Reading
- Continue Reading
- New Releases
- Recently Updated
- Genre names as rail titles
- Surprise Me

## Normal Settled State
Quiet stacked rails; white cards on washi paper; one vermillion action per card region; nothing moves.

## Alternate Visual States
- Guest view with no Continue Reading rail
- Empty catalog with the empty illustration and a clear next step
- Loading state with quiet skeleton cards

## Interaction Cues
- Hover raises border emphasis on novel cards
- Start Reading uses the vermillion primary button
- Surprise Me presents as a playful but calm tile
- Every novel card is a link to the novel detail page

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
- Rail titles exactly as listed
- The spotlight is derived from the catalog and never labeled as curated
- Surprise Me behavior
- Quiet density with no decorative motion

## Avoid
- Hero carousels, autoplay, or rotating slides
- Fake curation labels or editorial claims
- Confetti or celebratory graphics
- More than one vermillion action per card region

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
