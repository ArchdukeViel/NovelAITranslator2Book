# Reading Domain

## Contract Metadata

| Field | Value |
|---|---|
| Domain | reading |
| Surface | public |
| Routes | `/novels/[slug]`, `/novels/[slug]/chapter/[chapterId]` |
| Authority | `docs/DESIGN.md` -> `docs/design/public/reading/README.md` |

## Domain Purpose

Novel detail landing, metadata inspection, community reviews, chapter table of contents, and distraction-free long-form reader interface.

## Contained Routes

- `/novels/[slug]` -> [`novel-detail.md`](novel-detail.md)
- `/novels/[slug]/chapter/[chapterId]` -> [`chapter-reader.md`](chapter-reader.md)

## Audience and Permissions

- **Guests:** Access novel overview, chapter list, community reviews, and read translated chapters.
- **Authenticated Users:** Save novel to library, track reading progress automatically, post/edit reviews, and request missing chapters.

## Shared Navigation and Shell Behavior

- **Novel Detail:** Uses standard `PublicShell` (desktop header / mobile tab bar). Mobile sticky bottom bar replaces bottom tab bar on detail screen.
- **Chapter Reader:** Header and tab bar suppressed for low distraction. Replaced by minimal top reading progress bar and floating "Aa" settings button.

## Shared Data and State Rules

- Tab selection on novel detail URL-synced (`?tab=overview`, `?tab=chapters`, `?tab=reviews`).
- Reader settings (font size, column width, reader theme) stored in local client state (`localStorage`) and applied instantaneously.
- Account reading progress automatically synced via background API call (`useUpdateProgress`).

## Shared Terminology

- `slug`: URL-safe identifier for a novel.
- `chapterId`: Stable identifier for a chapter.
- `bookplate`: Generated fallback cover art when no custom illustration exists.

## Page Index

| Page | Document | Purpose |
|---|---|---|
| Novel Detail | `novel-detail.md` | Sticky overview panel, chapter table of contents, community reviews |
| Chapter Reader | `chapter-reader.md` | Distraction-free chapter reader with progress bar and Aa typography controls |

## Cross-Domain Dependencies

- Connects to `discovery` domain for taxonomy links and catalog navigation.
- Connects to `account` domain for saving to library and managing reading history.
