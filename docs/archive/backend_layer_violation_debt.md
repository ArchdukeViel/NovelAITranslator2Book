# Backend Layer Violation Debt (ARCHIVED)

**Archived:** 2026-07-12
**Reason:** Superseded by [`docs/DEBT.md`](../DEBT.md) as the canonical debt register.
**Canonical entries:** DEBT-054 (consolidated router layer violations), DEBT-006 (circular import in admin_glossary routers), DEBT-012 through DEBT-020 (individual service extractions).

---

This document tracks the router layer violations identified during the
backend audit. Per architecture.md §3, routers should not import
`db.models.*` or `storage.service.StorageService` directly — use-case
logic belongs in `services/`.

> **Note:** This file is archived. Active debt entries are in [`docs/DEBT.md`](../DEBT.md).

## Status: Partially addressed

The following quick wins were completed:
- `activity.py` — inline `db.models.novel` import replaced with
  `services/novel_query_service.py` call.
- `sources.py` — `sources.registry` import replaced with
  `services/source_catalog_service.py` call.
- `admin_taxonomy.py` — all DB logic extracted to
  `services/taxonomy_service.py`. Router is now thin.

## Remaining violations (deferred)

### 1. `library.py` — WORST OFFENDER

**Violations:** 3 `db.models` imports (ChapterModel, NovelGlossaryEntry,
Novel), 1 `sources.status` import, 1 `storage.service` import, ~30
direct `storage.*` calls (including `save_metadata`, `delete_novel`).

**Fix:** Extract `LibraryService` covering all storage and DB operations.
Move `normalize_publication_status` calls behind the service.

### 2. `admin_glossary.py` — HEAVY VIOLATIONS

**Violations:** 6 `db.models.glossary` symbols, `Novel`, 2 `providers.*`
imports (`TranslationProvider`, `get_provider`), `StorageService`, 6
direct storage calls (including mutations).

**Fix:** Extract `GlossaryWorkflowService` for candidate import, apply,
and provider suggestion flows. Move `_TranslationProviderGlossarySuggestionAdapter`
into `services/glossary_provider_suggestion.py`.

### 3. `auth.py` — HEAVY DB CRUD

**Violations:** 3 `db.models.users` symbols (User, PasswordResetToken,
EmailVerificationToken), ~25 `session.query/add/flush` calls.

**Fix:** Extract `AuthService` covering all user/token CRUD operations.

### 4. `user_data.py` — HEAVY DB CRUD

**Violations:** 7 `db.models` symbols (Chapter, Novel, +5 users models),
27 `session.*` CRUD operations.

**Fix:** Extract `UserLibraryService`, `ReadingService`, `ReviewService`.

### 5. `public.py` — HEAVY DB + STORAGE

**Violations:** 3 `db.models` symbols (Genre, Novel, Tag), 1
`sources.status` import, `StorageService`, ~18 direct storage calls.

**Fix:** Extract `PublicCatalogService` covering all catalog browse,
novel detail, chapter list, and chapter read operations.

### 6. `editor.py` — STORAGE + INLINE DB

**Violations:** 1 inline `db.models.novel` import, `StorageService`,
12 direct storage calls (including `save_edited_translation`,
`activate_translated_chapter_version`).

**Fix:** Extract `EditorService` covering all storage operations.

### 7. `requests.py` — DB CRUD

**Violations:** 2 `db.models` symbols (Novel, NovelRequest), full CRUD
in router.

**Fix:** Extract `NovelRequestService`.

### 8. `admin.py` — LIGHT STORAGE LEAK

**Violations:** `StorageService` import, 3 direct `storage.load_metadata`
preflight calls.

**Fix:** Move preflight checks into `AdminService`.

### 9. `operations.py` — LIGHT STORAGE LEAK

**Violations:** `StorageService` import (mostly pass-through), 1 direct
`storage.load_metadata` preflight call.

**Fix:** Move preflight check into `OperationsService`.

## Priority Order

1. `library.py` (worst, ~30 storage calls)
2. `admin_glossary.py` (heavy, includes provider imports)
3. `auth.py` (heavy CRUD, no service layer)
4. `user_data.py` (heavy CRUD, 7 models)
5. `public.py` (heavy, but read-only)
6. `editor.py` (medium, includes mutations)
7. `requests.py` (medium, full CRUD)
8. `admin.py` (light, 3 preflight calls)
9. `operations.py` (lightest, 1 preflight call)

## Recommendation

Do these as separate PRs, one router at a time, with full test
verification after each. Estimated effort: 1-2 days per router.
