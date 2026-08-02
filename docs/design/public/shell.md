# Public Shell & Navigation

Navigation frame and global shell behavior for public visitors.

## Layout Adaptivity

- **Desktop (>= 768px):** Header with inline links (Home, Browse, Request, Library), search overlay button, theme toggle, notification bell, user menu.
- **Mobile (< 768px):** Compact header (brand + bell) + fixed bottom tab bar (Home, Browse, Search, Library, Account).

## Navigation Hubs

- **Mobile Search Tab:** Triggers full-screen search overlay.
- **Mobile Account Tab:** Serves as Account/More hub (Library, History, Requests, Settings + links to Ranking, Contribute, FAQ, News, Legal).

## Reader Chrome Suppression

On `/novels/[slug]/chapter/[chapterId]` routes:
- Header shrinks to minimal back caret + title.
- Global bottom tab bar and footer are suppressed.
- Active reader controls: floating "Aa" settings button + top progress bar.

## Fixed Control Collision Policy

- At most one fixed bottom bar rendered at a time.
- Safe-area bottom padding enforced for gesture bars.
