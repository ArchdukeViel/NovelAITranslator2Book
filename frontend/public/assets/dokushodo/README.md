# Dokushodo Public Assets

Place generated public-facing Dokushodo artwork here. These files are served by
Next.js from `/assets/dokushodo/...`.

## Rename Map

| Generated asset | Put it here | Rename to | Public URL |
|---|---|---|---|
| Wide homepage hero background, misty torii/forest, 1600x900 or larger | `home/` | `hero-torii-forest.png` | `/assets/dokushodo/home/hero-torii-forest.png` |
| Dark seamless washi/charcoal paper texture, square | `texture/` | `charcoal-washi.png` | `/assets/dokushodo/texture/charcoal-washi.png` |
| Generic fantasy cover placeholder, 2:3 ratio | `covers/` | `cover-fantasy.png` | `/assets/dokushodo/covers/cover-fantasy.png` |
| Generic mystery/shrine corridor cover placeholder, 2:3 ratio | `covers/` | `cover-mystery.png` | `/assets/dokushodo/covers/cover-mystery.png` |
| Generic completed-novel/still-life cover placeholder, 2:3 ratio | `covers/` | `cover-completed.png` | `/assets/dokushodo/covers/cover-completed.png` |
| Generic archive/bookplate cover placeholder, 2:3 ratio | `covers/` | `cover-archive.png` | `/assets/dokushodo/covers/cover-archive.png` |
| Square vermillion hanko mark with `読`, transparent PNG preferred | `brand/` | `dokushodo-mark.png` | `/assets/dokushodo/brand/dokushodo-mark.png` |
| Horizontal Dokushodo wordmark, transparent PNG preferred | `brand/` | `dokushodo-wordmark.png` | `/assets/dokushodo/brand/dokushodo-wordmark.png` |
| Open Graph preview image, 1200x630 | `brand/` | `open-graph.png` | `/assets/dokushodo/brand/open-graph.png` |

## Notes

- Do not use source-site cover images here unless they are approved and cached
  through a safe public asset path.
- Keep cover placeholders text-free so real novel titles remain rendered by the
  UI, not baked into artwork.
- Prefer PNG or WebP. If exporting WebP, keep the same basename, for example
  `hero-torii-forest.webp`, and update the app path when wiring it.
