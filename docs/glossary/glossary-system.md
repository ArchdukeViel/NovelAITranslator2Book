# Glossary System

Current implementation — what exists, how it works, where to find it.

## Overview

The glossary system keeps novel terminology (names, places, ranks, magic terms) stable across all chapters of a novel. Glossary ownership is per novel (`novel_id`), not per source site.

Two parallel storage layers exist:

| Layer | Location | Purpose |
|---|---|---|
| **File-glossary** | `storage/novel_library/{slug}/glossary.json` | Auto-extracted terms, review staging, sync source |
| **DB glossary** | `novel_glossary_entries` + 5 related tables | Canonical approved terms, prompt injection, audit trail |

The **sync bridge** promotes approved file-glossary entries into the DB.

## Glossary Entry Statuses

### File-glossary statuses

| Status | Meaning |
|---|---|
| `approved` | Owner approved, eligible for sync to DB |
| `needs_manual_review` | Needs owner decision, synced as DB `candidate` |
| `pending` | Freshly extracted, not reviewed |
| `ignored` | Owner dismissed |
| `translated` | Handled at translation time (legacy marker) |

### DB entry statuses

| Status | Meaning |
|---|---|
| `candidate` | Auto-extracted or imported, needs review |
| `recommended` | Provider or manually recommended |
| `approved` | Owner-confirmed, injected into translation prompts |
| `rejected` | Owner-rejected |
| `deprecated` | Superseded by another entry |

### Novel-level glossary status

Stored on the `Novel` model as `glossary_status`:

- `glossary_pending` — no glossary ready yet
- `glossary_ready` — approved entries exist
- `glossary_skipped` — owner opted out

`glossary_revision` (int) increments on every change to the approved entry set. Translation pipeline uses this to detect stale cached output.

## How Glossary Gets Into Translations

Two parallel paths feed into the translation prompt:

1. **DB-approved terms** (newer, preferred): `GlossaryPromptInjectionService.build_for_chapter()` queries DB for approved entries, renders them as a `GLOSSARY FOR THIS NOVEL` block. Called from `TranslateStage._build_prompt_glossary_block()`.

2. **Runtime file-glossary** (older): `_normalize_runtime_glossary()` reads file-glossary entries from pipeline context. `_select_chunk_glossary()` picks chunk-relevant terms. Both paths concatenate into `additional_instructions` in the prompt.

## File-Glossary ↔ DB Sync Bridge

`GlossarySyncService.sync_from_file()` in `glossary_sync_service.py`:

- Only `approved` (→ DB `approved`) and `needs_manual_review` (→ DB `candidate`) entries sync
- Upserts on `canonical_term` match
- No downgrade: existing DB `approved` stays even if file changes
- Creates decision events, increments revision
- API: `POST /novels/{id}/glossary/sync-to-db`, `GET /novels/{id}/glossary/sync-status`

## Backend Files

| File | What it does |
|---|---|
| `db/models/glossary.py` | 6 ORM models: entries, aliases, provenance, decision events, QA findings, display overrides |
| `services/glossary_repository.py` | CRUD for all glossary tables |
| `services/glossary_sync_service.py` | sync bridge (file→DB) |
| `services/glossary_prompt_injection.py` | builds prompt glossary block from DB |
| `services/glossary_candidate_import.py` | heuristic candidate extraction from chapters |
| `services/glossary_provider_suggestion.py` | LLM-assisted candidate suggestions |
| `services/glossary_apply_preview.py` | preview replacement matches in translated text |
| `services/glossary_apply.py` | apply replacements to chapters (with backup/rollback) |
| `services/glossary_status_service.py` | transitions novel-level glossary_status |
| `storage/glossary.py` | save/load file-glossary JSON |
| `api/routers/admin_glossary.py` | ~25 admin endpoints |
| `glossary/orchestration/glossary.py` | extract_glossary_terms() pipe function |
| `translation/pipeline/stages/translate.py` | TranslateStage glossary integration |
| `prompts/builders.py` | glossary → prompt text assembly |

## Frontend

- `frontend/components/admin/glossary/admin-glossary-shell.tsx` — full admin glossary management UI
