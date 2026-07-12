# design.md

# Design: Public Reader Accessibility Baseline

## Overview

`public-reader-accessibility-baseline` adds baseline accessibility requirements for the public reader experience.

The public reader should be usable with keyboard navigation, screen readers, zoom, mobile assistive technology, reduced motion preferences, and high-contrast needs. This spec focuses on reader structure, navigation, controls, focus management, skip links, semantic landmarks, accessible glossary annotations, and safe fallback states.

This is a public-readiness feature. It should be treated as a quality gate before broader public launch.

## Goals

* Add semantic structure to public reader pages.
* Support keyboard navigation for reader controls.
* Add visible focus states.
* Add skip links and landmark regions.
* Improve screen-reader labels and announcements.
* Ensure reader typography controls are accessible.
* Ensure chapter navigation is accessible.
* Ensure glossary annotation interactions are accessible.
* Respect reduced motion preferences.
* Preserve color contrast across themes.
* Add accessible loading, empty, error, unavailable, and fallback states.
* Add tests for keyboard navigation, labels, semantics, and contrast where practical.

## Non-goals

* No full design-system rewrite.
* No complete WCAG audit certification.
* No browser extension support.
* No text-to-speech feature.
* No custom screen reader.
* No public reader layout redesign beyond accessibility fixes.
* No backend API changes unless required for accessible labels.
* No accessibility analytics tracking.

## Target areas

Public reader surfaces:

```text
/novels
/novels/{novel_slug}
/novels/{novel_slug}/chapters/{chapter_slug}
public reader fallback/unavailable pages
public search/list filters if part of reader flow
reader settings panel
glossary annotation highlights/tooltips
chapter navigation controls
export/download controls if visible publicly
```

## Accessibility principles

The public reader should follow these rules:

```text
use semantic HTML first
make all interactive controls keyboard reachable
provide visible focus states
avoid keyboard traps
preserve reading order
avoid content disappearing on focus/hover
provide accessible names for icon-only controls
do not rely on color alone
respect reduced motion
keep text readable at zoom
announce important state changes
```

## Semantic page structure

Recommended layout:

```html
<a href="#main-content" class="skip-link">Skip to main content</a>

<header>...</header>

<nav aria-label="Chapter navigation">...</nav>

<main id="main-content">
  <article aria-labelledby="chapter-title">
    <h1 id="chapter-title">Chapter Title</h1>
    <p>Chapter content...</p>
  </article>
</main>

<aside aria-label="Reader settings">...</aside>

<footer>...</footer>
```

Required landmarks:

```text
header/banner
main
article for chapter content
nav for chapter controls
footer where present
```

## Heading structure

Recommended:

```text
h1: novel title on novel page
h1: chapter title on chapter page
h2: sections such as chapter list, synopsis, reader settings
h3+: nested sections only
```

Rules:

```text
do not skip heading levels for visual styling
do not use headings solely for decorative text
ensure each page has one clear h1
```

## Keyboard navigation

Required keyboard support:

```text
Tab reaches all interactive controls
Shift+Tab reverses order
Enter/Space activates buttons
Escape closes modals/popovers/settings panels
Arrow keys may be used only when expected by component pattern
focus is restored after modal/popover closes
no keyboard traps
```

Reader controls that must be keyboard accessible:

```text
previous chapter
next chapter
chapter selector
reader settings
font size controls
theme controls
glossary annotation highlights
download/export buttons
search/filter controls
close buttons
```

## Focus management

Visible focus styles must exist for:

```text
links
buttons
inputs
selects
reader settings controls
chapter navigation controls
glossary annotation highlights
popover close buttons
```

Rules:

```text
focus indicator must be visible in light and dark themes
do not remove outline unless replaced with equivalent
focus should move into modal/dialog when opened
focus should return to triggering control when closed
route changes should move focus to main heading or main content
```

## Skip links

Add skip links for public reader pages.

Recommended:

```text
Skip to main content
Skip to chapter navigation
Skip to reader settings
```

Minimum V1:

```text
Skip to main content
```

Skip links should appear when focused and work with keyboard.

## Screen-reader labels

All icon-only controls need accessible names.

Examples:

```html
<button aria-label="Open reader settings">...</button>
<button aria-label="Previous chapter">...</button>
<button aria-label="Next chapter">...</button>
<button aria-label="Close glossary definition">...</button>
```

Avoid vague labels:

```text
Click here
Button
Open
Icon
```

## Reader settings accessibility

Reader settings should be accessible as either:

```text
dialog
popover
collapsible panel
normal page section
```

If implemented as a dialog:

```text
use role="dialog" or native dialog
use aria-modal="true" if modal
label with heading
trap focus while open
Escape closes
return focus to opener
```

Settings controls should have labels:

```text
Font size
Line spacing
Theme
Glossary highlights
Reduced motion if custom app setting exists
```

## Glossary annotation accessibility

Glossary highlights must be usable without mouse.

Required behavior:

```text
highlight can receive keyboard focus
focus or Enter/Space opens definition
Escape closes definition
definition has accessible label
definition content is associated with highlighted term
highlight text remains selectable/readable where practical
```

Recommended ARIA:

```text
aria-describedby for tooltip-style definitions
aria-expanded for popover-style definitions
aria-controls when a popover element exists
```

Do not expose private glossary fields to assistive technology.

## Loading, empty, error, unavailable states

States must be announced and understandable.

Recommended patterns:

```text
loading content -> aria-busy or status text
error state -> role="alert" only for immediate important errors
unavailable chapter -> clear heading and message
fallback/degraded reader -> visible message and accessible text
empty chapter list -> descriptive empty state
```

Avoid endless skeleton screens without text.

## Color contrast

Reader UI must meet baseline contrast.

Targets:

```text
normal text: at least 4.5:1
large text: at least 3:1
interactive component boundaries/focus indicators: at least 3:1 where practical
```

Apply to:

```text
reader text
chapter navigation
settings controls
glossary highlights
badges
error messages
links
focus rings
```

Use existing design tokens where possible.

## Reduced motion

Respect user preference:

```css
@media (prefers-reduced-motion: reduce) {
  * {
    scroll-behavior: auto;
  }
}
```

Behavior:

```text
disable non-essential animations
avoid animated page transitions
avoid smooth scrolling if user prefers reduced motion
keep tooltip/popover transitions minimal or disabled
```

## Zoom and responsive layout

Reader should remain usable at:

```text
200% browser zoom
mobile viewport widths
large font sizes
custom reader font sizes
```

Rules:

```text
content should reflow
controls should not overlap chapter text
horizontal scrolling should be avoided for normal prose
tap targets should remain usable
```

## Link and button semantics

Rules:

```text
use links for navigation
use buttons for actions
do not use div/span as buttons unless fully accessible
do not nest interactive elements
do not rely only on onclick handlers
```

Examples:

```text
Next chapter -> link if it navigates
Open settings -> button
Download export -> link or button depending on implementation
```

## Forms and filters

For public search/filter controls:

```text
inputs have labels
selects have labels
errors are associated with controls
filter changes are announced if results update dynamically
submit buttons have clear names
```

## Accessible document title

The document title should update per route.

Examples:

```text
Novel Title | Site Name
Chapter Title - Novel Title | Site Name
Search | Site Name
```

This overlaps with SEO, but accessibility requires meaningful browser titles too.

## Testing strategy

Use automated and manual tests.

Automated tests:

```text
component tests for labels
keyboard navigation tests
role/landmark queries
focus restoration tests
axe/accessibility tests where available
reader settings dialog tests
glossary tooltip keyboard tests
```

Manual checks:

```text
keyboard-only reader flow
screen reader smoke test
200% zoom test
dark/light contrast spot check
mobile touch target check
reduced motion check
```

## Rollout plan

1. Audit public reader DOM structure.
2. Add semantic landmarks and headings.
3. Add skip links.
4. Add accessible labels for controls.
5. Fix keyboard navigation.
6. Add focus management.
7. Fix reader settings accessibility.
8. Fix glossary annotation accessibility.
9. Add accessible loading/error/fallback states.
10. Add contrast/reduced-motion improvements.
11. Add tests.
12. Verify with keyboard-only and screen-reader smoke checks.
