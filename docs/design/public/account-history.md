# Dokushodo - Reading History

## Design Task
Design the reading history list of chapters opened while signed in.

## Product Context
History is recorded only for signed-in reading sessions.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

## Page Goal
Let a reader return to any previously opened chapter in one click.

## Audience and Access
Signed-in readers only.

## Primary Action
Reopening a chapter from the list.

## Information Hierarchy
- Page heading Reading History
- Description line
- Chronological list of chapters
- Back to Browse link

## Desktop Composition
- Description under the heading
- List rows with novel title, chapter title, and opened timestamp
- Row click opens the chapter

## Mobile Composition
- Same list full width
- Rows with thumbnails omitted to keep density

## Page Anatomy
- Account shell
- Page heading block
- History list
- Public footer

## Key Components
- History row
- Back to Browse link

## Representative Content
- Reading History
- Chapters you have opened while signed in.
- Back to Browse

## Normal Settled State
A quiet chronological list with monospace timestamps and clear row hover.

## Alternate Visual States
- Empty history with the empty illustration and a browse link
- Loading skeleton rows

## Interaction Cues
- Row hover raises border emphasis
- Row click opens the chapter reader

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- empty.png for the empty history

## Preserve Exactly
- The exact description wording
- Chronological order newest first

## Avoid
- Progress percentages not recorded in data
- Grouping by date unless data exists
- Clearing history without confirmation

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
