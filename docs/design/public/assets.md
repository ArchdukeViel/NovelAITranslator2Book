# Brand and Illustration Assets

Specification for brand assets and SVG illustrations.

## Brand Assets

- **Brand Mark (`brand-mark.svg`):** Pinched lantern silhouette. Recognized at 16px to 512px.
- **Favicon:** SVG + 16/32px PNG fallbacks.
- **PWA / App Icons:** Any + maskable icon on plum background (`#1B141F`).

## Illustration System

Flat vector illustrations using canonical export palette (`#1B141F`, `#EE862B`, `#DE7396`, `#274349`, `#EDE7DE`).

| Illustration | Asset File | Used On | Purpose |
|---|---|---|---|
| Default OG | `og-default-source.*` | Meta tags | Default social share image (1200x630) |
| Empty State | `empty-state.svg` | Catalog, Library | Zero-result state |
| 404 Not Found | `not-found.svg` | 404 Page | Playful wrong-turn scene |
| Maintenance | `maintenance.svg` | Downtime | Temporary shopfront closed scene |

## Constraints

- No gradients, blur, glow, or shadows.
- No generated or baked-in text in images.
- Images use `alt=""` and `aria-hidden="true"`; accessible text lives in HTML.
- Novel cover art ingested through controlled storage only (no hot-linking).
