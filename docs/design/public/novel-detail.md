# Dokushodo - Novel Detail

## Design Task
Design the novel detail page with overview, chapters, and community reviews.

## Product Context
The destination of every novel card and the entry point for reading, saving, and reviewing.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

## Page Goal
Give a reader the full picture of a novel and put reading one click away.

## Audience and Access
All visitors; signed-in readers get save, continue, and review actions.

## Primary Action
Continue Reading or Read First Chapter for signed-in readers; Save to Library as the secondary action.

## Information Hierarchy
- Novel header: gradient cover, title in serif, author, source title label, status badge, actions
- Tabs: Overview, Chapters, Reviews
- Overview: synopsis, metadata, tags
- Chapters: filter and search, First unread anchor, chapter list
- Reviews: community reviews with star ratings
- Footer

## Desktop Composition
- Left column with cover, title, author, source title label, and status badge
- Right side actions: Continue Reading and Save to Library
- Tab bar below the header with Overview, Chapters, and Reviews
- Chapters list with chapter numbers, titles, and translated labels
- Sidebar metadata: language, author, year, tags

## Mobile Composition
- Compact header with smaller cover, stacked title and badge
- Sticky bottom action bar with Read and Save
- Tabs scroll horizontally
- Chapter list rows with title and translated label

## Page Anatomy
- Public header
- Novel header block
- Tab bar
- Active tab panel
- Sticky mobile action bar
- Public footer

## Key Components
- Gradient cover with fallback
- Status badge
- Tab bar
- Chapter list with search and filter
- First unread anchor
- Review card with star rating
- Save to Library button
- Continue Reading button

## Representative Content
- Novel title and author
- Source title label followed by the source name
- Status badge: Ongoing, Completed, Hiatus, or Dropped
- Overview, Chapters, Reviews
- First unread
- Continue Reading, Save to Library

## Normal Settled State
A calm two-column layout: cover and title on the left, synopsis below, tabbed content beneath, one vermillion primary action.

## Alternate Visual States
- Guest view without save or continue actions
- Novel with no chapters yet: quiet empty state
- Novel not from a known source: no source title label
- Loading state with cover placeholder

## Interaction Cues
- Tab switch is instant with clear active underline
- Save to Library toggles its label and filled state
- First unread scrolls the chapter list to the reading anchor
- Star ratings fill in accent color

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- brand-mark.png
- Gradient cover generated from title and author
- empty.png for no-chapters state

## Preserve Exactly
- Tab labels exactly as listed
- Source title label wording
- Status badge colors from the status system
- Fallback cover with readable title lettering

## Avoid
- Spoiler copy in representative content
- Carousels of related novels without a title
- More than one primary action in the header
- Fake chapter counts

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
