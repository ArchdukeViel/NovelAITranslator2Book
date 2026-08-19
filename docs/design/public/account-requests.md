# Dokushodo - My Requests

## Design Task
Design the request history list with status filtering.

## Product Context
Every request the reader submitted, with review status.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Show where each request stands and provide the full history view.

## Audience and Access
Signed-in readers only.

## Primary Action
Reviewing a request status.

## Information Hierarchy
- Page heading My Requests
- Status filter
- Request list
- Current route `/account/request-novels`

## Desktop Composition
- Filter row above the list
- Rows with novel title, source URL, status badge, and date
- Toggle to expand beyond recent items

## Mobile Composition
- Filter as a horizontal chip row
- Rows stack compactly

## Page Anatomy
- Account shell
- Page heading block
- Filter row
- Request list
- Public footer

## Key Components
- Status badge
- Request row
- Status filter
- Full history toggle

## Representative Content
- My Requests
- Pending, Approved, Rejected, Completed
- Full request history

## Normal Settled State
A tidy filtered list with quiet status badges and monospace URLs.

## Alternate Visual States
- Empty state with a request a novel action
- Filter with no matches

## Interaction Cues
- Filter applies instantly
- Rows link to the requested novel when approved

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- brand-logo.svg / empty state fallback

## Preserve Exactly
- Status names exactly as listed
- Full history toggle behavior

## Avoid
- Edit or delete actions the system does not offer
- Fake approval estimates

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
