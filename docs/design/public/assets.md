# Brand and Illustration Assets

Specification for brand assets, illustrations, and image handling.

## Brand Assets

### Brand Mark

- **File**: `frontend/public/assets/dokushodo/brand/brand-mark.png`
- **Format**: PNG (SVG source not yet available)
- **Design**: Pinched lantern silhouette
- **Recognition**: MUST be recognizable at 16px to 512px
- **Background**: Plum (`#1B141F`) for maskable/PWA contexts

### Open Graph Image

- **File**: `frontend/public/assets/dokushodo/brand/open-graph.png`
- **Dimensions**: 1200×630px (standard OG image)
- **Use**: Default `og:image` meta tag when no novel-specific image is available

### Favicon

- **Status**: Not yet implemented
- **Required**: SVG favicon (primary), 16px PNG, 32px PNG, `apple-touch-icon.png` (180×180px)
- **Tracked in**: `docs/WORK.md` as part of approved asset inventory work

### PWA Icons

- **Status**: Not yet implemented
- **Required**: `any` purpose icon (192×192, 512×512), `maskable` icon on plum background (`#1B141F`)
- **Safe zone**: Maskable icons MUST keep meaningful content within the inner 80% circle

## Illustration System

Flat vector-style illustrations using the canonical Dokushodo export palette.

### Palette

| Color | Hex | Role |
|---|---|---|
| Plum | `#1B141F` | Dark background, outlines |
| Lantern Orange | `#EE862B` | Primary accent |
| Sakura Pink | `#DE7396` | Secondary accent |
| Deep Teal | `#274349` | Structural elements |
| Warm Cream | `#EDE7DE` | Light fills, paper |

### Current Assets

| Illustration | File | Dimensions | Used On |
|---|---|---|---|
| Empty State | `illustrations/empty.png` | Source PNG | Catalog zero results, Library empty state |
| 404 Not Found | `illustrations/404.png` | Source PNG | 404 error page |
| Maintenance | `illustrations/maintenance.png` | Source PNG | Downtime/maintenance page |

### Asset Path

All assets live under `frontend/public/assets/dokushodo/`:

```
frontend/public/assets/dokushodo/
├── brand/
│   ├── brand-mark.png
│   └── open-graph.png
└── illustrations/
    ├── 404.png
    ├── empty.png
    └── maintenance.png
```

## Constraints

- **MUST NOT** use gradients, blur, glow, or shadows in illustration assets
- **MUST NOT** bake text into image files — accessible text lives in HTML
- Images use `alt=""` and `aria-hidden="true"` for decorative illustrations; accessible text provided by surrounding HTML
- Novel cover art ingested through controlled storage only — no hotlinking

## SVG Sanitization

- SVG assets (when introduced) MUST be sanitized: no embedded scripts, no external references, no `data:` URIs
- `viewBox` MUST be present and correctly sized
- Exported at intended display size; no scaling artifacts

## Loading and Fallback

- Novel covers: `FallbackCover` component generates a bookplate from title initials when no cover image exists
- Illustrations: static PNG imports via Next.js `Image` component
- **MUST** set `width`, `height`, and `alt` on all `<img>` and `<Image>` elements
- Decorative images: `alt=""` and `aria-hidden="true"`

## Licensing and Provenance

- All brand assets and illustrations are original works created for Dokushodo
- Novel cover art is ingested from source sites and stored in controlled storage — copyright belongs to original publishers
- No third-party stock imagery or icon sets beyond Lucide (MIT licensed)

## File Size Budgets

| Asset Type | Budget |
|---|---|
| Brand mark PNG | < 50 KiB |
| Open Graph image | < 200 KiB |
| Illustration PNG | < 100 KiB each |
| SVG illustration (future) | < 20 KiB each |
| Favicon SVG (future) | < 5 KiB |
