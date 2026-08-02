# Admin Ingestion Domain

## Contract Metadata

| Field | Value |
|---|---|
| Domain | ingestion |
| Surface | admin |
| Routes | `/admin/crawler`, `/admin/activity`, `/admin/activity/[activityId]` |
| Authority | `docs/DESIGN.md` -> `docs/design/admin/ingestion/README.md` |

## Domain Purpose

Web novel crawling triggers, source scraping management, and real-time activity monitoring.

## Contained Routes

- `/admin/crawler` -> [`crawler.md`](crawler.md)
- `/admin/activity`, `/admin/activity/[activityId]` -> [`activity.md`](activity.md)

## Audience and Permissions

- **Owners (`role="owner"`):** Full access to trigger crawls and inspect scraping activity.
- **Regular Users / Guests:** Access forbidden (`403 Forbidden`).

## Shared Navigation and Shell Behavior

- Integrated with `AdminShell` sidebar navigation under "Ingestion" section.

## Shared Data and State Rules

- Real-time or polled activity status updates via `useAdminActivity`.
- Executed jobs create structured `ActivityLog` records.

## Shared Terminology

- `Crawl`: Automated web scraping process fetching novel metadata and raw chapter HTML from source platforms (Syosetu, Kakuyomu, Novel18).

## Page Index

| Page | Document | Purpose |
|---|---|---|
| Crawler Control | `crawler.md` | Interface for initiating source crawls |
| Activity Monitor | `activity.md` | Table and detail log viewer for background crawl jobs |

## Cross-Domain Dependencies

- Connects to `admin/content` domain as completed crawls create raw chapters ready for translation.
