# Responsive Design System

Layout adaptivity rules across viewports.

## Viewport Breakpoints

| Breakpoint | Width | Target Devices |
|---|---:|---|
| Mobile | < 768px | Smartphones |
| Tablet | 768px - 1023px | Tablets, small laptops |
| Desktop | >= 1024px | Laptops, desktop monitors |

## Layout Rules

- Mobile-first CSS utility approach.
- Safe areas: Fixed elements pad for `env(safe-area-inset-bottom)`.
- Fixed control collision: At most one fixed-bottom control bar active on screen at a time.
- Shell adaptation:
  - Mobile: Brand header + notification bell + fixed bottom tab bar + Account/More hub.
  - Desktop: Header with inline navigation + search overlay trigger + theme toggle + account menu.
- Data tables: Scroll horizontally on small viewports only when card/list transformation loses comparison value.
