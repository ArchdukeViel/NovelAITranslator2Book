# Admin People Domain

## Contract Metadata

| Field | Value |
|---|---|
| Domain | people |
| Surface | admin |
| Routes | `/admin/users`, `/admin/users/[userId]` |
| Authority | `docs/DESIGN.md` -> `docs/design/admin/people/README.md` |

## Domain Purpose

User account administration, account status management (active/disabled), and role management (`user` vs `owner`).

## Contained Routes

- `/admin/users`, `/admin/users/[userId]` -> [`users.md`](users.md)

## Audience and Permissions

- **Owners (`role="owner"`):** Authorized access.
- **Others:** 403 Forbidden.

## Shared Navigation and Shell Behavior

- Integrated with `AdminShell` sidebar navigation under "People" section.

## Shared Data and State Rules

- Cannot demote or disable the bootstrap owner account.
- User status modifications emit `AuditLog` events.

## Shared Terminology

- `role`: Account authorization role (`user` for public readers, `owner` for operators).

## Page Index

| Page | Document | Purpose |
|---|---|---|
| User Management | `users.md` | User accounts list, detail view, role management, and disable toggles |

## Cross-Domain Dependencies

- Connects to `admin/operations` for audit logging.
