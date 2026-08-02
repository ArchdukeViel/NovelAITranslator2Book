# Accessibility Requirements

Accessibility standards for public and admin surfaces.

## Standards Compliance

Target: WCAG 2.1 Level AA compliance across all routes.

## Core Rules

1. **Native elements first:** Use native HTML buttons, links, inputs before ARIA roles.
2. **Landmarks:** Every page defines exactly one `<main id="main-content">`, accompanied by skip link.
3. **Keyboard operation:** All interactive elements reachable and operable via keyboard without focus traps.
4. **Focus visible:** Focus indicators meet contrast requirements. Primary buttons use two-layer focus rings.
5. **Zoom and Reflow:** Fully functional at 200% zoom and 320px viewport width without horizontal content loss.
6. **Reduced motion:** `prefers-reduced-motion: reduce` disables smooth scrolling and animations.
7. **Screen readers:** Informative image `alt` attributes; decorative assets use `alt=""` and `aria-hidden="true"`. Dynamic updates announce via live regions (`aria-live="polite"`).
8. **Contrast:** Text and interactive icons maintain minimum 4.5:1 contrast against backgrounds in light and dark modes. Context tokens (`--{status}-text`) ensure AA compliance for chips and callouts.
9. **Color independence:** Color is never the sole indicator of state; paired with text labels, icons, or patterns.
