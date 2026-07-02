# Design: Create-Novel Lifecycle

## Overview

Two targeted code additions plus integration tests. No new DB migrations needed — the `Novel` model already has all required fields. No new storage modules needed. Changes: (1) add `POST /api/admin/novels` to `library.py`, (2) add post-scrape DB reconciliation to `OperationsService.scrape_novel` and `preliminary_crawl_novel`, (3) add integration test.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/api/routers/library.py` | Add `POST /` create endpoint; add `NovelCreateRequest` and `NovelCreateResponse` models |
| `backend/src/novelai/services/orchestration/operations.py` | Add best-effort `CatalogService.reconcile_catalog_projection` after scrape_metadata completes |
| `backend/tests/test_novel_lifecycle_integration.py` | New — full lifecycle test |

### Files Not Touched

- `db/models/novel.py` — no schema change
- Any migration files — no new columns
- `storage/service.py` — `save_metadata` unchanged
- `api/routers/operations.py` — router unchanged; `OperationsService` owns the change

## Component Design

### 1. `POST /api/admin/novels` in `library.py`

```python
class NovelCreateRequest(BaseModel):
    novel_id: str
    title: str
    source_url: str | None = None
    source_key: str | None = None
    language: str = "ja"

class NovelCreateResponse(BaseModel):
    novel_id: str
    title: str
    source_url: str | None
    source_key: str | None
    language: str
    created_at: str
    db_id: int

@router.post("/", response_model=NovelCreateResponse, status_code=201)
async def create_novel(
    body: NovelCreateRequest,
    storage: StorageService = Depends(get_storage),
    db: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> NovelCreateResponse:
```

**Validation:**
```python
from novelai.storage.validators import validate_storage_identifier
try:
    novel_id = validate_storage_identifier(body.novel_id.strip(), "novel_id")
except ValueError as exc:
    raise HTTPException(status_code=422, detail=str(exc)) from exc
```

**Conflict check:**
```python
existing_meta = storage.load_metadata(novel_id)
existing_db = db.query(Novel).filter_by(slug=novel_id).one_or_none()
if existing_meta is not None or existing_db is not None:
    raise HTTPException(status_code=409, detail="Novel already exists")
```

**Create storage record:**
```python
minimal_meta = {
    "title": body.title.strip(),
    "source_url": body.source_url,
    "source_key": body.source_key,
    "language": body.language,
    "origin_type": "url" if body.source_url else "library",
    "chapters": [],
}
storage.save_metadata(novel_id, minimal_meta)
```

**Create DB row:**
```python
novel = CatalogService(storage=storage, session=db).get_or_create_novel(
    novel_id, minimal_meta
)
db.flush()
```

**Return response:**
```python
return NovelCreateResponse(
    novel_id=novel_id,
    title=novel.title or body.title,
    source_url=body.source_url,
    source_key=body.source_key,
    language=novel.language,
    created_at=novel.created_at.isoformat(),
    db_id=novel.id,
)
```

### 2. Post-Scrape DB Reconciliation in `OperationsService`

In `scrape_novel`, after the `await self.orchestrator.scrape_metadata(...)` call succeeds:

```python
try:
    from novelai.services.catalog_service import CatalogService
    from novelai.db.engine import session_scope
    with session_scope() as session:
        CatalogService(storage=self.storage, session=session).reconcile_catalog_projection(novel_id)
except Exception as exc:
    logger.warning(
        "Post-scrape catalog projection reconciliation failed for %s: %s",
        novel_id, exc.__class__.__name__,
    )
```

Apply the same pattern to `preliminary_crawl_novel` after its metadata write.

Note: `safely_refresh_catalog_projection_after_storage_write` already does this for crawler-layer writes via `save_metadata`. The OperationsService layer sits one level above and doesn't currently call it. The new code adds the same best-effort pattern at the service level, creating a second reconciliation path that is harmless (idempotent) when both fire.

### 3. Integration Test Design

`test_novel_lifecycle_integration.py` uses pytest with:
- `tmp_path` fixture for real filesystem storage
- SQLite in-memory DB (same pattern as other integration tests)
- FastAPI test client
- No real HTTP to source sites

**`test_create_to_public_read_lifecycle`:**

```python
@pytest.mark.integration
def test_create_to_public_read_lifecycle(tmp_path, test_client, db_session, storage):
    novel_id = "test-novel-001"
    chapter_id = "ch001"

    # Step 1: create novel
    resp = test_client.post("/api/admin/novels", json={
        "novel_id": novel_id, "title": "Test Novel", "source_url": "https://example.com"
    }, headers=owner_auth)
    assert resp.status_code == 201
    assert resp.json()["db_id"] > 0

    # Step 2: simulate scrape result
    storage.save_metadata(novel_id, {
        "title": "Test Novel",
        "chapters": [{"id": chapter_id, "num": 1, "title": "Chapter 1"}],
    })

    # Step 3: refresh projection
    resp = test_client.post(f"/{novel_id}/refresh-catalog-projection", headers=owner_auth)
    assert resp.status_code == 200

    # Step 4: simulate translation
    storage.save_translated_chapter(novel_id, chapter_id, "Translated text here.")

    # Step 5: refresh again
    resp = test_client.post(f"/{novel_id}/refresh-catalog-projection", headers=owner_auth)
    assert resp.json()["after"]["translated_count"] == 1

    # Step 6: publish
    test_client.post(f"/{novel_id}/publish", headers=owner_auth)

    # Step 7: public catalog
    resp = test_client.get("/api/public/catalog")
    slugs = [n["slug"] for n in resp.json()["novels"]]
    assert any(novel_id in s for s in slugs)

    # Step 8: public chapter read
    resp = test_client.get(f"/api/public/novels/{novel_id}/chapters/{chapter_id}")
    assert resp.status_code == 200
    assert "Translated text here." in resp.json()["text"]
```

**Additional tests:**
- `test_create_conflict_returns_409`
- `test_create_invalid_novel_id_returns_422`
- `test_create_requires_owner_role` → unauthenticated → 403
- `test_created_novel_db_defaults` → `is_published=False`, `glossary_status="glossary_pending"`, correct `language`
- `test_translate_without_novel_returns_404` → call translate on non-existent novel → 404 with `novel_id` in detail

## Migration and Backward Compatibility

- New endpoint is additive. No existing callers break.
- Post-scrape reconciliation is best-effort and idempotent. Existing callers who manually call `refresh-catalog-projection` see the same final state.
- `Novel` row already supports all needed fields without migration.

## Acceptance Criteria

1. `POST /api/admin/novels` with a valid `novel_id` and `title` returns HTTP 201 with `db_id` populated.
2. A second call with the same `novel_id` returns HTTP 409.
3. An invalid `novel_id` returns HTTP 422.
4. An unauthenticated call returns HTTP 403.
5. After `POST /api/admin/novels`, the `Novel` DB row exists with `is_published=False`, `glossary_status="glossary_pending"`, and the supplied language.
6. After a scrape, the DB row is automatically created/updated without requiring a manual `refresh-catalog-projection` call.
7. The full lifecycle integration test passes: create → metadata → chapter → publish → public catalog → public chapter read.
