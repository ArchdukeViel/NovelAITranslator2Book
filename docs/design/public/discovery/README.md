# Discovery Domain

## Contract Metadata

| Field | Value |
|---|---|
| Domain | discovery |
| Surface | public |
| Routes | `/`, `/home`, `/browse-novels`, `/tags/[tag]`, `/genres/[genre]`, `/sources/[sourceKey]`, `/random`, shared search overlay |
| Authority | `docs/DESIGN.md` -> `docs/design/public/discovery/README.md` |

## Domain Purpose

Catalog exploration, novel discovery, taxonomy filtering, search indexing, and random novel selection.

## Contained Routes

- `/home` -> [`home.md`](home.md)
- `/browse-novels` -> [`browse.md`](browse.md)
- `/tags/[tag]`, `/genres/[genre]`, `/sources/[sourceKey]` -> [`taxonomy.md`](taxonomy.md)
- Shared Search Overlay -> [`search.md`](search.md)

## Audience and Permissions

- **Guests:** Unrestricted access to browse catalog, view home rails, filter taxonomy, search titles, and use random redirect.
- **Authenticated Users:** Retain all guest capabilities plus personalized "Continue Reading" progress rail.

## Shared Navigation and Shell Behavior

- Integrated with global `PublicShell`: desktop inline navigation header, mobile bottom tab bar.
- Mobile search tab opens shared search overlay directly.

## Shared Data and State Rules

- Query parameters drive filter state (`/browse-novels?genre=...&status=...&sort=...`).
- TanStack Query hooks handle client-side caching and refetching (`usePublicCatalog`, `usePublicTaxonomy`).
- URL filter changes update browsing state without full page reloads.

## Shared Terminology

- `source_key`: Canonical identifier for scraping source platform (e.g. Kakuyomu, Syosetu, Syosetu18).
- `tag`: Specific descriptive keyword attached to a novel.
- `genre`: Top-level categorization theme.

## Page Index

| Page | Document | Purpose |
|---|---|---|
| Home Page | `home.md` | Featured spotlight, personalized continue reading, new releases, and genre rails |
| Browse Catalog | `browse.md` | Filterable novel grid with sort, search, and view toggles |
| Search Overlay | `search.md` | Shared modal/sheet search interface for quick title, author, and tag lookup |
| Taxonomy & Source | `taxonomy.md` | Dedicated canonical pre-filtered landing pages for genres, tags, and sources |

## Cross-Domain Dependencies

- Links directly to `reading` domain (`/novels/[slug]`).
- Integrates with `account` domain for reading progress and library save actions.
