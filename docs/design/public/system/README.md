# System Domain

## Contract Metadata

| Field | Value |
|---|---|
| Domain | system |
| Surface | public |
| Routes | 404 (`/not-found`), 500 (`/error`), `/maintenance` |
| Authority | `docs/DESIGN.md` -> `docs/design/public/system/README.md` |

## Domain Purpose

Global system boundaries, 404 route handling, runtime error fallbacks, and scheduled maintenance downtime surfaces.

## Contained Routes

- 404 Not Found -> [`error-and-not-found.md`](error-and-not-found.md)
- `/maintenance`, Error Boundary -> [`maintenance.md`](maintenance.md)

## Audience and Permissions

- **Guests & Authenticated Users:** Displayed automatically during invalid route access, unhandled runtime exceptions, or scheduled backend downtime.

## Shared Navigation and Shell Behavior

- Uses dedicated visual illustrations (`not-found.svg`, `maintenance.svg`).
- Provides navigation actions back to `/home` or `/browse-novels`.

## Shared Data and State Rules

- Excludes missing/error routes from sitemap (`noindex, follow`).
- Exposes no raw stack traces, API keys, or internal file paths.

## Shared Terminology

- `404`: Route or novel entity not found.
- `Maintenance`: Scheduled offline window.

## Page Index

| Page | Document | Purpose |
|---|---|---|
| Error & 404 | `error-and-not-found.md` | Missing route (404) and global unhandled exception (500) error pages |
| Maintenance | `maintenance.md` | Scheduled backend downtime status page |

## Cross-Domain Dependencies

- Connects to `discovery` domain for return-to-home and catalog shortcuts.
