# Design: Glossary Auto-Population

## Overview

Add a post-translation term extraction step that identifies potential glossary candidates. Store suggestions as JSON files per novel. Expose an owner-only API for reviewing, accepting, and rejecting suggestions. Integration with existing `GlossaryService` for term addition.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/services/glossary/suggestion_extractor.py` | New — term extraction logic (frequency + LLM) |
| `backend/src/novelai/services/glossary/suggestion_service.py` | New — suggestion CRUD, storage, dedup |
| `backend/src/novelai/services/pipeline/stages/post_process.py` | Update — trigger term extraction after chapter save |
| `backend/src/novelai/api/routers/admin_glossary.py` | Update — add suggestion review endpoints |
| `backend/tests/test_glossary_suggestions.py` | New — suggestion system tests |

### Files Not Touched

- Existing glossary file format — no change
- GlossaryService.add_term — used as-is
- DB models — no change
- Storage layer — no change
- Frontend — no change

## Component Design

### 1. `SuggestionExtractor` (`services/glossary/suggestion_extractor.py`)

```python
import re
from collections import Counter
from typing import Optional

class SuggestionExtractor:
    def __init__(self, min_frequency: int = 3, ngram_range: tuple[int, int] = (2, 5)):
        self.min_frequency = min_frequency
        self.ngram_range = ngram_range

    def extract(self, source_text: str, translated_text: str) -> list[dict]:
        """Extract glossary suggestions from translated text."""
        suggestions = []

        # Strategy 1: Frequency-based on translated text
        freq_suggestions = self._frequency_extraction(translated_text)
        suggestions.extend(freq_suggestions)

        # Strategy 2: LLM-based on source text
        llm_suggestions = self._llm_extraction(source_text)
        suggestions.extend(llm_suggestions)

        return suggestions

    def _frequency_extraction(self, text: str) -> list[dict]:
        """Extract repeated n-grams as potential terms."""
        words = re.findall(r"\w+(?:'\w+)?", text.lower())
        suggestions = []
        for n in range(self.ngram_range[0], self.ngram_range[1] + 1):
            ngrams = zip(*[words[i:] for i in range(n)])
            ngram_counts = Counter(" ".join(ng) for ng in ngrams)
            for phrase, count in ngram_counts.items():
                if count >= self.min_frequency and len(phrase) > 2:
                    suggestions.append({
                        "term": phrase,
                        "frequency": count,
                        "source": "frequency",
                        "confidence": min(count / 10, 1.0),
                    })
        return suggestions

    async def _llm_extraction(self, source_text: str) -> list[dict]:
        """Use LLM to extract proper nouns and key terms from source text."""
        # Placeholder: calls a lightweight LLM with a structured extraction prompt
        # Returns list of {term, suggested_translation, confidence}
        try:
            prompt = (
                "Extract proper nouns (character names, place names, organization names) "
                "from the following text. Return a JSON list of {term, suggested_translation}.\n\n"
                f"{source_text[:3000]}"
            )
            # ... LLM call logic (reuses existing provider infrastructure) ...
            return []
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "LLM term extraction failed: %s", exc
            )
            return []
```

### 2. `SuggestionService` (`services/glossary/suggestion_service.py`)

```python
import json
from pathlib import Path
from datetime import datetime, timezone

SUGGESTIONS_FILE = "glossary_suggestions.json"

class GlossarySuggestion(BaseModel):
    id: str  # UUID
    term: str
    suggested_translation: str
    frequency: int
    source: str  # "frequency" or "llm"
    chapter_ids: list[str]
    confidence: float
    status: str  # "pending", "accepted", "rejected"
    rejection_reason: str | None = None
    created_at: str  # ISO timestamp

class GlossarySuggestionService:
    def __init__(self, storage_path: Path):
        self.suggestions_path = storage_path / "glossary" / SUGGESTIONS_FILE

    def _load(self) -> dict[str, GlossarySuggestion]:
        if not self.suggestions_path.exists():
            return {}
        with open(self.suggestions_path, "r") as f:
            data = json.load(f)
        return {k: GlossarySuggestion(**v) for k, v in data.items()}

    def _save(self, suggestions: dict[str, GlossarySuggestion]) -> None:
        self.suggestions_path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.model_dump() for k, v in suggestions.items()}
        with open(self.suggestions_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_suggestions(self, novel_id: str, extracted: list[dict]) -> int:
        """Add extracted suggestions, merging with existing."""
        existing = self._load()
        added = 0
        for item in extracted:
            term = item["term"]
            # Skip if already in active glossary (checked by caller)
            # Skip if previously rejected
            if term in existing and existing[term].status == "rejected":
                continue
            if term in existing and existing[term].status == "pending":
                # Merge: increment frequency, append chapter
                existing[term].frequency += item.get("frequency", 1)
                ch = item.get("chapter_id")
                if ch and ch not in existing[term].chapter_ids:
                    existing[term].chapter_ids.append(ch)
            else:
                suggestion = GlossarySuggestion(
                    id=str(uuid.uuid4()),
                    term=term,
                    suggested_translation=item.get("suggested_translation", term),
                    frequency=item.get("frequency", 1),
                    source=item.get("source", "frequency"),
                    chapter_ids=[item.get("chapter_id")] if item.get("chapter_id") else [],
                    confidence=item.get("confidence", 0.5),
                    status="pending",
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                existing[term] = suggestion
                added += 1
        self._save(existing)
        return added

    def list_suggestions(self, novel_id: str, status: str | None = None, source: str | None = None) -> list[GlossarySuggestion]:
        suggestions = list(self._load().values())
        if status:
            suggestions = [s for s in suggestions if s.status == status]
        if source:
            suggestions = [s for s in suggestions if s.source == source]
        return sorted(suggestions, key=lambda s: s.confidence, reverse=True)

    def accept(self, novel_id: str, suggestion_id: str, modified_translation: str | None = None) -> GlossarySuggestion:
        suggestions = self._load()
        for term, s in suggestions.items():
            if s.id == suggestion_id:
                s.status = "accepted"
                translation = modified_translation or s.suggested_translation
                # Add to active glossary via GlossaryService
                from novelai.services.glossary_service import GlossaryService
                GlossaryService().add_term(novel_id, term, translation)
                self._save(suggestions)
                return s
        raise ValueError(f"Suggestion not found: {suggestion_id}")

    def reject(self, novel_id: str, suggestion_id: str, reason: str | None = None) -> GlossarySuggestion:
        suggestions = self._load()
        for term, s in suggestions.items():
            if s.id == suggestion_id:
                s.status = "rejected"
                s.rejection_reason = reason
                self._save(suggestions)
                return s
        raise ValueError(f"Suggestion not found: {suggestion_id}")

    def accept_all(self, novel_id: str) -> int:
        count = 0
        for s in self.list_suggestions(novel_id, status="pending"):
            self.accept(novel_id, s.id)
            count += 1
        return count

    def reject_all(self, novel_id: str) -> int:
        count = 0
        for s in self.list_suggestions(novel_id, status="pending"):
            self.reject(novel_id, s.id)
            count += 1
        return count
```

### 3. Post-Processing Integration (`stages/post_process.py`)

After the translated chapter is saved:

```python
async def execute(self, context: PipelineContext, chapter_bundle: dict) -> dict:
    # ... existing post-processing and save logic ...

    # Trigger term extraction (best-effort)
    try:
        from novelai.services.glossary.suggestion_extractor import SuggestionExtractor
        from novelai.services.glossary.suggestion_service import GlossarySuggestionService
        from novelai.storage.service import get_storage_path

        storage_path = get_storage_path()
        extractor = SuggestionExtractor()
        suggestion_service = GlossarySuggestionService(storage_path / "novel_library" / "novel" / context.novel_id)

        extracted = extractor.extract(
            source_text=chapter_bundle.get("source_text", ""),
            translated_text=chapter_bundle.get("translated_text", ""),
        )
        if extracted:
            count = suggestion_service.add_suggestions(context.novel_id, extracted)
            context.logger.info("Extracted %d glossary suggestions for chapter %s", count, context.chapter_id)
    except Exception as exc:
        context.logger.warning("Term extraction failed for chapter %s: %s", context.chapter_id, exc)

    return chapter_bundle
```

### 4. Owner Review API Endpoints

All under `router = APIRouter(prefix="/api/admin/novels/{novel_id}/glossary", dependencies=[Depends(require_role("owner"))])`:

- `GET /suggestions` — list, filter by `status` and `source`
- `POST /suggestions/{suggestion_id}/accept` — body: `{"modified_translation": str | null}`
- `POST /suggestions/{suggestion_id}/reject` — body: `{"reason": str | null}`
- `POST /suggestions/accept-all`
- `POST /suggestions/reject-all`

## Migration and Backward Compatibility

- All new endpoints and logic are additive. No existing glossary functionality is changed.
- Existing glossary files remain unchanged.
- Extraction runs only on newly translated chapters. Existing translated chapters are not re-analyzed.
- The owner must explicitly accept suggestions; nothing is added to the glossary automatically.

## Acceptance Criteria

1. After a chapter is translated, suggestion candidates appear in `GET /api/admin/novels/{id}/glossary/suggestions`.
2. Accepting a suggestion adds the term to the novel's active glossary file.
3. Rejecting a suggestion sets its status to `rejected` and it does not reappear.
4. Duplicate suggestions for the same term are merged (frequency incremented).
5. Accept-all accepts all pending suggestions in one call.
6. The system handles extraction failure gracefully without blocking translation.
