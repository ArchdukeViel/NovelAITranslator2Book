# Design: Public Reader Glossary Annotations

## Overview

This design adds optional glossary annotations to the public reader. The backend selects public-safe approved glossary entries, matches them against the translated chapter text, and returns compact annotation metadata. The frontend renders highlights/tooltips without changing the underlying translated text.

The design is additive and privacy-conscious. It does not expose glossary diagnostics, editor QA metadata, prompt details, or unpublished glossary entries.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| Public reader router, such as `backend/src/novelai/api/routers/public.py` | Include optional `glossary_annotations` in chapter response |
| Glossary service/model access layer | Add public-safe glossary selection helper |
| New annotation helper/service | Match public glossary terms against translated chapter text/reader blocks |
| Settings module | Add global enable/disable and max annotation limits |
| Public reader frontend | Add optional annotation rendering and toggle |
| Public reader tests | Add backend and frontend annotation tests |

### Files Not Touched

- Translation prompt builder.
- Glossary admin review rules.
- Editor QA.
- Translation storage text content.
- Public reader availability policy.

## Data Contract

Public chapter response adds:

```json
{
  "glossary_annotations": [
    {
      "term_id": "term_123",
      "source_term": "魔王",
      "display_term": "Demon King",
      "translation": "Demon King",
      "reading": "maou",
      "term_type": "title",
      "short_definition": "A title used for the ruler of demons.",
      "aliases": ["demon king"],
      "matches": [
        {
          "surface": "Demon King",
          "block_index": 3,
          "start": 18,
          "end": 28
        }
      ]
    }
  ]
}
```

Field rules:

- `term_id` is required.
- `display_term` or `translation` is required.
- `matches` is required and may be empty only if the API is returning a glossary sidebar rather than inline annotations; initial implementation should return only matched terms.
- `short_definition` is optional and must be public-safe.
- `aliases` are optional and must be public-safe.
- `matches.start` and `matches.end` are offsets in the block text when block-level matching is used.

## Public-Safe Glossary Selection

Add helper:

```python
def list_public_glossary_terms(novel_id: str) -> list[PublicGlossaryTerm]:
    ...
```

Selection rules:

- Include approved entries only.
- Exclude candidate/pending/rejected/internal entries.
- Include only terms with public visibility enabled, if such a field exists.
- If no public visibility field exists, use a conservative config:
  - global setting must allow annotations,
  - entry must be approved,
  - entry must not be marked internal/admin-only,
  - optional per-novel setting may enable exposure.

Recommended new fields only if current glossary schema supports migration:

```text
public_visible: bool
public_definition: str | null
```

If avoiding DB migration, use existing metadata fields/tags where available and document the conservative fallback.

## Matching Service

Add:

```python
class PublicGlossaryAnnotationService:
    def build_annotations(
        self,
        *,
        novel_id: str,
        chapter_id: str,
        translated_text: str | None,
        reader_blocks: list[dict[str, Any]],
        active_version_id: str | None,
    ) -> list[dict[str, Any]]:
        ...
```

Matching inputs:

- translated chapter text,
- reader blocks if available,
- public glossary terms.

Matching behavior:

- Prefer block-level matching to make frontend rendering easier.
- Match approved translations/display terms.
- Match public-safe aliases.
- Use case-insensitive matching for Latin-script terms.
- Use word boundaries for Latin-script terms to avoid substring false positives.
- Sort longer terms first to reduce overlap.
- Drop overlapping matches, keeping the longest match or earliest match.
- Bound maximum terms and matches.

Suggested limits:

```python
PUBLIC_READER_GLOSSARY_ANNOTATIONS_ENABLED = True
PUBLIC_READER_GLOSSARY_MAX_TERMS = 100
PUBLIC_READER_GLOSSARY_MAX_MATCHES_PER_TERM = 20
PUBLIC_READER_GLOSSARY_MAX_TOTAL_MATCHES = 300
```

## Backend Integration

In public `get_chapter` response:

1. Load translated chapter as today.
2. Build `reader_blocks` as today.
3. If annotations are enabled globally and for the novel, call annotation service.
4. Return `glossary_annotations`.

Pseudo-code:

```python
annotations = []
if _public_glossary_annotations_enabled(meta):
    annotations = annotation_service.build_annotations(
        novel_id=novel_id,
        chapter_id=chapter_id,
        translated_text=translated.get("text"),
        reader_blocks=reader_blocks,
        active_version_id=translated.get("version_id"),
    )

return {
    ...existing_response,
    "glossary_annotations": annotations,
}
```

For unavailable chapter shell responses, return `glossary_annotations: []`.

## Cache Strategy

Optional cache key:

```text
public-glossary-annotations:{novel_id}:{chapter_id}:{version_id}:{glossary_revision}
```

If not implementing cache initially, keep matching bounded and deterministic. The design should allow caching later without changing API shape.

## Frontend Rendering

Implement annotation rendering in the public reader component.

Rendering strategy:

- Render from `reader_blocks` when available.
- For each text block, apply non-overlapping ranges from annotation matches.
- Wrap matched text in a semantic element such as `button`, `span`, or `mark` with accessible tooltip/popover behavior.
- Preserve original text and paragraph structure.
- Do not mutate stored text.

Accessible interaction:

- Hover/focus shows tooltip on desktop.
- Tap opens popover/sheet on mobile.
- Keyboard focus opens tooltip/popover.
- Escape or outside click closes popover.

Toggle:

- Add reader control: "Glossary notes" on/off.
- Store preference in local storage if existing pattern permits.
- If disabled, render plain text.

## Security and Privacy

Do not expose:

- glossary review notes,
- status history,
- rejected terms,
- prompt diagnostics,
- editor QA,
- confidence scores unless public-safe,
- internal IDs beyond stable non-sensitive term IDs.

Public glossary selection must follow the same novel/chapter publication checks as the public chapter endpoint.

## Migration and Backward Compatibility

- Public chapter response fields are additive.
- Clients ignoring `glossary_annotations` behave as before.
- If no public-safe glossary entries exist, return an empty list.
- Existing glossary schema can be used with conservative filtering.
- A DB migration for `public_visible` and `public_definition` is optional; if added, include migration/backfill defaults to `false`.

## Test Design

Backend tests:

- approved public term is returned,
- pending/rejected/internal term is not returned,
- matching finds display term in reader block,
- matching avoids substring false positives,
- overlapping matches are resolved deterministically,
- disabled setting returns empty annotations,
- public reader response excludes diagnostics,
- chapter shell response returns empty annotations.

Frontend tests:

- annotations render without changing text,
- tooltip/popover shows public definition,
- toggle hides annotations,
- keyboard focus works,
- mobile layout does not overlap or clip.

## Acceptance Criteria

1. Public chapter response includes `glossary_annotations` when enabled.
2. Only approved public-safe glossary entries are exposed.
3. Matching finds translated terms and avoids obvious false positives.
4. Reader rendering preserves original text and paragraph structure.
5. Reader has a show/hide annotation control.
6. Public APIs do not expose admin diagnostics or unpublished glossary data.
7. Feature is bounded for response size and matching cost.
8. Existing public reader behavior remains compatible when annotations are ignored or disabled.
9. Focused backend and frontend tests pass.

