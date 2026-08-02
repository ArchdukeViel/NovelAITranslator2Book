# Admin Moderation Domain

## Contract Metadata

| Field | Value |
|---|---|
| Domain | moderation |
| Surface | admin |
| Routes | `/admin/requests`, `/admin/reviews`, `/admin/takedowns` |
| Authority | `docs/DESIGN.md` -> `docs/design/admin/moderation/README.md` |

## Domain Purpose

User request approval queues, public review moderation, and legal DMCA takedown enforcement.

## Contained Routes

- `/admin/requests` -> [`requests.md`](requests.md)
- `/admin/reviews` -> [`reviews.md`](reviews.md)
- `/admin/takedowns` -> [`takedowns.md`](takedowns.md)

## Audience and Permissions

- **Owners (`role="owner"`):** Authorized access.
- **Others:** 403 Forbidden.

## Shared Navigation and Shell Behavior

- Integrated with `AdminShell` sidebar navigation under "Moderation" section.

## Shared Data and State Rules

- Moderation operations record structured `AuditLog` events.
- Approved or rejected decisions propagate immediately to public reader APIs.

## Shared Terminology

- `Takedown`: Legal removal of a novel title, setting state to HTTP 451 unavailable.

## Page Index

| Page | Document | Purpose |
|---|---|---|
| Requests Queue | `requests.md` | Moderation table for novel/chapter translation requests |
| Review Moderation | `reviews.md` | Moderation interface for user-submitted novel reviews |
| DMCA & Takedowns | `takedowns.md` | Legal notice management and takedown execution |

## Cross-Domain Dependencies

- Connects to `admin/ingestion` domain for auto-queuing approved novel requests into crawler jobs.
- Connects to `admin/operations` for audit logging.
