# Interaction Patterns

Shared behavior contracts for interactive components.

## Control States

Interactive controls must support all applicable states. States are not mutually exclusive — a control can be focused and disabled, or selected and pressed.

### State Matrix

| State | Visual Treatment | Cursor | ARIA | Focus |
|---|---|---|---|---|
| Default | Base appearance | `pointer` | — | — |
| Hover | 120ms color/background shift via `transition-colors` | `pointer` | — | — |
| Pressed / Active | `active:` state, subtle scale or color shift | `pointer` | — | — |
| Selected / Active | Clear visual marker (accent border, fill, or checkmark) | `pointer` | `aria-selected="true"` or `aria-checked="true"` | — |
| Disabled | `opacity-50`, `pointer-events: none` | `default` | `disabled` attribute | Removed from tab order |
| `aria-disabled` | `opacity-50`, cursor `not-allowed`, remains in tab order | `not-allowed` | `aria-disabled="true"` | Keeps tab order, MUST announce disabled |
| Read-only | Normal appearance, no edit affordance | `default` | `readonly` or `aria-readonly="true"` | Keeps tab order |
| Pending / Loading | Spinner or skeleton replaces or overlays control, `aria-busy="true"` | `wait` or `default` | `aria-busy="true"` | Control MUST preserve width to prevent layout shift |
| Focus-visible | `--ring` or `--focus-ring` token; primary buttons use two-layer | — | — | `:focus-visible` only; no permanent ring on click |

## Keyboard Interaction

- `Tab` / `Shift+Tab`: Navigate between focusable elements
- `Enter` / `Space`: Activate buttons, links, toggles
- `Arrow keys`: Navigate within composite widgets (tabs, menus, lists, grids)
- `Escape`: Close dialogs, dropdowns, dismiss toasts, cancel destructive actions
- `Home` / `End`: Jump to first/last item in composite widgets

## Pointer vs Touch Behavior

- Hover states apply only on `@media (hover: hover)` — touch devices MUST NOT show stuck hover
- Touch targets MUST meet 44×44px minimum (WCAG 2.2 Target Size)
- Long-press is not used for any action

## Async Width Preservation

- Buttons with pending state MUST NOT change width during loading (use `min-w-[original]` or fixed width)
- "Load more" and submit buttons MUST disable during request and restore on completion

## Destructive Confirmation

- Destructive actions (delete, remove, reject) MUST require explicit confirmation via modal dialog
- Confirmation dialog MUST state what will be destroyed and use `--destructive` button variant
- Escape and backdrop click cancel the destructive action

## Editable-Control Shortcut Suppression

- Global keyboard shortcuts (`/` for search, `.` for reader panel) MUST NOT fire when focus is inside `input`, `textarea`, `select`, or `[contenteditable]`
