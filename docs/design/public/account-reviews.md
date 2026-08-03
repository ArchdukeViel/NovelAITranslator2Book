# Dokushodo - My Reviews

## Design Task
Design the reader's review list with ratings and deletion.

## Product Context
Reviews the reader published on novels, with the ability to delete them.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

## Page Goal
Show every review the reader wrote and allow removal.

## Audience and Access
Signed-in readers only.

## Primary Action
Deleting a review.

## Information Hierarchy
- Page heading My Reviews
- Review list
- Delete action per review

## Desktop Composition
- Rows with star rating, novel title, review text, and date
- Quiet delete action on each row

## Mobile Composition
- Rows stack with full-width review text
- Delete stays visible but quiet

## Page Anatomy
- Account shell
- Page heading block
- Review list
- Public footer

## Key Components
- Star rating
- Review row
- Delete action

## Representative Content
- My Reviews
- Star ratings filled in accent color
- Delete

## Normal Settled State
A quiet list of review cards with accent-filled stars and one quiet delete action each.

## Alternate Visual States
- Empty state with a browse link
- Delete confirmation state

## Interaction Cues
- Delete requires confirmation
- Star ratings are display only here

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- empty.png for the empty list

## Preserve Exactly
- Accent color for filled stars
- Confirmation before delete

## Avoid
- Edit actions the system does not offer
- Average rating math not present in data

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
