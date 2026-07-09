# Design: Public Reader Glossary Annotations

## Overview

This design adds optional public-safe glossary annotations to the public reader.

The backend selects approved glossary entries that are safe for public display, matches them against the translated chapter text or reader blocks, and returns compact annotation metadata. The frontend renders highlights, tooltips, or popovers without changing stored translated text.

This feature is additive and privacy-conscious. It must not expose glossary diagnostics, editor QA metadata, prompt details, rejected terms, pending terms, internal glossary notes, provider metadata, or unpublished glossary entries.

This spec should be implemented after the core glossary, public reader availability, glossary diagnostics, and editor QA surfaces are stable.

## Goals

- Show useful public glossary notes in translated chapters.
- Expose only approved public-safe glossary entries.
- Match translated/display terms in reader text deterministically.
- Render annotations without mutating stored translation text.
- Let readers toggle glossary notes on or off.
- Keep annotation payloads bounded.
- Preserve public reader compatibility when annotations are disabled or ignored.
- Avoid exposing admin-only glossary, diagnostics, prompt, or QA metadata.

## Non-Goals

- Changing translated chapter text.
- Re-running translation.
- Replacing prompt-time glossary injection.
- Replacing editor QA.
- Exposing glossary diagnostics.
- Exposing glossary review state.
- Exposing pending, rejected, internal, or admin-only glossary entries.
- Adding public reader availability behavior.
- Changing active-version selection.
- Adding semantic/LLM-based annotation detection.
- Adding full glossary management to the public reader.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| Public reader router, such as `backend/src/novelai/api/routers/public.py` | Add optional `glossary_annotations` to public chapter response |
| Glossary service/repository layer | Add public-safe glossary selection helper |
| New annotation helper/service | Match public glossary terms against translated text or reader blocks |
| Settings/config module | Add global, per-novel, and limit settings where supported |
| Public reader frontend | Render optional highlights/tooltips/popovers and reader toggle |
| Public reader backend tests | Add annotation contract and privacy tests |
| Public reader frontend tests | Add rendering, toggle, and accessibility tests |

### Files Not Touched

- Translation prompt builder.
- Glossary prompt injection rules.
- Glossary admin review rules.
- Glossary diagnostics admin surfacing.
- Glossary-aware editor QA.
- Translation storage text content.
- Public reader availability policy.
- Active translation version selection.
- Scheduler/provider logic.

## Public API Contract

Public chapter response may add:

```json
{
  "glossary_annotations": [
    {
      "term_id": "pub_term_123",
      "display_term": "Demon King",
      "translation": "Demon King",
      "source_term": "魔王",
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

| Field | Rule |
|---|---|
| `term_id` | Required; must be stable and non-sensitive |
| `display_term` | Required unless `translation` is present |
| `translation` | Required unless `display_term` is present |
| `source_term` | Optional; include only when public-safe |
| `reading` | Optional; include only when public-safe |
| `term_type` | Optional; must use public-safe values |
| `short_definition` | Optional; must be public-safe |
| `aliases` | Optional; must be public-safe and bounded |
| `matches` | Required for inline annotation mode |
| `matches.surface` | Exact matched text from reader block |
| `matches.block_index` | Index into public reader block array |
| `matches.start` | Offset in block text |
| `matches.end` | Offset in block text |

Initial implementation should return only matched terms. A future glossary sidebar mode may allow terms with empty `matches`, but inline annotation mode should not.

For untranslated chapter shell responses, return:

```json
{
  "glossary_annotations": []
}
```

## API Enablement Strategy

Annotations should be optional.

Preferred first rollout:

```http
GET /public/novels/{novel_id}/chapters/{chapter_id}?include_glossary_annotations=true
```

Alternative if the existing public API prefers additive always-present fields:

```json
{
  "glossary_annotations": []
}
```

Rules:

- If annotations are globally disabled, return an empty list.
- If annotations are disabled for the novel, return an empty list.
- If the chapter has no translated text, return an empty list.
- If no public-safe glossary entries exist, return an empty list.
- Existing clients that ignore `glossary_annotations` must behave as before.

## Public-Safe Glossary Selection

Add a helper:

```python
def list_public_glossary_terms(novel_id: str) -> list[PublicGlossaryTerm]:
    ...
```

Selection rules:

- Include approved entries only.
- Exclude pending entries.
- Exclude candidate entries.
- Exclude rejected entries.
- Exclude disabled or archived entries.
- Exclude internal/admin-only entries.
- Include only entries with public visibility enabled when such a field exists.
- Respect novel publication and public reader access checks.
- Respect inherited/global glossary behavior only when the existing glossary repository already supports it.
- Do not expose glossary review notes, decision history, prompt metadata, diagnostics, or editor QA metadata.

Recommended fields if schema migration is acceptable:

```text
public_visible: bool
public_definition: str | null
public_display_term: str | null
```

Default migration behavior should be conservative:

```text
public_visible = false
```

If avoiding a DB migration, use existing metadata/tags only when there is already a clear public-safe marker. Do not default all approved terms to public-visible unless the project explicitly accepts that exposure.

## Public Glossary Term Shape

Internal service object:

```python
@dataclass(frozen=True)
class PublicGlossaryTerm:
    term_id: str
    display_term: str
    translation: str | None
    source_term: str | None
    reading: str | None
    term_type: str | None
    short_definition: str | None
    aliases: list[str]
    match_terms: list[str]
```

Rules:

- `term_id` should be an opaque public-safe ID.
- `match_terms` should include the approved translation/display term.
- `match_terms` may include public-safe aliases.
- `short_definition` should use a public-specific field when available.
- Internal notes must never be copied into `short_definition`.

## Annotation Service

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

The service should:

- Load public-safe glossary terms.
- Prefer reader block text for matching.
- Fall back to translated chapter text only if reader blocks are unavailable.
- Match approved translations, display terms, and public-safe aliases.
- Return compact annotations grouped by glossary term.
- Include only matched terms.
- Bound term count, match count per term, and total match count.
- Avoid mutating translated text.
- Avoid reading or exposing admin-only metadata.

## Matching Behavior

Matching must be deterministic.

Rules:

- Prefer block-level matching.
- Use case-insensitive matching for Latin-script terms.
- Use word boundaries for Latin-script terms to avoid substring false positives.
- Allow exact substring matching for non-Latin scripts where word boundaries are unreliable.
- Sort longer match terms before shorter terms.
- Resolve overlaps deterministically.
- Drop overlapping matches, keeping the longest match first.
- If length ties, keep the earliest match.
- If still tied, keep stable glossary term order.
- Bound total matches.
- Do not call an LLM.

Suggested limits:

```python
PUBLIC_READER_GLOSSARY_ANNOTATIONS_ENABLED = False
PUBLIC_READER_GLOSSARY_MAX_TERMS = 100
PUBLIC_READER_GLOSSARY_MAX_MATCHES_PER_TERM = 20
PUBLIC_READER_GLOSSARY_MAX_TOTAL_MATCHES = 300
PUBLIC_READER_GLOSSARY_MAX_ALIAS_COUNT = 10
PUBLIC_READER_GLOSSARY_MAX_DEFINITION_LENGTH = 240
```

Recommended first rollout default:

```python
PUBLIC_READER_GLOSSARY_ANNOTATIONS_ENABLED = False
```

Enable per deployment or per novel after public-safe glossary curation is ready.

## Backend Integration

Public chapter response flow:

1. Load chapter through existing public reader availability logic.
2. Select active translated version exactly as today.
3. Build `reader_blocks` exactly as today.
4. Check global and per-novel annotation settings.
5. Load public-safe glossary terms.
6. Build annotations from `reader_blocks`.
7. Add `glossary_annotations` to the response.
8. Return an empty list for unavailable chapter shells.

Pseudo-code:

```python
annotations: list[dict[str, Any]] = []

if public_glossary_annotations_enabled(novel_meta):
    annotations = annotation_service.build_annotations(
        novel_id=novel_id,
        chapter_id=chapter_id,
        translated_text=translated.get("text"),
        reader_blocks=reader_blocks,
        active_version_id=translated.get("version_id"),
    )

return {
    **existing_response,
    "glossary_annotations": annotations,
}
```

Rules:

- Do not change public reader availability behavior.
- Do not change active version selection.
- Do not change reader block generation.
- Do not mutate translated text.
- Do not expose annotations for unpublished or inaccessible novels.
- Do not expose annotations for chapters that are not publicly readable.

## Cache Strategy

Initial implementation may skip caching if matching is bounded.

Optional cache key:

```text
public-glossary-annotations:{novel_id}:{chapter_id}:{version_id}:{glossary_revision}
```

If glossary revision is unavailable:

```text
public-glossary-annotations:{novel_id}:{chapter_id}:{version_id}:{public_glossary_hash}
```

Cache invalidation dimensions:

- active translated version ID,
- glossary revision/hash,
- public glossary visibility changes,
- annotation settings,
- reader block rendering version if applicable.

Rules:

- Cache must not outlive public visibility changes.
- Cache must not expose annotations from unpublished or unauthorized state.
- Cache must store only public-safe annotation payloads.

## Frontend Rendering

The public reader should render annotations from `reader_blocks`.

Rendering strategy:

- For each block, collect matches with the same `block_index`.
- Sort matches by `start`.
- Apply non-overlapping ranges.
- Wrap matched text in a semantic element such as `button`, `span`, or `mark`.
- Preserve original text and paragraph structure.
- Do not mutate stored text.
- Do not re-tokenize in a way that changes displayed text.

Accessible behavior:

- Hover shows tooltip on desktop.
- Focus shows tooltip/popover.
- Tap opens popover or sheet on mobile.
- Escape closes tooltip/popover.
- Outside click closes tooltip/popover.
- Keyboard navigation must reach annotated terms.
- Screen reader label should identify the annotation as a glossary note.

Reader toggle:

- Add a control: `Glossary notes`.
- Toggle on/off without reloading the chapter when possible.
- Store preference in local storage if existing reader settings already use local storage.
- If disabled, render plain text.
- If annotations are unavailable, hide or disable the toggle gracefully.

## Security and Privacy

Do not expose:

- glossary review notes,
- decision history,
- rejected terms,
- pending terms,
- candidate terms,
- internal aliases,
- internal definitions,
- glossary diagnostics,
- prompt diagnostics,
- prompt blocks,
- editor QA metadata,
- confidence scores unless explicitly public-safe,
- provider/model metadata,
- internal database IDs when avoidable,
- unpublished glossary entries.

Rules:

- Public glossary selection must use the same publication/access checks as the public chapter endpoint.
- Annotation payloads must be bounded.
- Definitions and aliases must be public-safe.
- Public APIs must not expose admin-only metadata even when annotations are enabled.
- Public annotations must not reveal information for unpublished novels or chapters.

## Migration and Backward Compatibility

- Public chapter response changes are additive.
- Clients ignoring `glossary_annotations` behave as before.
- Disabled annotations return an empty list or omit the field according to existing API style.
- If no public-safe glossary entries exist, return an empty list.
- Existing glossary schema may be used with conservative filtering.
- Optional DB migration may add `public_visible`, `public_definition`, and `public_display_term`.
- If migration is added, default public visibility should be `false`.
- Existing public reader behavior remains compatible.

## Test Design

### Backend Tests

Create or extend public reader tests for:

- approved public-visible term is returned,
- approved but non-public term is not returned,
- pending term is not returned,
- rejected term is not returned,
- internal/admin-only term is not returned,
- display term is matched in reader block,
- public-safe alias is matched,
- Latin substring false positive is avoided,
- overlapping matches resolve deterministically,
- longer match wins over shorter overlapping match,
- match limits are enforced,
- disabled global setting returns empty annotations,
- disabled per-novel setting returns empty annotations,
- chapter shell response returns empty annotations,
- unpublished novel/chapter does not expose annotations,
- public reader response excludes glossary diagnostics,
- public reader response excludes editor QA metadata,
- public reader response excludes prompt metadata,
- existing clients can ignore annotation field.

### Frontend Tests

Add tests for:

- annotations render without changing visible text,
- tooltip/popover shows public definition,
- missing definition still renders gracefully,
- toggle hides annotations,
- toggle restores annotations,
- keyboard focus opens annotation UI,
- Escape closes annotation UI,
- mobile popover/sheet does not clip or overlap badly,
- annotations are not rendered when payload is empty,
- paragraph/block structure is preserved.

## Acceptance Criteria

1. Public chapter response can include `glossary_annotations` when the feature is enabled.
2. Only approved public-safe glossary entries are exposed.
3. Pending, rejected, internal, admin-only, and unpublished glossary data are excluded.
4. Matching finds translated/display terms and avoids obvious substring false positives.
5. Overlapping matches are resolved deterministically.
6. Annotation payloads are bounded.
7. Reader rendering preserves original text and paragraph structure.
8. Reader has a show/hide glossary notes control.
9. Public APIs do not expose glossary diagnostics, editor QA metadata, prompt details, or unpublished glossary data.
10. Existing public reader behavior remains compatible when annotations are disabled or ignored.
11. Focused backend and frontend tests pass.