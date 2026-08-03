# Component Contract — Navigation Components

## Specifications

- **Desktop Header:** Fixed height 64px, inline navigation links, search trigger input button, theme toggle icon, notification bell, user avatar menu.
- **Mobile Bottom Tab Bar:** Fixed height 56px + `env(safe-area-inset-bottom)`. 5 thumb-reachable icons (Home, Browse, Search, Library, Account).
- **Pagination:** Numeric pagination buttons with Previous/Next controls for catalog lists.
- **Breadcrumbs:** Used in Admin shell header and public informational deep links.

## Z-Index

| Element | Z-Index | Context |
|---|---|---|
| Public header | 30 | Sticky top |
| Mobile tab bar | 40 | Fixed bottom |
| Admin sidebar | 20 | Fixed left |
| Admin header | 10 | Sticky top (below sidebar) |

## Accessibility

- Header navigation uses `<nav aria-label="Main navigation">`
- Mobile tab bar icons MUST have visible labels (not icon-only)
- Active route indicated by visual marker AND `aria-current="page"`
- Skip link bypasses all navigation (z-100, visible on focus)
- Notification bell hidden for guests (never shown disabled/empty)

## Shell Adaptation

Shell adaptation occurs at `md:` (768px) — see `docs/design/shared/responsive.md` for full breakpoint and shell adaptation documentation.
