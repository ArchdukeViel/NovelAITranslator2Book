# Public Design System — Yokocho Lantern

Visual identity and token specification for public surfaces.

## Theme & Palette

Dark-first night-market aesthetic with warm lantern highlights.

| Token | Dark (default) | Light (alt) | Purpose |
|---|---|---|---|
| `--background` | `280 20% 10%` | `35 35% 96%` | Page background |
| `--foreground` | `35 30% 90%` | `280 18% 14%` | Default text |
| `--card` | `275 16% 14%` | `0 0% 100%` | Card & popover surfaces |
| `--primary` | `28 85% 55%` | `28 78% 50%` | Lantern orange CTAs |
| `--secondary` | `190 30% 22%` | `190 30% 85%` | Deep teal structural chips |
| `--muted` | `275 12% 20%` | `30 20% 90%` | Muted backgrounds |
| `--accent` | `340 62% 66%` | `340 55% 40%` | Sakura pink (hearts/ratings only) |
| `--focus-ring` | `28 85% 65%` | `28 78% 45%` | Focus indicators |

## Color Usage Rules

- **Sakura pink (`--accent`)** is strictly reserved for favorites, ratings, and save-to-library actions. Never for primary buttons or focus rings.
- **Lantern orange (`--primary`)** carries all primary CTAs ("Start Reading", "Sign in").
- **Deep teal (`--secondary`)** used for structural chips and section dividers.

## Typography

- **Display & Titles:** Noto Serif JP
- **UI & Body Copy:** DM Sans
- **Metadata & Numbers:** DM Mono

## Motifs

- **Pill lantern status badges:** Flat status color mapping.
- **Halo ring:** `--primary` flat-fill ring around active novel covers.
- **Noren curtain divider:** Thin vertical stroke section breaks.
