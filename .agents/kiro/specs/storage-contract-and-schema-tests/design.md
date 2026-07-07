# Design: Storage Contract and Schema Tests

## Overview

This design documents and tests the existing file/JSON storage contract. It does not change where artifacts live or what they contain. Instead, it creates a durable reference for maintainers and a focused contract test suite that catches accidental path or schema drift.

The storage contract is important because the repository uses file storage for canonical high-volume artifacts while PostgreSQL stores relational state and projections. Without explicit contracts, migrations, backups, repair tools, and refactors must infer behavior from helper methods.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `docs/storage-contract.md` or `backend/docs/storage-contract.md` | New storage contract document |
| `backend/tests/test_storage_contracts.py` | New contract test module |
| `backend/tests/fixtures/storage_contract/` | New synthetic legacy fixture files |
| Existing storage modules | Read only during implementation; change only if tests reveal missing helper access needed for contract coverage |

### Files Not Touched

- Database models and migrations.
- Storage JSON schemas.
- Public API routes.
- Crawl, translation, glossary, and reader business logic.

## Contract Document Structure

Create a document with this structure:

```markdown
# Storage Contract

## Overview
## Canonical vs Derived State
## Artifact Index
## Novel Metadata
## Metadata Backups
## Raw Chapter Bundles
## Chapter Image Assets
## Translated Chapter Versions
## Translation Edit History
## PostgreSQL Projection Relationship
## Compatibility Rules
## Migration and Repair Notes
```

Recommended location: `docs/storage-contract.md`. If the repository keeps backend-specific docs under `backend/docs`, use `backend/docs/storage-contract.md` instead.

## Artifact Index

The document should include a table like:

| Artifact | Canonical? | Storage owner | Writer | Reader | Notes |
|---|---:|---|---|---|---|
| Novel metadata | Yes | File storage | `save_metadata` | `load_metadata` | Includes chapter list and translated metadata fields |
| Metadata backup | Backup | File storage | backup helper | metadata history/recovery helpers | Timestamped snapshots |
| Raw chapter bundle | Yes | File storage | `save_chapter` | `load_chapter` | Raw text, paragraphs, images, source provenance |
| Chapter image asset | Yes | File storage | `save_chapter_image_asset` | chapter/image loaders | Binary asset plus manifest fields |
| Translated version bundle | Yes | File storage | `save_translated_chapter` | `load_translated_chapter`, `list_translated_chapter_versions` | Active and historical versions |
| Edit history | Yes | File storage | `save_edited_translation` | `load_translation_edit_history` | Human edits and version history |
| SQL novel/chapter rows | Projection/relational state | PostgreSQL | catalog refresh / DB services | query APIs | Searchable status and workflow state |

## Schema Documentation

Use schema outlines, not exhaustive sample dumps. The document should show required fields, optional fields, and compatibility expectations.

### Novel Metadata

Document at least:

```json
{
  "id": "novel-id",
  "title": "Source or translated title",
  "chapters": [
    {
      "id": "1",
      "num": 1,
      "title": "Chapter title",
      "url": "https://example.test/chapter-1"
    }
  ],
  "source_language": "ja",
  "origin_type": "web",
  "origin_uri_or_path": "https://example.test/novel",
  "document_type": "web_novel",
  "input_adapter_key": "syosetu",
  "context_group_id": "..."
}
```

The exact optional fields should be documented from the current loaders and writers.

### Raw Chapter Bundle

Document at least:

```json
{
  "id": "1",
  "source_key": "syosetu",
  "source_url": "https://example.test/chapter-1",
  "raw": {
    "id": "1",
    "scraped_at": "2026-07-07T00:00:00Z",
    "text": "Synthetic raw text",
    "paragraphs": ["Synthetic raw text"],
    "images": [],
    "source_blocks": []
  },
  "origin_type": "web",
  "origin_uri_or_path": "https://example.test/novel",
  "document_type": "web_novel",
  "unit_type": "chapter",
  "input_adapter_key": "syosetu",
  "context_group_id": "..."
}
```

### Translated Chapter Versions

Document active-version behavior and version list structure. The exact field names must come from current `storage/translations.py`, but the contract should cover:

- version ID
- active flag or active version pointer
- translated text
- provider
- model
- version kind
- created/translated timestamp
- glossary revision/hash when present
- editor/note/confidence fields when present

### Edit History

Document:

- chapter ID
- edited text
- editor identity when available
- note/reason when available
- created timestamp
- base version or prior version reference when available

### Image Assets and Manifest Entries

Document manifest fields such as:

- source image URL
- saved asset path/key
- MIME type/content type when available
- width/height when available
- download error when image download fails

The binary image bytes themselves do not need a JSON schema.

## Test Design

Create `backend/tests/test_storage_contracts.py`.

Use existing storage APIs instead of direct private path assertions where possible. If private helpers are the only stable way to assert path contracts, keep assertions narrow and explain why.

### Test Categories

| Category | Purpose |
|---|---|
| Path contract tests | Confirm helper-generated paths and backup patterns do not drift |
| Schema shape tests | Confirm writers emit required fields and loaders normalize optional fields correctly |
| Round-trip tests | Confirm save/load behavior preserves contract fields |
| Version behavior tests | Confirm translated versions and active selection behave deterministically |
| Legacy fixture tests | Confirm older artifact shapes remain readable |
| Additive field tests | Confirm unknown/additive fields do not break loaders unless explicitly forbidden |

## Fixture Design

Add synthetic fixtures under:

```text
backend/tests/fixtures/storage_contract/
  legacy_metadata.json
  legacy_chapter_bundle.json
  legacy_translation_bundle.json
  legacy_edit_history.json
```

Rules:

- Use synthetic text only.
- Keep fixtures minimal.
- Include only fields needed to prove backward compatibility.
- Add comments in the test code, not inside JSON files.
- If exact historical schema is unknown, create fixtures from the oldest supported shape currently handled by loaders.

## Validation Helpers

Add test-only helper functions in the test module or a local fixture helper file:

```python
def assert_metadata_contract(payload: dict[str, Any]) -> None:
    ...

def assert_raw_chapter_contract(payload: dict[str, Any]) -> None:
    ...

def assert_translation_version_contract(payload: dict[str, Any]) -> None:
    ...

def assert_edit_history_contract(payload: Any) -> None:
    ...
```

These helpers should assert:

- required fields exist,
- required fields have expected broad types,
- optional fields are accepted when present,
- unknown additive fields do not fail unless current loaders reject them by design.

Avoid adding runtime JSON schema validation unless the project already uses a schema validation library.

## Path Contract Strategy

Some storage paths may intentionally be private behind helpers. Use this rule:

- If a helper path is part of the operational contract, document and test the path pattern.
- If a helper path is intentionally private, document it as helper-owned and test round-trip behavior instead.

For example, the document can say:

```markdown
Raw chapter bundles are stored under the per-novel chapter directory through `save_chapter` and loaded through `load_chapter`. Callers must not construct the path manually.
```

This allows internal path refactors while preserving the public storage-service contract.

## Compatibility Rules

The contract document should state:

- Loaders should tolerate additive fields.
- Missing optional fields should receive existing default behavior.
- Required fields should be present in newly written artifacts.
- Legacy artifacts should load if they match supported historical shapes.
- SQL projection state can be rebuilt from canonical file storage where existing code supports it.

## Migration and Repair Notes

Add practical notes:

- Do not edit canonical JSON by hand unless backups are available.
- Use storage service helpers for migrations instead of constructing paths ad hoc.
- For corrupted metadata, prefer latest valid metadata backup.
- For stale SQL projection rows, prefer catalog projection refresh rather than manual DB edits.
- Translation versions should not be deleted manually unless active-version pointers are also repaired.

## Acceptance Criteria

1. A storage contract document exists and describes all major file/JSON artifacts.
2. Contract tests cover path generation or observable helper-owned round trips.
3. Contract tests cover metadata, raw chapter, translation version, edit history, and image manifest schema shapes.
4. Legacy synthetic fixtures load successfully through current loaders.
5. Translated chapter version tests prove active-version behavior and historical version preservation.
6. Tests distinguish required fields from optional/additive fields.
7. No storage schemas or DB schemas are changed.
8. Existing storage tests still pass.

