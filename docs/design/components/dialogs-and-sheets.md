# Component Contract — Dialogs & Sheets

Modal overlays, bottom sheets, and palette overlays.

## Modal Dialogs

- Position: centered on viewport (desktop)
- Border radius: `rounded-lg` (6px) top corners; full `rounded-lg` on desktop
- Backdrop: `bg-background/80 backdrop-blur-sm` (public) or `bg-black/70 backdrop-blur-sm` (admin)
- Z-index: 50 (public) or 50-60 (admin)
- Shadow: `shadow-2xl`

### Accessible Naming

- MUST have `aria-label` or `aria-labelledby` pointing to dialog title
- MUST include visible title (`<h2>` or equivalent)

### Focus Management

- Initial focus: first focusable element inside dialog, or close button
- Focus trap: Tab cycles within dialog; focus MUST NOT escape to background
- Focus restoration: on close, focus returns to the element that opened the dialog
- `Escape` key closes dialog

### Inert Background

- Background content MUST be `inert` or `aria-hidden="true"` while dialog is open
- Background MUST NOT be scrollable while dialog is open

### Close Behavior

- Single close affordance: top-right X icon button
- `Escape` key closes
- Backdrop click closes (non-destructive dialogs)
- Destructive confirmation dialogs SHOULD NOT close on backdrop click

### Scroll Locking

- Body scroll MUST be locked while modal is open
- Dialog content scrolls internally if it exceeds viewport height

## Bottom Sheets (Mobile)

- Position: fixed to viewport bottom
- Border radius: `rounded-t-xl` (12px top corners)
- Background: `bg-card`
- Shadow: `shadow-xl ring-1 ring-border`
- Max height: `max-h-[85vh]`
- Internal scroll for content exceeding visible area
- Pinned action buttons at bottom (Apply / Clear for filters)
- Temporarily hides bottom tab bar while open

### Safe Area

- Bottom padding includes `env(safe-area-inset-bottom)` for gesture bars

## Search Overlay

- Desktop: centered palette overlay, `max-w-lg`, `rounded-xl` on desktop
- Mobile: full-screen overlay
- Z-index: 50
- Keyboard: `ArrowUp`/`ArrowDown` cycle results, `Enter` selects, `Escape` closes
- Focus: search input receives focus on open; focus returns to trigger on close

## Destructive Confirmation

- Confirmation dialog for delete/remove/reject actions
- MUST state what will be destroyed
- Confirm button: `--destructive` variant with active verb ("Remove", "Delete", "Reject")
- Cancel button: "Cancel" — always present
- `Escape` and backdrop click cancel (do NOT confirm)

## Nested Overlay Policy

- **MUST NOT** nest modals — only one modal or sheet open at a time
- Confirm dialogs within sheets are allowed as a single exception (e.g., confirm delete within a list sheet)
- Toasts MAY appear above modals (z-60 > z-50)

## Animation

- Enter: fade-in + scale (desktop dialog), slide-up (mobile sheet)
- Exit: reverse of enter
- Duration: 200ms
- Reduced motion: instant show/hide, no animation
