# Accessibility Standards

Non-negotiable accessibility requirements.

## WCAG 2.2 AA Target

Target is WCAG 2.2 Level AA. This includes all WCAG 2.1 AA criteria plus:
- **2.5.7 Dragging Movements**: Not applicable (no drag interactions implemented)
- **2.5.8 Target Size (Minimum)**: Interactive targets MUST be at least 24×24px; SHOULD be 44×44px on touch surfaces
- **3.3.7 Redundant Entry**: Forms MUST NOT require re-entry of information already provided in the same session
- **3.3.8 Accessible Authentication**: Login MUST support paste and password managers; MUST NOT require cognitive function tests

## Non-Text Contrast

- Interactive component boundaries (input borders, button edges) MUST maintain 3:1 contrast against adjacent colors
- Focus indicators MUST maintain 3:1 contrast against the focused component and its background
- Icons that convey meaning MUST maintain 3:1 contrast

## Pointer Target Sizing

- All interactive targets: minimum 24×24px (WCAG 2.2)
- Mobile touch targets: SHOULD be 44×44px
- Inline text links are exempt from target size requirements
- Targets MUST NOT overlap — adjacent targets require spacing

## Focus Not Obscured

- When an element receives focus, it MUST NOT be fully obscured by sticky headers, fixed bottom bars, or other author-created content
- Sticky public header (z-30) and mobile tab bar (z-40) MUST NOT cover focused content — scroll-padding or scroll-margin MUST be applied

## Forced Colors and High Contrast

- All borders, focus rings, and text MUST remain visible in Windows High Contrast mode
- `forced-colors: active` media query SHOULD be tested for:
  - Button borders visible
  - Focus rings visible
  - Status badges distinguishable by border or text, not fill alone
  - Form input boundaries visible
- **Manual acceptance required** — no automated CI coverage exists

## Autofill and Browser Validation

- Inputs MUST accept browser autofill without breaking layout or validation
- Custom validation messages MUST NOT conflict with native browser validation
- `autocomplete` attributes MUST be set on login/registration forms

## Field Error Association

- Error messages MUST be associated with their input via `aria-describedby`
- Error state MUST set `aria-invalid="true"` on the input
- Error text MUST use `--destructive-text` token

## Live Region Behavior

| Severity | `aria-live` | `role` | Use |
|---|---|---|---|
| Informational | `polite` | `status` | Loading states, empty states, success toasts |
| Important | `polite` | `status` | Form validation results, search result counts |
| Critical | `assertive` | `alert` | Error states, destructive confirmations, session expiry |

## Toast Requirements

- Toasts MUST auto-dismiss after 4 seconds minimum
- Toasts with actions MUST remain visible until dismissed or action taken
- Toast container uses `aria-live="polite"` and `role="status"`
- Toasts MUST NOT be the sole feedback for destructive or error actions

## Screen Reader and Browser Acceptance Matrix

| Combination | Status |
|---|---|
| NVDA + Chrome (Windows) | Manual acceptance required |
| VoiceOver + Safari (macOS) | Manual acceptance required |
| VoiceOver + Safari (iOS) | Manual acceptance required |
| TalkBack + Chrome (Android) | Manual acceptance required |

Manual acceptance tracked in `docs/WORK.md` as DEBT-FE-01A.

## Automated vs Manual Verification

| Check | Automated | Manual |
|---|---|---|
| Color contrast (token pairs) | ✓ `app/(public)/__tests__/token-contrast.test.ts` | — |
| Focus ring presence | ✓ CSS inspection | — |
| Reduced motion | ✓ CSS media query | ✓ Browser behavior |
| Keyboard navigation | — | ✓ DEBT-FE-01A |
| Screen reader labels | — | ✓ DEBT-FE-01A |
| 200% zoom reflow | — | ✓ DEBT-FE-01A |
| 320px width reflow | — | ✓ DEBT-FE-01A |
| Forced colors mode | — | ✓ DEBT-FE-01A |
| Touch target sizing | — | ✓ DEBT-FE-01A |
