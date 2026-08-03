# Domain Contract Template

## Contract Metadata

| Field | Value |
|---|---|
| Domain | <domain-name> |
| Surface | public or admin |
| Routes | list of routes |
| Owner | role or team owner |
| Last reviewed | YYYY-MM-DD |
| Design status | approved, draft, or deferred |
| Implementation status | implemented, partial, drifted, or unavailable |
| Active work | work ID or none |
| Design-system dependencies | tokens, components, assets required |
| Accessibility assumptions | WCAG target, specific screen-reader or keyboard rules |
| Localization | supported languages, CJK wrapping, timezone rules |
| Performance | domain-specific performance budgets |
| Verification evidence | test files, build checks, manual acceptance records |
| Cross-domain risks | dependencies on other domains or backend APIs |
| Authority | `docs/DESIGN.md` -> `docs/design/<surface>/<domain>/README.md` |

## Domain Purpose

[Summary of domain purpose and responsibilities]

## Contained Routes

- `/route-path` -> `docs/design/<surface>/<domain>/<page>.md`

## Audience and Permissions

[User roles, guest access, authentication requirements]

## Shared Navigation and Shell Behavior

[Domain navigation patterns, breadcrumbs, layout wrappers]

## Shared Data and State Rules

[Query patterns, caching, common data structures, real-time updates]

## Shared Terminology

[Canonical names used across pages in this domain]

## Page Index

| Page | Document | Purpose |
|---|---|---|
| Page Name | `<page-file>.md` | Summary |

## Cross-Domain Dependencies

[Relationships to other domains or backend services]
