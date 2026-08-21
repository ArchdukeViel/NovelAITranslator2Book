# Dokushodo - Contact

## Design Task
Design the contact form with name, email, subject, and message.

## Product Context
A direct channel to the operator for questions and problems.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Capture a clear message with valid contact details.

## Audience and Access
All visitors.

## Primary Action
Sending the message.

## Information Hierarchy
- Page heading Contact
- Form card
- Success confirmation

## Desktop Composition
- Centered form card with fields: name, email, subject, message
- Submit button aligned right

## Mobile Composition
- Form full width
- Submit button full width

## Page Anatomy
- Public header
- Form card
- Public footer

## Key Components
- Name field
- Email field
- Subject field
- Message textarea
- Submit button

## Representative Content
- Contact
- Name
- Email
- Subject
- Message
- Send Message

## Normal Settled State
A single quiet card with four fields and one vermillion submit button.

## Alternate Visual States
- Validation errors
- Success state confirming the message was sent
- Empty state before first use

## Interaction Cues
- Submit disabled until required fields are valid
- Success replaces the form with a confirmation

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets

## Preserve Exactly
- Field labels exactly as listed
- Single submit path

## Avoid
- Chat widgets
- Fake response-time promises
- Phone numbers not verified

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
