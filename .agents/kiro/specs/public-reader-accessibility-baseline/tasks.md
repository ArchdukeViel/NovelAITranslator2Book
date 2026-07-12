# tasks.md

# Tasks: Public Reader Accessibility Baseline

## Task List

* [ ] 0. Preflight accessibility audit

  * [ ] 0.1 Inspect public novel list page structure.
  * [ ] 0.2 Inspect public novel detail page structure.
  * [ ] 0.3 Inspect public chapter reader page structure.
  * [ ] 0.4 Inspect reader settings panel/dialog.
  * [ ] 0.5 Inspect chapter navigation controls.
  * [ ] 0.6 Inspect glossary annotation highlight/tooltip components if implemented.
  * [ ] 0.7 Inspect public search/filter controls.
  * [ ] 0.8 Inspect loading, empty, error, unavailable, and degraded states.
  * [ ] 0.9 Inspect theme/focus styles.
  * [ ] 0.10 Inspect existing frontend accessibility test tooling.

* [ ] 1. Add semantic landmarks

  * [ ] 1.1 Add main landmark to public reader pages. (REQ-1)
  * [ ] 1.2 Wrap chapter content in article or equivalent semantic region. (REQ-1)
  * [ ] 1.3 Add navigation landmark/label for chapter controls. (REQ-1)
  * [ ] 1.4 Add header/footer landmarks where applicable. (REQ-1)
  * [ ] 1.5 Avoid confusing duplicate landmarks. (REQ-1)
  * [ ] 1.6 Add tests for landmark discovery. (REQ-1, REQ-17)

* [ ] 2. Fix heading structure

  * [ ] 2.1 Ensure novel page has one clear h1. (REQ-2)
  * [ ] 2.2 Ensure chapter page has one clear h1. (REQ-2)
  * [ ] 2.3 Use logical h2/h3 levels for subsections. (REQ-2)
  * [ ] 2.4 Replace decorative heading misuse with styled text. (REQ-2)
  * [ ] 2.5 Add safe fallback headings. (REQ-2)
  * [ ] 2.6 Add tests for heading presence and order where practical. (REQ-2, REQ-17)

* [ ] 3. Add skip links

  * [ ] 3.1 Add skip link to main content. (REQ-3)
  * [ ] 3.2 Make skip link visible on focus. (REQ-3)
  * [ ] 3.3 Ensure skip link moves focus to main content or heading. (REQ-3)
  * [ ] 3.4 Add optional skip link to chapter navigation if useful. (REQ-3)
  * [ ] 3.5 Add keyboard tests for skip link behavior. (REQ-3, REQ-17)

* [ ] 4. Improve keyboard navigation

  * [ ] 4.1 Verify all reader controls are reachable by Tab. (REQ-4)
  * [ ] 4.2 Verify Shift+Tab order is logical. (REQ-4)
  * [ ] 4.3 Ensure buttons activate with Enter/Space. (REQ-4)
  * [ ] 4.4 Ensure navigation links activate with Enter. (REQ-4)
  * [ ] 4.5 Ensure Escape closes popovers/dialogs where appropriate. (REQ-4)
  * [ ] 4.6 Remove keyboard traps. (REQ-4)
  * [ ] 4.7 Add keyboard navigation tests for core reader flow. (REQ-4, REQ-17)

* [ ] 5. Add visible focus states

  * [ ] 5.1 Audit existing focus styles. (REQ-5)
  * [ ] 5.2 Add focus styles for links. (REQ-5)
  * [ ] 5.3 Add focus styles for buttons. (REQ-5)
  * [ ] 5.4 Add focus styles for inputs/selects. (REQ-5)
  * [ ] 5.5 Add focus styles for glossary highlights. (REQ-5, REQ-9)
  * [ ] 5.6 Verify focus styles in light theme. (REQ-5)
  * [ ] 5.7 Verify focus styles in dark theme. (REQ-5)
  * [ ] 5.8 Add tests or visual checklist for focus visibility. (REQ-5, REQ-17)

* [ ] 6. Add accessible names for controls

  * [ ] 6.1 Add labels to icon-only buttons. (REQ-6)
  * [ ] 6.2 Label previous chapter control. (REQ-6, REQ-8)
  * [ ] 6.3 Label next chapter control. (REQ-6, REQ-8)
  * [ ] 6.4 Label reader settings opener. (REQ-6, REQ-7)
  * [ ] 6.5 Label close buttons with context. (REQ-6)
  * [ ] 6.6 Label download/export controls with format where available. (REQ-6)
  * [ ] 6.7 Add tests querying controls by accessible name. (REQ-6, REQ-17)

* [ ] 7. Fix reader settings accessibility

  * [ ] 7.1 Decide whether settings is dialog, popover, or inline panel. (REQ-7)
  * [ ] 7.2 Move focus into settings when opened where appropriate. (REQ-7)
  * [ ] 7.3 Restore focus to opener when closed. (REQ-7)
  * [ ] 7.4 Trap focus if settings is modal. (REQ-7)
  * [ ] 7.5 Add Escape close behavior. (REQ-7)
  * [ ] 7.6 Add labels for font size controls. (REQ-7)
  * [ ] 7.7 Add labels for theme controls. (REQ-7)
  * [ ] 7.8 Add labels for glossary highlight toggle. (REQ-7)
  * [ ] 7.9 Add tests for keyboard operation and focus restoration. (REQ-7, REQ-17)

* [ ] 8. Fix chapter navigation accessibility

  * [ ] 8.1 Ensure previous chapter is a link if it navigates. (REQ-8, REQ-14)
  * [ ] 8.2 Ensure next chapter is a link if it navigates. (REQ-8, REQ-14)
  * [ ] 8.3 Handle missing previous chapter accessibly. (REQ-8)
  * [ ] 8.4 Handle missing next chapter accessibly. (REQ-8)
  * [ ] 8.5 Label chapter selector. (REQ-8)
  * [ ] 8.6 Move focus to heading/main content after route change where practical. (REQ-8)
  * [ ] 8.7 Add tests for navigation labels and disabled/absent states. (REQ-8, REQ-17)

* [ ] 9. Fix glossary annotation accessibility

  * [ ] 9.1 Ensure annotation highlights can receive focus. (REQ-9)
  * [ ] 9.2 Open definition on focus/activation. (REQ-9)
  * [ ] 9.3 Close definition with Escape. (REQ-9)
  * [ ] 9.4 Associate definition content with highlighted term. (REQ-9)
  * [ ] 9.5 Restore focus after close where practical. (REQ-9)
  * [ ] 9.6 Ensure private glossary metadata is not exposed. (REQ-9)
  * [ ] 9.7 Add tests for keyboard opening, closing, labels, and privacy. (REQ-9, REQ-17)

* [ ] 10. Improve loading, empty, error, and fallback states

  * [ ] 10.1 Add accessible loading text/status. (REQ-10)
  * [ ] 10.2 Ensure loaded content becomes reachable. (REQ-10)
  * [ ] 10.3 Add clear unavailable chapter message. (REQ-10)
  * [ ] 10.4 Add accessible degraded/fallback message. (REQ-10)
  * [ ] 10.5 Add safe accessible error messages. (REQ-10)
  * [ ] 10.6 Add descriptive empty chapter list state. (REQ-10)
  * [ ] 10.7 Add tests for state messages. (REQ-10, REQ-17)

* [ ] 11. Improve color contrast

  * [ ] 11.1 Audit reader text contrast in light theme. (REQ-11)
  * [ ] 11.2 Audit reader text contrast in dark theme. (REQ-11)
  * [ ] 11.3 Audit link contrast and non-color cue. (REQ-11)
  * [ ] 11.4 Audit focus indicator contrast. (REQ-11)
  * [ ] 11.5 Audit glossary highlight contrast. (REQ-11)
  * [ ] 11.6 Update design tokens/styles where needed. (REQ-11)
  * [ ] 11.7 Document manual contrast verification. (REQ-11, REQ-17)

* [ ] 12. Add reduced-motion support

  * [ ] 12.1 Add reduced-motion CSS overrides. (REQ-12)
  * [ ] 12.2 Disable/minimize smooth scrolling for reduced motion. (REQ-12)
  * [ ] 12.3 Reduce tooltip/popover transitions. (REQ-12)
  * [ ] 12.4 Reduce page transitions if present. (REQ-12)
  * [ ] 12.5 Verify reader behavior remains functional. (REQ-12)
  * [ ] 12.6 Add tests or manual checklist for reduced motion. (REQ-12, REQ-17)

* [ ] 13. Verify zoom and responsive accessibility

  * [ ] 13.1 Test reader at 200% browser zoom. (REQ-13)
  * [ ] 13.2 Test increased reader font size. (REQ-13)
  * [ ] 13.3 Fix overlapping controls. (REQ-13)
  * [ ] 13.4 Avoid horizontal scrolling for normal prose. (REQ-13)
  * [ ] 13.5 Verify mobile tap targets. (REQ-13)
  * [ ] 13.6 Document manual zoom/mobile checks. (REQ-13, REQ-17)

* [ ] 14. Fix link/button semantics

  * [ ] 14.1 Replace navigation buttons with links where appropriate. (REQ-14)
  * [ ] 14.2 Replace action links with buttons where appropriate. (REQ-14)
  * [ ] 14.3 Fix non-native clickable elements. (REQ-14)
  * [ ] 14.4 Add disabled semantics for unavailable controls. (REQ-14)
  * [ ] 14.5 Remove nested interactive elements. (REQ-14)
  * [ ] 14.6 Add role/semantics tests for common controls. (REQ-14, REQ-17)

* [ ] 15. Fix public search/filter accessibility

  * [ ] 15.1 Label search input. (REQ-15)
  * [ ] 15.2 Label filter controls. (REQ-15)
  * [ ] 15.3 Label sort controls. (REQ-15)
  * [ ] 15.4 Announce dynamic result updates where practical. (REQ-15)
  * [ ] 15.5 Associate validation errors with controls. (REQ-15)
  * [ ] 15.6 Add tests for labels and error association. (REQ-15, REQ-17)

* [ ] 16. Add accessible document titles

  * [ ] 16.1 Set novel page document title. (REQ-16)
  * [ ] 16.2 Set chapter page document title. (REQ-16)
  * [ ] 16.3 Set fallback/error page document titles. (REQ-16)
  * [ ] 16.4 Update title on client-side route changes. (REQ-16)
  * [ ] 16.5 Add safe fallback title. (REQ-16)
  * [ ] 16.6 Add tests for title updates. (REQ-16, REQ-17)

* [ ] 17. Add automated accessibility tests

  * [ ] 17.1 Add tests for landmarks. (REQ-17)
  * [ ] 17.2 Add tests for headings. (REQ-17)
  * [ ] 17.3 Add tests for skip link. (REQ-17)
  * [ ] 17.4 Add tests for keyboard access to controls. (REQ-17)
  * [ ] 17.5 Add tests for accessible names. (REQ-17)
  * [ ] 17.6 Add tests for reader settings behavior. (REQ-17)
  * [ ] 17.7 Add tests for glossary keyboard behavior if implemented. (REQ-17)
  * [ ] 17.8 Add tests for loading/error/empty states. (REQ-17)
  * [ ] 17.9 Add axe or equivalent automated checks if available. (REQ-17)

* [ ] 18. Add manual accessibility checklist

  * [ ] 18.1 Document keyboard-only reader flow. (REQ-17, REQ-18)
  * [ ] 18.2 Document screen-reader smoke test steps. (REQ-17, REQ-18)
  * [ ] 18.3 Document 200% zoom check. (REQ-13, REQ-18)
  * [ ] 18.4 Document reduced-motion check. (REQ-12, REQ-18)
  * [ ] 18.5 Document contrast spot-check steps. (REQ-11, REQ-18)
  * [ ] 18.6 Document mobile tap target check. (REQ-13, REQ-18)

* [ ] 19. Completion verification

  * [ ] 19.1 Open a public chapter using keyboard only. (REQ-18)
  * [ ] 19.2 Verify skip link moves to main content. (REQ-3, REQ-18)
  * [ ] 19.3 Verify previous/next chapter navigation works without mouse. (REQ-8, REQ-18)
  * [ ] 19.4 Verify reader settings opens, operates, and closes without mouse. (REQ-7, REQ-18)
  * [ ] 19.5 Verify glossary definitions open and close without mouse if annotations exist. (REQ-9, REQ-18)
  * [ ] 19.6 Run screen-reader smoke test for headings, landmarks, and controls. (REQ-1, REQ-2, REQ-6, REQ-18)
  * [ ] 19.7 Test reader at 200% zoom. (REQ-13, REQ-18)
  * [ ] 19.8 Test reader with reduced motion enabled. (REQ-12, REQ-18)
  * [ ] 19.9 Verify loading/error/fallback states are accessible. (REQ-10, REQ-18)
  * [ ] 19.10 Mark `public-reader-accessibility-baseline` complete only after the public reading flow is usable without a mouse and basic screen-reader structure is understandable.
