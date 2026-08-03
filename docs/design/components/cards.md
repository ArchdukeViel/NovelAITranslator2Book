# Component Contract — Cards

## Specifications

### 1. Compact Rail Card
- **Used On:** Homepage rails, "See all" horizontal scrollers.
- **Anatomy:** Cover thumbnail (2:3 aspect ratio), translated title, status lantern badge, chapter count / latest chapter label, save button icon.
- **Constraints:** No synopsis. Cover and title link to novel detail page. Save icon is a separate button.

### 2. Rich Browse Card
- **Used On:** Catalog browse grid, taxonomy pages, author pages.
- **Anatomy:** 2:3 cover art (or restyled bookplate), translated title (primary) + Japanese title (secondary), author name, status badge, chapter count, last updated timestamp, rating summary, up to 3 genre chips, single-line synopsis excerpt, Start/Continue CTA.
- **F20 Fix:** Card surface is NOT wrapped in a master link. Cover/title link, Start button link, and Save button are separate interactive elements sharing one visual card frame.

## Token Usage

- Card surface: `bg-card text-card-foreground` (Panel component: `border bg-card text-card-foreground rounded-lg`)
- Card border: `border-border`
- Hover: `hover:border-accent/30 hover:bg-card` (subtle border tint, full opacity background)
- Cover image: `object-cover transition-transform duration-300 group-hover:scale-[1.02]`
- Title: `font-literary font-semibold` (Noto Serif JP)
- Japanese subtitle: `font-literary text-accent`
- Metadata: `text-muted-foreground text-sm`

## Accessibility

- Card is NOT a single interactive element — individual links/buttons within the card frame
- Cover image and title link to novel detail (separate `<a>` elements with same `href`)
- Save button is an independent `<button>` with `aria-label`
- No nested interactive controls
- Status badge includes text content for color-independent identification

## States

| State | Presentation |
|---|---|
| Default | Border, card background |
| Hover | Accent border tint, cover subtle zoom |
| Loading | Skeleton pulse matching card dimensions |
| Empty (no cover) | Fallback bookplate with initial and title |

## Implementation

- `frontend/components/public/novel-card.tsx` — Both compact and rich variants
- `frontend/components/public/fallback-cover.tsx` — Generated bookplate cover
- `frontend/components/ui/panel.tsx` — Generic card/panel container
