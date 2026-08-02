# Interaction Rules

Standard interactive behaviors across public and admin interfaces.

## Control States

Every interactive element defines:
- **Default:** base visual appearance.
- **Hover (pointer only):** 120ms smooth transition.
- **Pressed:** active click/tap visual scale or color shift.
- **Selected / Active:** clear visual selection marker.
- **Disabled:** 50% opacity, `pointer-events: none`, retains element visibility.
- **Pending:** async operation in flight (spinner or skeleton, never frozen button).
- **Focus-visible:** uses `--focus-ring` token. Primary buttons use a two-layer treatment (neutral inner ring + `--focus-ring` outer offset).

## Forms and Input

- Labels bound via `htmlFor` or direct nesting.
- Explicit inline validation error messages.
- Form data survives authentication detours (draft restoration).
- Unsaved changes trigger confirmation before navigation on complex forms.

## Dialogs and Sheets

- One close affordance per modal (top-right X icon).
- Escape key closes open dialog/sheet/overlay.
- Dialog traps focus and restores focus to trigger on close.
- Mobile bottom sheets suppress persistent bottom tab bars.

## Keyboard Interaction

- Full keyboard navigation across all surfaces.
- standard shortcuts: `/` opens search overlay, `Escape` closes overlays, `←`/`→` for chapter navigation, `.` opens chapter reader Aa panel.
