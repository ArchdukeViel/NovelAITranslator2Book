# Design Document

## Glossary-First Onboarding

---

## Overview

This feature gates novel translation behind a glossary readiness check.
Every novel crawled or imported goes through a structured glossary bootstrapping
step immediately after metadata is saved. Three fields are added to the `novels`
table: `glossary_status` (VARCHAR 32, default `glossary_pending`),
`glossary_revision` (INTEGER, default 0).

The translation endpoint gains a `skip_glossary_gate` flag and a pre-flight
check that blocks jobs when the novel is `glossary_pending`. The
`TranslateStage` records prompt-audit metadata alongside each chunk output.
`GlossaryRepository` increments `glossary_revision` whenever approved entries
change. The admin UI gains a three-action onboarding widget and a readiness
badge on the novel detail page.

No existing functionality is removed. All changes are additive.

---

## Architecture

The feature touches four layers; each change respects the declared dependency
direction `api → services → domain → storage/providers/sources/export`.

```
┌───────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                               │
│  - Novel-add flow: three-action widget (Review / Approve / Skip)  │
│  - Novel-detail page: ReadinessBadge component                    │
│  - Calls existing /api/novels/* endpoints (no new pages)          │
└─────────────────────────┬─────────────────────────────────────────┘
                          │  HTTP (existing API client)
┌─────────────────────────▼─────────────────────────────────────────┐
│  API layer (FastAPI routers)                                       │
│  - operations.py: TranslateRequest gains skip_glossary_gate field  │
│  - operations.py: translate endpoint passes flag into service      │
│  - admin_glossary.py: new PATCH /novels/{id}/glossary-status       │
│  - admin_novels.py: novel detail response gains three new fields   │
└─────────────────────────┬─────────────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────────────┐
│  Services layer                                                    │
│  - novel_orchestration_service.py: wires bootstrap step in        │
│  - orchestration/crawler.py: bootstrap hook after metadata save   │
│  - orchestration/translation.py: _preflight_translation gains     │
│    glossary gate check                                             │
│  - glossary_repository.py: revision increment on approved changes  │
│  - glossary_status_service.py (new): handles status transitions   │
│    and NovelGlossaryDecisionEvent writes                           │
└─────────────────────────┬─────────────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────────────┐
│  Domain / DB models                                                │
│  - db/models/novel.py: two new mapped columns                     │
│  - db/models/novel.py: validator on glossary_status writes        │
│  - TranslateStage: writes glossary audit metadata per chunk        │
└─────────────────────────┬─────────────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────────────┐
│  Database                                                          │
│  - New Alembic migration: adds glossary_status, glossary_revision  │
│    columns to novels; backfills defaults                           │
└───────────────────────────────────────────────────────────────────┘
```

### Data flow: novel add

```
POST /preliminary-crawl
  → OperationsService.preliminary_crawl_novel
      → scrape_metadata (crawler.py)
          → [metadata saved, catalog projection refreshed]
          → bootstrap_glossary_if_needed (new helper in crawler.py)
              → NovelOrchestrationService.extract_glossary_terms
              → GlossaryRepository.save_candidates
              → db: glossary_status = glossary_pending   (if not already ready)
  → return: {..., glossary_status, glossary_pending_count, bootstrap_candidate_count}
```

### Data flow: translate request

```
POST /{novel_id}/translate
  → _preflight_translation (translation.py)
      → reads novels.glossary_status via DB session
      → IF status == glossary_pending AND skip_glossary_gate == False:
            → raise PreflightIssue(code="glossary_gate_pending", ...)
      → proceeds with existing checks
```

### Data flow: glossary entry approval (revision increment)

```
GlossaryRepository.change_glossary_entry_status(status="approved")
  → existing logic
  → [NEW] _increment_glossary_revision(novel_id)   ← within same transaction
  → db flush
```

---

## Components and Interfaces

### 1. `Novel` ORM model (`db/models/novel.py`)

Two new mapped columns are added after the existing `is_published` column:

```python
GLOSSARY_STATUS_VALUES = frozenset({
    "glossary_pending",
    "glossary_ready",
    "glossary_skipped",
})

glossary_status: Mapped[str] = mapped_column(
    String(32), nullable=False, default="glossary_pending"
)
glossary_revision: Mapped[int] = mapped_column(
    Integer, nullable=False, default=0
)
```

A `@validates("glossary_status")` decorator raises `ValueError` for any value
outside `GLOSSARY_STATUS_VALUES`. This is the single enforcement point — the
validator lives on the ORM model so every write path (direct assignment,
`update()`, etc.) is covered.

### 2. Alembic migration

New file: `backend/alembic/versions/<hash>_add_glossary_status_fields.py`

```python
down_revision = "9f3b2c1d0e7a"  # after glossary tables

def upgrade():
    op.add_column("novels", sa.Column(
        "glossary_status", sa.String(32),
        nullable=False, server_default="glossary_pending"
    ))
    op.add_column("novels", sa.Column(
        "glossary_revision", sa.Integer(),
        nullable=False, server_default="0"
    ))
    op.create_index(
        "ix_novels_glossary_status", "novels", ["glossary_status"]
    )

def downgrade():
    op.drop_index("ix_novels_glossary_status", "novels")
    op.drop_column("novels", "glossary_revision")
    op.drop_column("novels", "glossary_status")
```

### 3. Catalog projection (`catalog_service.py`)

`CATALOG_PROJECTION_FIELDS` gains `"glossary_status"` and
`"glossary_revision"`. `recompute_catalog_projection` reads these from the
`Novel` ORM row; because they are DB columns (not file-storage fields), they
are already present on the row after the migration and no additional storage
read is required.

### 4. Glossary bootstrap hook (`orchestration/crawler.py`)

A new async helper is added at module level:

```python
async def bootstrap_glossary_if_needed(
    self: Any,
    novel_id: str,
    *,
    session: Session,
) -> dict[str, Any]:
    """Run glossary extraction after metadata is saved.

    Called by scrape_metadata immediately before return.
    Non-fatal: exceptions are logged and swallowed.
    """
```

Logic:
1. Load `Novel` from DB; return early if `glossary_status == "glossary_ready"`.
2. Call `self.extract_glossary_terms(novel_id=novel_id, ...)`.
3. If at least one candidate is returned: persist via `GlossaryRepository`,
   set `novel.glossary_status = "glossary_pending"`, flush.
4. If zero candidates: log warning, leave status unchanged.
5. Any exception: log error, swallow, return empty result.

`scrape_metadata` calls this helper after `safely_refresh_catalog_projection_after_storage_write`, passing the existing scoped session (or opening one if needed).

**Design decision**: the bootstrap is a best-effort step. The calling
`scrape_metadata` function already swallows metadata-translation errors in the
same pattern; this follows the same non-fatal idiom. If the LLM is unavailable,
the novel is still added with `glossary_pending` status and the operator can
trigger extraction manually from the glossary management section.

### 5. Translation guard (`orchestration/translation.py`)

`_preflight_translation` gains a new check inserted after the existing
`pending_terms` check:

```python
# --- Glossary gate ---
if not skip_glossary_gate:
    with session_scope() as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
    if novel is not None and novel.glossary_status == "glossary_pending":
        pending_count = _count_pending_glossary_entries(novel_id)
        review_path = f"/admin/novels/{novel_id}/glossary"
        issues.append(
            PreflightIssue(
                code="glossary_gate_pending",
                reason="Glossary review required before translation.",
                details={
                    "glossary_status": "glossary_pending",
                    "glossary_pending_count": pending_count,
                    "glossary_review_url": review_path,
                },
            )
        )
```

`PreflightIssue` already exists in `orchestration/common.py`. Its `details`
field is added if not already present (it currently only has `code` and
`reason`); the router maps issues to HTTP 422.

`skip_glossary_gate` is threaded through from `TranslateRequest` →
`OperationsService.translate_novel` → `orchestrator.translate_chapters` →
`_preflight_translation`. The existing call chain passes keyword arguments, so
adding `skip_glossary_gate: bool = False` at each level is a non-breaking
extension.

### 6. `TranslateRequest` schema (`api/routers/operations.py`)

```python
class TranslateRequest(BaseModel):
    ...
    skip_glossary_gate: bool = False   # new optional field
```

The router passes the new field to `service.translate_novel(...)` which passes
it to `orchestrator.translate_chapters(...)`.

### 7. `GlossaryStatusService` (new, `services/glossary_status_service.py`)

Handles the status-transition endpoint logic. Kept separate from
`GlossaryRepository` because it touches both the `Novel` row and
`NovelGlossaryDecisionEvent` — a use-case layer concern, not a pure data-access
concern.

```python
class GlossaryStatusService:
    def __init__(self, session: Session) -> None: ...

    def transition_status(
        self,
        novel_id: str,
        *,
        target_status: str,
        actor_user_id: int | None,
    ) -> Novel:
        """Set glossary_status; increment revision if target is glossary_ready.
        Writes NovelGlossaryDecisionEvent. Raises LookupError if novel not found.
        """
```

Valid `target_status` values: `glossary_pending`, `glossary_ready`,
`glossary_skipped`. Incrementing `glossary_revision` only when transitioning to
`glossary_ready`. The decision event uses the existing `NovelGlossaryDecisionEvent`
model and `GlossaryRepository.create_decision_event`.

### 8. Status-transition endpoint (`api/routers/admin_glossary.py`)

```
PATCH /novels/{novel_id}/glossary-status
Authorization: owner role required
Body: { "target_status": "glossary_ready" | "glossary_skipped" | "glossary_pending" }
Response 200: { novel_id, glossary_status, glossary_revision }
Response 403: non-owner
Response 404: novel not found
Response 422: invalid target_status value
```

**Design decision**: placing this in `admin_glossary.py` rather than a new
router keeps all glossary management operations co-located and avoids a new
router file and registration.

### 9. `GlossaryRepository` revision increment (`services/glossary_repository.py`)

A private helper is added:

```python
def _increment_glossary_revision(self, novel_id: int) -> None:
    """Increment novels.glossary_revision within the current transaction.
    Raises if the novel row is not found (propagates as DB error).
    """
    from novelai.db.models.novel import Novel
    novel = self.db.get(Novel, novel_id)
    if novel is None:
        raise LookupError(f"Novel {novel_id} not found during revision increment")
    novel.glossary_revision += 1
    self.db.flush()
```

This is called from:
- `change_glossary_entry_status` when `status == "approved"` or when moving an
  approved entry to `"deprecated"` / `"rejected"`.
- `update_glossary_entry` when the entry's current status is `"approved"`.

The helper runs within the caller's transaction — no new `session_scope()` is
opened. If the flush fails, the exception propagates up to the caller, rolling
back the entire transaction (SQLAlchemy's default session behavior).

### 10. `TranslateStage` prompt audit (`translation/pipeline/stages/translate.py`)

In `_save_chunk_output`, two new keys are added to the output record:

```python
"glossary_revision": context.metadata.get("glossary_revision", 0),
"glossary_injected_term_count": context.metadata.get("glossary_injected_term_count", 0),
```

`glossary_revision` is populated by reading `novels.glossary_revision` at the
start of `translate_chapters` (in `orchestration/translation.py`) and injecting
it into the pipeline context metadata under `"glossary_revision"`. Similarly,
`glossary_injected_term_count` is set by counting the entries in the resolved
`PromptGlossaryBlock.included_terms` tuple after `GlossaryPromptInjectionService.build_for_chapter`
runs, before the chunk loop begins.

**Design decision**: reading revision at job start (not per-chunk) is
intentional. All chunks in one translation job should carry the same revision
stamp so the audit trail is coherent per run.

### 11. Novel detail API enrichment

The existing novel-detail endpoint (admin novels router) is updated to include:

```json
{
  "glossary_status": "glossary_pending",
  "glossary_revision": 0,
  "glossary_pending_count": 7
}
```

`glossary_pending_count` is computed by counting `novel_glossary_entries` rows
with `status = "candidate"` or `"recommended"` for the novel. This query is
cheap (indexed by `novel_id + status`).

### 12. Frontend components

#### `ReadinessBadge` (`frontend/src/components/admin/ReadinessBadge.tsx`)

Props: `{ glossaryStatus, glossaryRevision, glossaryPendingCount, novelId }`.

| Status             | Background | Content                                     |
|--------------------|------------|---------------------------------------------|
| `glossary_pending` | amber-500  | "Glossary pending (N terms)" + review link  |
| `glossary_ready`   | green-500  | "Glossary ready (rev. N)"                   |
| `glossary_skipped` | gray-400   | "Glossary skipped"                          |

The review link uses Next.js `<Link>` for SPA navigation.

#### Three-action widget (`frontend/src/components/admin/GlossaryOnboardingActions.tsx`)

Displayed in the novel-add flow after preliminary crawl completes, when
`bootstrap_candidate_count > 0`. Three buttons:

1. **Review glossary** — navigate to `/admin/novels/{id}/glossary` (SPA link)
2. **Approve all & set ready** — call
   `PATCH /api/novels/{id}/glossary-status` with `glossary_ready`, then
   `POST /api/novels/{id}/glossary/batch-approve`
3. **Skip for now** — call
   `PATCH /api/novels/{id}/glossary-status` with `glossary_skipped`

When `bootstrap_candidate_count == 0`, only the **Skip for now** button is shown
with a notice: "No glossary terms were detected in available source text."

---

## Data Models

### `novels` table additions

| Column             | Type          | Nullable | Default           | Index                   |
|--------------------|---------------|----------|-------------------|-------------------------|
| `glossary_status`  | `VARCHAR(32)` | NOT NULL | `glossary_pending`| `ix_novels_glossary_status` |
| `glossary_revision`| `INTEGER`     | NOT NULL | `0`               | —                       |

Valid `glossary_status` values are enforced at the ORM layer via `@validates`.

### Translation output record additions

The dict passed to `storage.save_translation_output(...)` gains two keys:

| Key                          | Type  | Source                                              |
|------------------------------|-------|-----------------------------------------------------|
| `glossary_revision`          | `int` | `context.metadata["glossary_revision"]` (from DB)  |
| `glossary_injected_term_count` | `int` | `len(glossary_block.included_terms)`              |

These are persisted alongside the existing output record in file-backed storage.
They survive re-translation because each call to `save_translation_output`
writes a new versioned record (existing behavior).

### `GlossaryStatusTransitionRequest` (Pydantic)

```python
class GlossaryStatusTransitionRequest(BaseModel):
    target_status: Literal["glossary_pending", "glossary_ready", "glossary_skipped"]
```

### `GlossaryStatusTransitionResponse` (Pydantic)

```python
class GlossaryStatusTransitionResponse(BaseModel):
    novel_id: str
    glossary_status: str
    glossary_revision: int
```

### `NovelDetailResponse` additions (admin)

```python
glossary_status: str
glossary_revision: int
glossary_pending_count: int
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all
valid executions of a system — essentially, a formal statement about what the
system should do. Properties serve as the bridge between human-readable
specifications and machine-verifiable correctness guarantees.*

### Property 1: Glossary status validation rejects all invalid values

*For any* string value that is not one of `{"glossary_pending",
"glossary_ready", "glossary_skipped"}`, assigning it to
`Novel.glossary_status` should raise `ValueError`; all three valid values
should be accepted without error.

**Validates: Requirements 1.3, 1.4**

---

### Property 2: Catalog projection always carries glossary fields

*For any* novel with any `glossary_status` and any `glossary_revision`,
the dict returned by `recompute_catalog_projection` must contain both
`"glossary_status"` and `"glossary_revision"` with values equal to the
novel's current DB column values.

**Validates: Requirements 1.5**

---

### Property 3: Bootstrap exception isolation

*For any* exception type raised by `extract_glossary_terms` during the
bootstrap step, `scrape_metadata` should complete successfully, the novel's
`glossary_status` should remain at its value before the exception, and no
exception should propagate to the caller.

**Validates: Requirements 2.4**

---

### Property 4: Bootstrap invocation gate

*For any* novel with `glossary_status` in `{"glossary_pending",
"glossary_skipped"}`, completing `scrape_metadata` should trigger the
bootstrap step. *For any* novel with `glossary_status == "glossary_ready"`,
the bootstrap step should not be invoked.

**Validates: Requirements 2.1, 2.5**

---

### Property 5: Bootstrap produces pending status

*For any* non-empty list of extracted candidate terms returned by the
bootstrap step, the resulting `novels.glossary_status` should be
`"glossary_pending"` and the candidates should be queryable via
`GlossaryRepository.list_glossary_entries_for_novel`.

**Validates: Requirements 2.2**

---

### Property 6: Translation guard blocks pending novels

*For any* translate request where `skip_glossary_gate` is `False` and the
novel's `glossary_status` is `"glossary_pending"`, the preflight check should
return a `PreflightIssue` with code `"glossary_gate_pending"` and a `details`
dict containing `"glossary_status"`, `"glossary_pending_count"`, and
`"glossary_review_url"`.

**Validates: Requirements 3.1, 3.5**

---

### Property 7: Translation guard respects skip flag and non-pending statuses

*For any* translate request where `skip_glossary_gate` is `True`, or where
the novel's `glossary_status` is `"glossary_ready"` or `"glossary_skipped"`,
the glossary gate should not add any `PreflightIssue` with code
`"glossary_gate_pending"`.

**Validates: Requirements 3.2, 3.3**

---

### Property 8: Glossary-ready transition always increments revision

*For any* novel with current `glossary_revision` value N, calling
`GlossaryStatusService.transition_status` with `target_status="glossary_ready"`
should set `glossary_revision` to exactly N + 1.

**Validates: Requirements 4.2, 6.2**

---

### Property 9: Glossary-skipped transition never changes revision

*For any* novel with current `glossary_revision` value N, calling
`GlossaryStatusService.transition_status` with
`target_status="glossary_skipped"` should leave `glossary_revision` at N.

**Validates: Requirements 6.3**

---

### Property 10: Every successful status transition writes a decision event

*For any* successful call to `GlossaryStatusService.transition_status`,
a `NovelGlossaryDecisionEvent` record should be persisted with the correct
actor user ID, `old_value_json` capturing the previous status, `new_value_json`
capturing the new status, and a valid ISO 8601 `created_at` timestamp.

**Validates: Requirements 6.6**

---

### Property 11: Novel detail API always returns glossary fields

*For any* novel with any `glossary_status`, any `glossary_revision`, and any
number of pending glossary entries, the admin novel detail API response should
include `glossary_status`, `glossary_revision`, and `glossary_pending_count`
with values consistent with the DB state at the time of the request.

**Validates: Requirements 5.5**

---

### Property 12: TranslateStage audit metadata matches DB state at job start

*For any* novel with DB `glossary_revision` value R and N approved glossary
entries at the time translation starts, every chunk output record written by
`TranslateStage` should contain `glossary_revision == R` and
`glossary_injected_term_count == N_injected` where `N_injected` is the count
of terms included in the `PromptGlossaryBlock` (≤ N due to truncation limits).

**Validates: Requirements 7.1, 7.2, 7.3, 7.5**

---

### Property 13: Approved entry changes increment glossary_revision

*For any* novel with current `glossary_revision` N and any glossary entry
that is in `"approved"` status, performing any of the following operations via
`GlossaryRepository` — approving a candidate, updating an approved entry's
fields, deprecating an approved entry — should result in `glossary_revision`
being N + 1, within the same transaction.

**Validates: Requirements 8.1, 8.2, 8.3**

---

### Property 14: Non-approved entry changes do not increment glossary_revision

*For any* novel with current `glossary_revision` N and any glossary entry
whose status is `"candidate"` or `"recommended"`, updating that entry's fields
without transitioning it to `"approved"` should leave `glossary_revision`
unchanged at N.

**Validates: Requirements 8.4**

---

## Error Handling

### Bootstrap failures (non-fatal)

`bootstrap_glossary_if_needed` catches all exceptions, logs them at `ERROR`
level with novel ID and exception details, and returns an empty result dict.
The novel is left at `glossary_pending` status. The operator can manually
trigger extraction from the glossary management section.

Specific error shapes to log:
- LLM provider unavailable: log at `WARNING` (expected in dev environments)
- No source chapters available: log at `WARNING`, include count of available
  chapters
- All other exceptions: log at `ERROR` with full traceback

### Translation guard rejections (HTTP 422)

When `_preflight_translation` collects a `glossary_gate_pending` issue, the
existing router logic raises `HTTPException(422)`. The response body is the
standard `{"detail": [...issues...]}` shape. Each issue includes `code`,
`reason`, and `details` (see Component 5 above).

The frontend reads `error.detail[].code == "glossary_gate_pending"` to display
a targeted message with the review link.

### Status transition errors

- `novel_id` not found: `GlossaryStatusService` raises `LookupError` →
  router catches and raises `HTTPException(404)`.
- Invalid `target_status`: Pydantic `Literal` validation rejects at
  deserialization time → FastAPI returns HTTP 422 automatically.
- DB failure during revision increment: SQLAlchemy exception propagates,
  session is rolled back by the `session_scope` context manager → router
  returns HTTP 500. The `GlossaryRepository._increment_glossary_revision`
  raises so the entry status change is also rolled back (atomicity).

### TranslateStage audit metadata missing

If `context.metadata.get("glossary_revision")` is absent (e.g., the novel was
translated by an older code path), `_save_chunk_output` defaults to `0` for
both audit fields. This is a safe degradation; the audit fields are
informational, not required for translation correctness.

---

## Testing Strategy

### Unit tests

- `db/models/novel.py` — `@validates` raises `ValueError` for invalid statuses,
  accepts valid ones. Test with representative valid and invalid values.
- `orchestration/crawler.py` — bootstrap helper: zero candidates (warning
  logged, status unchanged), non-empty candidates (status set, repo called),
  exception (swallowed, status unchanged).
- `orchestration/translation.py` — preflight: pending status without skip
  returns `glossary_gate_pending` issue; pending with skip returns no such
  issue; ready and skipped return no such issue.
- `services/glossary_status_service.py` — `transition_status`: glossary_ready
  increments revision, glossary_skipped does not, decision event is written,
  LookupError on missing novel.
- `services/glossary_repository.py` — `_increment_glossary_revision` increments
  by one, stays within transaction; `change_glossary_entry_status` to approved
  calls increment; candidate update does not call increment.
- `translation/pipeline/stages/translate.py` — `_save_chunk_output` includes
  `glossary_revision` and `glossary_injected_term_count` from context metadata;
  defaults to 0 when absent.
- `api/routers/operations.py` — `TranslateRequest` deserializes with
  `skip_glossary_gate` defaulting to `False`.

Unit tests avoid I/O: DB interactions are mocked via `unittest.mock` or
SQLite in-memory sessions.

### Property-based tests

Library: **Hypothesis** (already a Python project; `pip install hypothesis`).

Each property-based test runs a minimum of 100 examples.

```python
# Example structure for Property 1
from hypothesis import given, settings
from hypothesis.strategies import text, sampled_from

@given(invalid_status=text().filter(
    lambda s: s not in {"glossary_pending", "glossary_ready", "glossary_skipped"}
))
@settings(max_examples=200)
def test_invalid_glossary_status_rejected(invalid_status):
    """Feature: glossary-first-onboarding, Property 1: glossary status validation rejects all invalid values"""
    novel = Novel(slug="test", title="Test", glossary_status="glossary_pending")
    with pytest.raises(ValueError):
        novel.glossary_status = invalid_status
```

Each property test is tagged with a comment in the format:
`Feature: glossary-first-onboarding, Property N: <property_text>`

Properties requiring DB state (Properties 2, 5, 8, 9, 10, 11, 13, 14) use
SQLite in-memory sessions via a `db_session` fixture.

Properties involving the translation guard (Properties 6, 7) mock
`session_scope` and `Novel` queries to isolate the preflight logic from real
DB connections.

Property 12 (TranslateStage audit) mocks `StorageService` and
`GlossaryPromptInjectionService` to inject controlled revision and term-count
values and asserts the saved output record matches.

### Integration tests

- Migration smoke test: apply migration on a test DB, assert both new columns
  exist with correct types and server defaults.
- End-to-end preflight: `preliminary_crawl_novel` on a mocked source returns
  metadata → bootstrap is called → novel has `glossary_pending` status.
- Translate attempt on a `glossary_pending` novel without skip flag: HTTP 422
  with `glossary_gate_pending` code.
- Translate attempt on a `glossary_pending` novel with `skip_glossary_gate=true`:
  proceeds past the gate (existing translation checks may still block for other
  reasons, but not the glossary gate).

### Frontend tests

- `ReadinessBadge` renders amber/green/grey for each status (snapshot test).
- `GlossaryOnboardingActions` renders three buttons when `bootstrap_candidate_count > 0`
  and one button when `bootstrap_candidate_count == 0` (example-based React
  Testing Library test).
- API client sends correct `skip_glossary_gate` field in translate request body.
