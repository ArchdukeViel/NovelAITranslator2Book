# Admin Content Domain

## Contract Metadata

| Field | Value |
|---|---|
| Domain | content |
| Surface | admin |
| Routes | `/admin/library`, `/admin/translation`, `/admin/editor`, `/admin/novels/[novelId]/glossary` |
| Authority | `docs/DESIGN.md` -> `docs/design/admin/content/README.md` |

## Domain Purpose

Catalog novel administration, AI translation job orchestration, side-by-side chapter translation editing, and glossary dictionary maintenance.

## Contained Routes

- `/admin/library` -> [`library.md`](library.md)
- `/admin/translation` -> [`translation.md`](translation.md)
- `/admin/editor` -> [`editor.md`](editor.md)
- `/admin/novels/[novelId]/glossary` -> [`glossary.md`](glossary.md)

## Audience and Permissions

- **Owners (`role="owner"`):** Authorized access.
- **Others:** 403 Forbidden.

## Shared Navigation and Shell Behavior

- Integrated with `AdminShell` sidebar navigation under "Content" section.

## Shared Data and State Rules

- Full CRUD operations over catalog metadata and chapter translations.
- Raw scraped Japanese source text preserved independently of translation output versions.

## Shared Terminology

- `Glossary`: Novel-specific translation dictionary mapping CJK terms to English equivalents.

## Page Index

| Page | Document | Purpose |
|---|---|---|
| Library Management | `library.md` | Operator administration view for all catalog novels |
| Translation Jobs | `translation.md` | Orchestration dashboard for AI translation batch jobs |
| Chapter Editor | `editor.md` | Side-by-side Japanese/English chapter translation editor |
| Glossary Manager | `glossary.md` | Term dictionary and auto-population manager |

## Cross-Domain Dependencies

- Connects to `admin/operations` domain for translation provider credentials and token usage tracking.
