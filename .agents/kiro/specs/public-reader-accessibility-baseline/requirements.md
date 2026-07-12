# requirements.md

# Requirements: Public Reader Accessibility Baseline

## Introduction

The public reader must be usable by readers who rely on keyboard navigation, screen readers, zoom, high contrast, reduced motion, and accessible controls. This spec defines the baseline accessibility requirements for public novel pages, chapter pages, reader controls, settings, glossary annotations, and fallback states.

## Requirement 1: Semantic page structure

### User story

As a screen-reader user, I want public reader pages to have semantic structure so I can navigate the page efficiently.

### Acceptance criteria

1. WHEN a public reader page is rendered THEN it SHALL include a main landmark.
2. WHEN a chapter page is rendered THEN chapter content SHALL be inside an article or equivalent semantic region.
3. WHEN chapter navigation exists THEN it SHALL be inside a navigation landmark or have an accessible navigation label.
4. WHEN a page has header content THEN it SHOULD use a header/banner landmark.
5. WHEN a page has footer content THEN it SHOULD use a footer/contentinfo landmark.
6. WHEN landmarks are used THEN they SHALL not be duplicated confusingly.
7. WHEN tests inspect the page THEN main content SHALL be discoverable by role or landmark.

## Requirement 2: Heading structure

### User story

As a reader using assistive technology, I want clear headings so I can understand the page hierarchy.

### Acceptance criteria

1. WHEN a novel page is rendered THEN it SHALL have one clear `h1`.
2. WHEN a chapter page is rendered THEN it SHALL have one clear `h1`.
3. WHEN sections exist under the main heading THEN they SHALL use appropriate heading levels.
4. WHEN visual styling requires large text THEN it SHALL not misuse heading levels.
5. WHEN title data is missing THEN a safe fallback heading SHALL be rendered.
6. WHEN tests inspect headings THEN heading order SHOULD be logical.

## Requirement 3: Skip links

### User story

As a keyboard user, I want skip links so I can bypass repeated navigation.

### Acceptance criteria

1. WHEN a public reader page loads THEN it SHALL include a skip link to main content.
2. WHEN the skip link receives focus THEN it SHALL be visible.
3. WHEN the skip link is activated THEN focus SHALL move to main content or the main heading.
4. WHEN chapter navigation is long or repeated THEN an additional skip link to chapter content SHOULD be available.
5. WHEN tests use keyboard focus THEN the skip link SHALL be reachable near the beginning of tab order.

## Requirement 4: Keyboard navigation

### User story

As a keyboard-only user, I want to read and navigate chapters without using a mouse.

### Acceptance criteria

1. WHEN pressing Tab THEN all interactive controls SHALL be reachable.
2. WHEN pressing Shift+Tab THEN focus SHALL move backward through interactive controls.
3. WHEN a button has focus THEN Enter or Space SHALL activate it.
4. WHEN a link has focus THEN Enter SHALL activate navigation.
5. WHEN a modal, popover, or settings panel is open THEN Escape SHOULD close it where appropriate.
6. WHEN keyboard navigation reaches the reader THEN focus order SHALL follow visual/logical order.
7. WHEN a keyboard user navigates the page THEN there SHALL be no keyboard trap.
8. WHEN tests simulate keyboard navigation THEN main reader controls SHALL be reachable and operable.

## Requirement 5: Visible focus states

### User story

As a keyboard user, I want visible focus indicators so I know where I am on the page.

### Acceptance criteria

1. WHEN a link receives focus THEN a visible focus state SHALL be shown.
2. WHEN a button receives focus THEN a visible focus state SHALL be shown.
3. WHEN an input or select receives focus THEN a visible focus state SHALL be shown.
4. WHEN glossary highlights are focusable THEN they SHALL have visible focus state.
5. WHEN focus state appears in light theme THEN it SHALL be visible.
6. WHEN focus state appears in dark theme THEN it SHALL be visible.
7. WHEN default browser outline is removed THEN an equivalent custom focus indicator SHALL be provided.
8. WHEN tests or visual review inspect focus states THEN focus SHALL not be invisible.

## Requirement 6: Accessible names for controls

### User story

As a screen-reader user, I want every reader control to have a clear accessible name.

### Acceptance criteria

1. WHEN an icon-only button exists THEN it SHALL have an accessible name.
2. WHEN previous chapter control exists THEN it SHALL be announced as previous chapter or equivalent.
3. WHEN next chapter control exists THEN it SHALL be announced as next chapter or equivalent.
4. WHEN reader settings control exists THEN it SHALL have a clear accessible name.
5. WHEN close buttons exist THEN they SHALL include context such as close settings or close glossary definition.
6. WHEN download/export controls exist THEN they SHALL identify the action and format where possible.
7. WHEN tests query controls by accessible name THEN core controls SHALL be discoverable.

## Requirement 7: Reader settings accessibility

### User story

As a reader, I want reader settings to be accessible so I can adjust the reading experience.

### Acceptance criteria

1. WHEN reader settings are opened THEN focus SHALL move to the settings panel/dialog where appropriate.
2. WHEN reader settings are closed THEN focus SHOULD return to the opener.
3. WHEN reader settings are modal THEN focus SHALL not escape the modal while open.
4. WHEN reader settings are open THEN Escape SHOULD close them.
5. WHEN settings controls exist THEN each SHALL have a visible or accessible label.
6. WHEN font size controls exist THEN they SHALL be keyboard operable.
7. WHEN theme controls exist THEN they SHALL be keyboard operable.
8. WHEN glossary highlight toggle exists THEN it SHALL be keyboard operable and labeled.
9. WHEN tests simulate settings interaction THEN settings SHALL be operable without mouse.

## Requirement 8: Chapter navigation accessibility

### User story

As a reader, I want previous/next chapter navigation to be accessible and understandable.

### Acceptance criteria

1. WHEN previous chapter exists THEN the control SHALL be keyboard reachable.
2. WHEN next chapter exists THEN the control SHALL be keyboard reachable.
3. WHEN previous chapter does not exist THEN the control SHALL be absent or disabled with clear semantics.
4. WHEN next chapter does not exist THEN the control SHALL be absent or disabled with clear semantics.
5. WHEN a chapter selector exists THEN it SHALL have an accessible label.
6. WHEN navigation changes route THEN focus SHOULD move to the new page heading or main content.
7. WHEN tests simulate chapter navigation THEN controls SHALL be reachable and correctly labeled.

## Requirement 9: Glossary annotation accessibility

### User story

As a keyboard and screen-reader user, I want glossary annotations to be usable without relying on hover.

### Acceptance criteria

1. WHEN glossary annotations are interactive THEN they SHALL be keyboard focusable.
2. WHEN a focused annotation is activated THEN its definition SHALL open.
3. WHEN an annotation definition is open THEN Escape SHOULD close it.
4. WHEN definition content is open THEN it SHALL have an accessible label or description.
5. WHEN annotation tooltip/popover closes THEN focus SHOULD return to the annotation.
6. WHEN annotations are disabled THEN reader content SHALL remain accessible.
7. WHEN annotation content is announced THEN it SHALL not include private glossary metadata.
8. WHEN tests simulate keyboard interaction THEN glossary definition SHALL be reachable.

## Requirement 10: Loading, empty, error, and fallback states

### User story

As a reader using assistive technology, I want loading and error states to be clear and announced appropriately.

### Acceptance criteria

1. WHEN chapter content is loading THEN an accessible loading state SHALL be present.
2. WHEN loading completes THEN the final content SHALL be reachable.
3. WHEN a chapter is unavailable THEN a clear accessible message SHALL be shown.
4. WHEN public reader fallback/degraded mode is active THEN a visible and accessible message SHOULD explain it.
5. WHEN an error occurs THEN the error message SHALL be safe and understandable.
6. WHEN an empty chapter list exists THEN the empty state SHALL be descriptive.
7. WHEN tests inspect error and empty states THEN messages SHALL be available as text.

## Requirement 11: Color contrast

### User story

As a low-vision reader, I want text and controls to have sufficient contrast.

### Acceptance criteria

1. WHEN normal reader text is displayed THEN contrast SHOULD meet at least 4.5:1.
2. WHEN large text is displayed THEN contrast SHOULD meet at least 3:1.
3. WHEN links are displayed THEN they SHALL be distinguishable from surrounding text.
4. WHEN color is used to show state THEN another cue SHALL also be available where needed.
5. WHEN focus indicators are displayed THEN they SHOULD have sufficient contrast.
6. WHEN glossary highlights are displayed THEN highlighted text SHALL remain readable.
7. WHEN dark theme is used THEN text and controls SHALL remain readable.
8. WHEN visual review or automated tooling detects low contrast THEN issues SHALL be fixed or documented with rationale.

## Requirement 12: Reduced motion

### User story

As a reader sensitive to motion, I want the reader to respect reduced motion preferences.

### Acceptance criteria

1. WHEN `prefers-reduced-motion: reduce` is active THEN non-essential animations SHALL be reduced or disabled.
2. WHEN smooth scrolling is used THEN it SHALL be disabled or minimized for reduced-motion users.
3. WHEN tooltips/popovers animate THEN animation SHOULD be reduced for reduced-motion users.
4. WHEN page transitions exist THEN they SHOULD respect reduced-motion preferences.
5. WHEN reduced motion is active THEN reader functionality SHALL remain unchanged.
6. WHEN tests or manual checks enable reduced motion THEN animations SHALL not be required to understand content.

## Requirement 13: Zoom and responsive accessibility

### User story

As a low-vision or mobile reader, I want reader content to remain usable with zoom and larger text.

### Acceptance criteria

1. WHEN browser zoom is set to 200% THEN reader content SHOULD remain readable.
2. WHEN reader font size is increased THEN content SHOULD reflow without overlapping controls.
3. WHEN mobile viewport is used THEN controls SHOULD remain reachable and not cover content permanently.
4. WHEN prose content is rendered THEN horizontal scrolling SHOULD be avoided for normal paragraphs.
5. WHEN tap targets are used on mobile THEN they SHOULD be large enough to activate reliably.
6. WHEN tests or manual checks increase font size THEN core reader flow SHALL remain usable.

## Requirement 14: Link and button semantics

### User story

As a user of assistive technology, I want controls to use correct semantics so their behavior is predictable.

### Acceptance criteria

1. WHEN a control navigates to another page THEN it SHOULD be implemented as a link.
2. WHEN a control performs an action on the current page THEN it SHOULD be implemented as a button.
3. WHEN a non-native element is used as a control THEN it SHALL implement keyboard and ARIA semantics correctly.
4. WHEN controls are disabled THEN they SHALL communicate disabled state correctly.
5. WHEN interactive elements are rendered THEN they SHALL not be nested inside other interactive elements.
6. WHEN tests inspect common controls THEN they SHALL have appropriate roles.

## Requirement 15: Public search/filter accessibility

### User story

As a reader, I want public search and filters to be accessible if they are part of the reader discovery flow.

### Acceptance criteria

1. WHEN a search input exists THEN it SHALL have an accessible label.
2. WHEN filter controls exist THEN each SHALL have an accessible label.
3. WHEN sort controls exist THEN they SHALL have an accessible label.
4. WHEN search/filter results update dynamically THEN the update SHOULD be announced or discoverable.
5. WHEN validation errors occur THEN they SHALL be associated with the relevant control.
6. WHEN tests inspect search/filter controls THEN labels SHALL be discoverable.

## Requirement 16: Accessible document title

### User story

As a screen-reader or browser-tab user, I want each public reader route to have a meaningful document title.

### Acceptance criteria

1. WHEN a novel page loads THEN the document title SHALL include the novel title and site name.
2. WHEN a chapter page loads THEN the document title SHALL include chapter title, novel title, and site name.
3. WHEN a fallback/error page loads THEN the document title SHALL describe the state safely.
4. WHEN route changes occur client-side THEN document title SHALL update.
5. WHEN title data is missing THEN a safe fallback title SHALL be used.

## Requirement 17: Test coverage

### User story

As a maintainer, I want accessibility tests so reader accessibility does not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover landmarks/main content.
2. WHEN tests run THEN they SHALL cover heading structure.
3. WHEN tests run THEN they SHALL cover skip link behavior.
4. WHEN tests run THEN they SHALL cover keyboard access to core controls.
5. WHEN tests run THEN they SHALL cover visible or class-applied focus states where practical.
6. WHEN tests run THEN they SHALL cover accessible names for controls.
7. WHEN tests run THEN they SHALL cover reader settings keyboard behavior.
8. WHEN tests run THEN they SHALL cover chapter navigation labels.
9. WHEN tests run THEN they SHALL cover glossary annotation keyboard behavior where implemented.
10. WHEN tests run THEN they SHALL cover loading/error/empty states.
11. WHEN tests run THEN they SHOULD include automated accessibility checks where available.
12. WHEN tests cannot cover visual/manual requirements THEN manual checklist SHALL be documented.

## Requirement 18: Completion verification

### User story

As an operator, I want a clear verification path so public reader accessibility is complete only when the main reading flow is usable without a mouse.

### Acceptance criteria

1. WHEN using keyboard only THEN a user SHALL be able to open a public chapter and navigate reader controls.
2. WHEN using keyboard only THEN a user SHALL be able to open and close reader settings.
3. WHEN using keyboard only THEN a user SHALL be able to use previous/next chapter navigation.
4. WHEN glossary annotations exist THEN a keyboard user SHALL be able to open and close definitions.
5. WHEN a screen-reader smoke test is performed THEN headings, landmarks, and controls SHALL be understandable.
6. WHEN browser zoom is set to 200% THEN reader content SHALL remain usable.
7. WHEN reduced motion is enabled THEN reader content SHALL remain usable without unnecessary motion.
8. WHEN public reader error/fallback states occur THEN they SHALL be understandable and accessible.
