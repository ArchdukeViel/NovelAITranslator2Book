# Participation Domain

## Contract Metadata

| Field | Value |
|---|---|
| Domain | participation |
| Surface | public |
| Routes | `/request-novel`, `/contribute` |
| Authority | `docs/DESIGN.md` -> `docs/design/public/participation/README.md` |

## Domain Purpose

Public novel submission requests and community API contribution landing pages.

## Contained Routes

- `/request-novel` -> [`request-novel.md`](request-novel.md)
- `/contribute` -> [`contribute.md`](contribute.md)

## Audience and Permissions

- **Guests:** Access landing pages, read program guidelines, and fill out request forms. Submitting requests requires authentication (triggers sign-in detour preserving draft data).
- **Authenticated Users:** Submit novel/chapter requests and view request history.

## Shared Navigation and Shell Behavior

- Uses standard `PublicShell` (desktop header nav link / mobile Account & More hub link).

## Shared Data trick and State Rules

- Form data preserved in local draft state across authentication detours.
- Submissions validate source URLs client-side before sending payload.

## Shared Terminology

- `source_url`: URL pointing to original web novel on Kakuyomu, Syosetu, or Syosetu18.

## Page Index

| Page | Document | Purpose |
|---|---|---|
| Request Novel | `request-novel.md` | Public novel and chapter translation request submission page |
| Contribute | `contribute.md` | API contribution program landing page |

## Cross-Domain Dependencies

- Connects to `authentication` domain for sign-in detours.
- Connects to `admin/moderation` domain for request review queue processing.
