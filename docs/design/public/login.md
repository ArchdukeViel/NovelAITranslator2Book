# Dokushodo - Login

## Design Task
Design the sign-in and sign-up surface with Google and email paths.

## Product Context
The only entry into the account area. Mode is sign in or sign up, controlled by a mode parameter; a next parameter returns the reader where they were headed.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Complete authentication in the fewest steps with a clear path choice.

## Audience and Access
All visitors; no admin creation is possible here.

## Primary Action
Continue with Google, or submit the email form.

## Information Hierarchy
- Centered card with brand mark
- Mode heading: Sign in to Dokushodo or Create your Dokushodo account
- Continue with Google button
- Divider
- Email and password fields
- Submit: Sign in with email or Create one
- Mode switch link

## Desktop Composition
- Single centered card on washi background
- Brand mark above the heading
- Full width buttons and fields

## Mobile Composition
- Card fills most of the viewport
- Fields and buttons full width

## Page Anatomy
- Public header
- Auth card
- Public footer

## Key Components
- Brand mark
- Google button
- Email field
- Password field
- Submit button
- Mode switch link

## Representative Content
- Sign in to Dokushodo
- Create your Dokushodo account
- Continue with Google
- Sign in with email
- Create one

## Normal Settled State
One quiet centered card with a vermillion submit button and a Google button above a divider.

## Alternate Visual States
- Sign up mode with the alternate heading and submit
- Validation errors on fields
- Redirect state after success

## Interaction Cues
- Mode switch swaps heading and submit label
- Submit disabled until fields are valid

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
- Exact headings and labels listed above
- Google as the only external login provider
- No admin signup path

## Avoid
- Decorative illustrations
- Social login buttons beyond Google
- Marketing copy about benefits

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
