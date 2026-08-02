# Trust Domain

## Contract Metadata

| Field | Value |
|---|---|
| Domain | trust |
| Surface | public |
| Routes | `/about`, `/contact`, `/support`, `/faq`, `/news`, `/legal`, `/terms`, `/privacy`, `/cookie-policy`, `/dmca` |
| Authority | `docs/DESIGN.md` -> `docs/design/public/trust/README.md` |

## Domain Purpose

Static informational pages, help & support, FAQ, product changelog, legal terms, privacy policy, and copyright DMCA takedown workflow.

## Contained Routes

- `/about`, `/contact`, `/support`, `/faq`, `/news`, `/legal`, `/terms`, `/privacy`, `/cookie-policy` -> [`informational-pages.md`](informational-pages.md)
- `/dmca` -> [`dmca.md`](dmca.md)

## Audience and Permissions

- **Guests & Authenticated Users:** Open public access to all trust pages.

## Shared Navigation and Shell Behavior

- Accessible via `PublicFooter` links and mobile Account/More hub.
- Standard text layout (720px max content width).

## Shared Data and State Rules

- Mostly static content pages. `FAQ` and `News` pages build on static layouts.

## Shared Terminology

- `DMCA`: Digital Millennium Copyright Act takedown policy.

## Page Index

| Page | Document | Purpose |
|---|---|---|
| Informational Pages | `informational-pages.md` | Static support, FAQ, news, terms, and privacy policy pages |
| DMCA Takedown | `dmca.md` | Copyright policy and DMCA takedown notice submission |

## Cross-Domain Dependencies

- Connects to `admin/moderation` domain for DMCA takedown enforcement.
