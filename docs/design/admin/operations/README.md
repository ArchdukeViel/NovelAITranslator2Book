# Admin Operations Domain

## Contract Metadata

| Field | Value |
|---|---|
| Domain | operations |
| Surface | admin |
| Routes | `/admin`, `/admin/dashboard`, `/admin/analytics`, `/admin/audit`, `/admin/maintenance`, `/admin/credentials`, `/admin/settings` |
| Authority | `docs/DESIGN.md` -> `docs/design/admin/operations/README.md` |

## Domain Purpose

System health overview, telemetry analytics, administrative audit logging, maintenance schedule inspection, provider credential management, and application configuration.

## Contained Routes

- `/admin`, `/admin/dashboard` -> [`dashboard.md`](dashboard.md)
- `/admin/analytics` -> [`analytics.md`](analytics.md)
- `/admin/audit` -> [`audit.md`](audit.md)
- `/admin/maintenance` -> [`maintenance.md`](maintenance.md)
- `/admin/credentials` -> [`credentials.md`](credentials.md)
- `/admin/settings` -> [`settings.md`](settings.md)

## Audience and Permissions

- **Owners (`role="owner"`):** Authorized access.
- **Others:** 403 Forbidden.

## Shared Navigation and Shell Behavior

- Integrated with `AdminShell` sidebar navigation under "Operations" section.

## Shared Data and State Rules

- Diagnostics, credentials, and logs mask sensitive data (`mask-token.ts`).
- Operations surfaces communicate directly with owner-only administrative endpoints.

## Shared Terminology

- `AuditLog`: Immutable record of administrative operations.
- `Durable Maintenance`: Scheduled background cleanup tasks with persistent state.

## Page Index

| Page | Document | Purpose |
|---|---|---|
| Dashboard | `dashboard.md` | System overview landing page and operational metric cards |
| Analytics | `analytics.md` | Telemetry, traffic, and translation token usage charts |
| Audit Log | `audit.md` | Immutable record of administrative operations |
| Maintenance Status | `maintenance.md` | Scheduled background task inspector and manual trigger |
| Credentials | `credentials.md` | Provider API key and service secret management |
| System Settings | `settings.md` | Global application configuration parameters |

## Cross-Domain Dependencies

- Monitors and logs operations across all backend domains.
