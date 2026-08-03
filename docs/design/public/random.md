# Dokushodo - Random

## Design Task
Design the transient random novel resolving surface.

## Product Context
Choosing Surprise Me resolves a random novel; while resolving, this quiet surface is shown, then the reader is redirected to the novel or to browse with a notice.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

## Page Goal
Borrow a moment of anticipation without noise.

## Audience and Access
All visitors.

## Primary Action
None; automatic redirect.

## Information Hierarchy
- Centered quiet message
- Small spinner
- Automatic redirect

## Desktop Composition
- Centered block with a short line and quiet spinner

## Mobile Composition
- Same centered block

## Page Anatomy
- Public header
- Resolving block
- Public footer

## Key Components
- Resolving block
- Spinner

## Representative Content
- Picking a random novel...

## Normal Settled State
A single quiet line and a small spinner on washi paper.

## Alternate Visual States
- Redirect to a random novel detail page
- Redirect to browse with the notice No novels match your filters when the catalog is empty

## Interaction Cues
- Spinner is quiet
- Redirect is automatic

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
- The exact resolving line
- Automatic redirect behavior

## Avoid
- Slot machine graphics
- Countdowns
- Decorative particles

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
