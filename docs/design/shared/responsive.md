# Responsive Design System

Layout adaptivity rules across viewports.

## Viewport Breakpoints

Standard Tailwind breakpoints defining media query boundaries.

| Breakpoint | Tailwind prefix | Width | Target Devices |
|---|---|---|---|
| Mobile | (default) | < 640px | Smartphones |
| Small tablet | `sm:` | ≥ 640px | Large phones, small tablets |
| Tablet | `md:` | ≥ 768px | Tablets, small laptops |
| Desktop | `lg:` | ≥ 1024px | Laptops, desktop monitors |
| Wide | `xl:` | ≥ 1280px | Large monitors |
| Ultra-wide | `2xl:` | ≥ 1536px | Ultra-wide monitors |

## Shell Adaptation Breakpoints

The public shell adapts at `md:` (768px), not at the desktop viewport breakpoint. This is intentional — navigation mode switches at tablet width for usability.

| Width | Shell Behavior |
|---|---|
| < 768px | Compact header (brand + notification bell) + fixed bottom tab bar (5 icons) |
| ≥ 768px | Full header with inline links, search trigger, theme toggle, notification bell, account menu |

Shell adaptation is **independent** of viewport breakpoint naming. A 768px device gets desktop-style navigation even though the viewport breakpoint taxonomy calls it "tablet."

## Layout Rules

- Mobile-first CSS utility approach
- Safe areas: Fixed elements MUST pad for `env(safe-area-inset-bottom)` and `env(safe-area-inset-top)` where applicable
- Fixed control collision: At most one fixed-bottom control bar active on screen at a time
- Data tables: Scroll horizontally on small viewports only when card/list transformation loses comparison value

## Page Gutters

| Viewport | Horizontal Padding |
|---|---|
| < 768px | `px-4` (16px) |
| ≥ 768px | `px-6` (24px) |

## Max Widths

| Content Type | Max Width | Utility |
|---|---|---|
| Reading column (default) | 680px | `max-w-[680px]` |
| Reading column (narrow) | 560px | `max-w-[560px]` |
| Reading column (wide) | 800px | `max-w-[800px]` |
| Browse grid | Full width minus gutters | — |
| Content pages | `max-w-4xl` (896px) | `max-w-4xl` |
| Admin content | Full width minus sidebar | — |

## Safe Areas

| Edge | Treatment |
|---|---|
| Bottom (iOS gesture bar) | `env(safe-area-inset-bottom)` on fixed bottom bars |
| Top (notch/dynamic island) | Handled by browser viewport; no explicit inset needed for scrolling content |
| Left/Right (rounded corners) | Standard gutters sufficient |

## Landscape Phone

- No special landscape rules — standard responsive flow applies
- Fixed bottom bars remain fixed; content scrolls normally
- Reader column respects max-width constraints

## Large Screen Behavior

- Content MUST NOT stretch beyond max-width constraints
- Browse grid fills available space with responsive columns
- Admin sidebar is fixed; content area is fluid
- Novel detail uses sticky left panel on desktop (lg:)

## Pointer and Hover Capability

- Hover effects apply only under `@media (hover: hover)`
- Touch targets follow sizing rules in `docs/design/shared/accessibility.md`
- No drag-and-drop interactions exist

## Fixed-Control Collision Policy

- At most **one** fixed bottom bar visible at a time
- Reader chrome suppresses header and tab bar entirely
- Novel detail bottom CTA suppresses mobile tab bar on that route
- Browse filter sheet suppresses tab bar while open
- `env(safe-area-inset-bottom)` MUST be applied to whichever fixed bar is active

## Data Table Adaptation

- Admin tables: horizontal scroll with sticky first column where practical
- Public surfaces: card/list layout preferred over tables
- Compact density (`gap-2`, `p-2`) for admin; comfortable density (`gap-4`, `p-4`) for public
