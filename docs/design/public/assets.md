# Brand and Illustration Assets

Specification for brand assets, illustrations, brand taxonomy, gradient boundaries, and image handling.

## Brand Asset Taxonomy

### Canonical Brand Mark (Minimalist UI Header Mark)

- **File**: `frontend/public/assets/dokushodo/brand/brand-mark.png`
- **Format**: PNG (1-color / minimalist silhouette)
- **Design**: Pinched lantern silhouette without detailed gradients
- **Use**: Desktop/mobile navigation headers, footer brand mark
- **Recognition**: MUST be recognizable at 16px to 64px height
- **Safe Zone**: 4px padding around mark

### Canonical App Icon (Detailed Vector / App Store / PWA)

- **File**: `frontend/public/assets/dokushodo/brand/icon.svg`
- **Format**: SVG (Primary scalable vector source)
- **Design**: Detailed lantern with soft window glow, kanji accent (読), and tassel
- **Use**: Vector icon source for browsers, favicons, app shortcuts
- **Favicon Fallback**: `frontend/public/assets/dokushodo/brand/favicon.ico`
- **Apple Touch Icon**: `frontend/public/assets/dokushodo/brand/apple-touch-icon.png` (180×180px)

### PWA Icons & Web Manifest

- **Files**:
  - `frontend/app/manifest.ts` (App Router metadata route for `manifest.webmanifest`)
  - `frontend/public/assets/dokushodo/brand/icon-192.png` (`any` purpose icon, 192×192)
  - `frontend/public/assets/dokushodo/brand/icon-512.png` (`maskable` purpose icon, 512×512, background `#1B141F`)

### Open Graph Image (Social Sharing)

- **File**: `frontend/public/assets/dokushodo/brand/open-graph.png`
- **Dimensions**: 1200×630px (standard OG image)
- **Use**: Default `og:image` and `twitter:image` meta tag when no novel-specific cover image is available

---

## Gradient & Glow Policy Boundary

- **UI Surfaces**: **STRICTLY PROHIBITED**. Buttons, cards, navigation bars, modal dialogs, and section backgrounds MUST NOT use gradients, radial glows, drop-shadow glows, or mesh blurs.
- **Brand App Icon (`icon.svg`)**: **PERMITTED**. Vectors within `icon.svg` use subtle linear gradients (`#E23E1D` to `#C22F13`) and window glows (`#FFF3E0` to `#FFE0B2`) to provide richness at icon scale.
- **Illustration Assets**: **PERMITTED (Restrained)**. Vector illustrations under `illustrations/` may use subtle tonal fills, but MUST NOT use synthetic blurs or glassmorphism.

---

## Illustration System

Flat vector-style illustrations using the canonical Dokushodo export palette.

### Palette

| Color | Hex | Role |
|---|---|---|
| Midnight Slate | `#1B141F` | Dark background, outlines |
| Shuji Vermillion | `#EE862B` / `#E23E1D` | Primary action / signature accent |
| Sakura Pink | `#DE7396` | Secondary accent |
| Soft Teal | `#274349` | Structural elements |
| Washi Warm Paper | `#EDE7DE` / `#F8F6F0` | Light fills, paper surfaces |

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
│   ├── apple-touch-icon.png
│   ├── brand-mark.png
│   ├── favicon.ico
│   ├── icon-192.png
│   ├── icon-512.png
│   ├── icon.svg
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
