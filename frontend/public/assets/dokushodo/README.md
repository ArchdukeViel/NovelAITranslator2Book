# Dokushodo Public Assets

Place generated public-facing Dokushodo artwork here. These files are served by
Next.js from `/assets/dokushodo/...`.

## Shipped assets (in use)

| Asset | Location | Public URL |
|---|---|---|
| Brand mark | `brand/` | `/assets/dokushodo/brand/brand-mark.png` |
| Default OG image (1200×630) | `brand/` | `/assets/dokushodo/brand/open-graph.png` |
| 404 illustration | `illustrations/` | `/assets/dokushodo/illustrations/404.png` |
| Empty-state illustration | `illustrations/` | `/assets/dokushodo/illustrations/empty.png` |
| Maintenance illustration | `illustrations/` | `/assets/dokushodo/illustrations/maintenance.png` |

## Notes

- Fallback novel covers are generated with a CSS gradient bookplate (no image
  assets) so that no real novel artwork is ever simulated.
- Keep cover placeholders text-free so real novel titles remain rendered by the
  UI, not baked into artwork.
- Prefer PNG or WebP. If exporting WebP, keep the same basename, for example
  `brand-mark.webp`, and update the app path when wiring it.
