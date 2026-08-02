# Authentication Domain

## Contract Metadata

| Field | Value |
|---|---|
| Domain | authentication |
| Surface | public |
| Routes | `/login`, `/auth/callback`, `/logout` |
| Authority | `docs/DESIGN.md` -> `docs/design/public/authentication/README.md` |

## Domain Purpose

User sign-in, account registration, OAuth callbacks, and session termination.

## Contained Routes

- `/login` -> [`login.md`](login.md)
- `/auth/callback`, `/logout` -> [`session-flows.md`](session-flows.md)

## Audience and Permissions

- **Guests:** Access `/login` to authenticate or register a user account (`role="user"`).
- **Authenticated Users:** Access `/logout` to terminate active session.

## Shared Navigation and Shell Behavior

- `/login` is the canonical standalone authentication page.
- Auth Modal (desktop dialog / mobile full-screen sheet) renders the exact same underlying form component as `/login`.
- Authentication flow preserves triggering destination route via `next` query parameter (`/login?next=/account/library`).

## Shared Data and State Rules

- Credentials submitted via HTTPS with CSRF protection.
- Successful authentication establishes httpOnly session cookies.
- Public registration creates `role="user"` accounts only; never promotes an owner.

## Shared Terminology

- `next`: URL query parameter carrying target destination after authentication.

## Page Index

| Page | Document | Purpose |
|---|---|---|
| Login / Register | `login.md` | Standalone login page and modal dialog wrapper |
| Session Flows | `session-flows.md` | OAuth callback processor and session logout page |

## Cross-Domain Dependencies

- Connects to `account` domain upon successful login redirect.
