# Dokushodo - Request Novel

## Design Task
Design the request form for novels from supported sources.

## Product Context
Readers request novels that are not yet in the catalog. Requests are reviewed before approval.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

## Page Goal
Capture a source URL and optional details in the fewest steps.

## Audience and Access
All visitors; signed-in readers can track requests in My Requests.

## Primary Action
Submit Request.

## Information Hierarchy
- Page title and short description
- Request form
- Supported sources list
- Review notice

## Desktop Composition
- Two-column layout: form on the left, Supported Sources card on the right
- Form fields: Source URL with placeholder https://example.com/novel, Details optional textarea
- Submit Request button aligned right

## Mobile Composition
- Single column: form, then sources card, then notice
- Submit button full width

## Page Anatomy
- Public header
- Page heading block
- Request form card
- Supported Sources card
- Public footer

## Key Components
- URL input
- Details textarea
- Submit Request button
- Supported Sources list
- Review notice

## Representative Content
- Request a novel from a supported source.
- Source URL
- Details (optional)
- Submit Request
- Supported Sources
- Kakuyomu, Syosetu, Syosetu18
- Requests are reviewed before they are added.

## Normal Settled State
A clean two-column form page with one vermillion submit button and a quiet sources card.

## Alternate Visual States
- Success state confirming the request was received
- Validation errors on the URL field
- Signed-out state prompting sign in to track the request

## Interaction Cues
- Submit disabled until the URL is valid
- Source names are links to the source websites
- Success clears the form and shows a confirmation

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
- Supported source names exactly as listed
- The review notice wording
- Placeholder format for the URL field

## Avoid
- Logos or branding of the sources rendered large
- Fake queue positions or wait times
- Multiple submit paths

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
