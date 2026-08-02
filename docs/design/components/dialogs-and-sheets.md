# Component Contract — Dialogs & Sheets

## Specifications

- **Modal Dialogs:** Centered on desktop, 16px top border-radius, backdrop overlay (`bg-background/80 backdrop-blur-sm`). Contains single top-right X close button. Traps keyboard focus.
- **Bottom Sheets:** Mobile filter sheet and mobile search surface. Pinned to viewport bottom with persistent action buttons. Temporarily hides bottom tab bar while open.
- **Search Overlay:** Centered palette overlay on desktop, full-screen on mobile. Keyboard `ArrowUp`/`ArrowDown`/`Enter`/`Escape` supported.
