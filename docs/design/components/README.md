# Shared Component Design Contracts

UI primitive and shared component design contracts.

## Components Index

| Component | Document | Implementation | Status |
|---|---|---|---|
| Buttons | [`buttons.md`](buttons.md) | `frontend/components/ui/button.tsx` | Documented |
| Cards | [`cards.md`](cards.md) | `frontend/components/public/novel-card.tsx`, `frontend/components/ui/panel.tsx` | Documented |
| Forms | [`forms.md`](forms.md) | `frontend/components/ui/input.tsx`, `textarea.tsx` | Documented |
| Navigation | [`navigation.md`](navigation.md) | `public-header.tsx`, `mobile-tab-bar.tsx` | Documented |
| Dialogs & Sheets | [`dialogs-and-sheets.md`](dialogs-and-sheets.md) | `dialog-shell.tsx`, inline dialogs | Documented |
| Feedback | [`feedback.md`](feedback.md) | `frontend/components/ui/badge.tsx`, `page-state.tsx` | Documented |

## Scope

These contracts cover **shared** primitives used across both public and admin surfaces. Route-specific component behavior is documented in the relevant page contract under `docs/design/public/` or `docs/design/admin/`.

## Authority

Component contracts are subordinate to:
1. `docs/design/public/design-system.md` (token values)
2. `docs/design/shared/interaction.md` (state behavior)
3. `docs/design/shared/accessibility.md` (WCAG requirements)
