# design.md

# Design: Public Reader Glossary Annotations Wiring

## Overview

`public-reader-glossary-annotations-wiring` connects public glossary annotation lookup to the public chapter reader API.

The backend already has or plans to have `PublicGlossaryAnnotationsService.find_annotations()`, but the public chapter API does not yet call it or expose the result. This spec wires the service into public chapter retrieval and adds a safe `glossary_annotations` response field.

This is follow-up feature wiring, not a V1 launch blocker. It enables later frontend rendering work, such as highlights and tooltips, without requiring the frontend implementation in this spec.

## Goals

* Call `PublicGlossaryAnnotationsService.find_annotations()` from the public chapter API.
* Add `glossary_annotations` to the public chapter response.
* Ensure only safe, public, approved glossary data is exposed.
* Preserve existing chapter response fields and reader behavior.
* Support both plain text and `reader_blocks` rendering modes if both exist.
* Add backend tests for annotation visibility, response shape, ordering, and disabled/private cases.

## Non-goals

* No frontend tooltip/highlight rendering. That belongs to `frontend-glossary-annotation-rendering`.
* No global/per-novel annotation setting unless already implemented. That belongs to `public-glossary-annotations-setting`.
* No glossary editor changes.
* No public glossary management UI.
* No annotation caching redesign unless required for performance.
* No new glossary matching algorithm unless the service is incomplete.
* No annotation invalidation rules beyond existing glossary/chapter cache behavior.

## Public API change

Add this field to public chapter API responses:

```json id="ckn28l"
{
  "glossary_annotations": []
}
```

Recommended annotation object:

```json id="4e9w6i"
{
  "annotation_id": "ann_001",
  "term_id": "term_123",
  "source_term": "王都",
  "display_term": "Royal Capital",
  "definition": "The royal capital city.",
  "start_offset": 128,
  "end_offset": 130,
  "match_text": "王都",
  "match_type": "exact",
  "confidence": 1.0
}
```

If the reader uses block-based rendering, include block position:

```json id="kq6m5p"
{
  "annotation_id": "ann_001",
  "term_id": "term_123",
  "source_term": "王都",
  "display_term": "Royal Capital",
  "definition": "The royal capital city.",
  "block_id": "block_5",
  "block_index": 4,
  "start_offset": 16,
  "end_offset": 18,
  "match_text": "王都",
  "match_type": "exact"
}
```

The final response shape should match existing reader text structure. If both full-text offsets and block offsets are available, include both only if safe and useful.

## Recommended response contract

Top-level field:

```text id="kcoxzv"
glossary_annotations: PublicGlossaryAnnotation[]
```

Recommended fields:

```text id="9hypdk"
annotation_id
term_id
source_term
display_term
definition
match_text
match_type
start_offset
end_offset
block_id
block_index
confidence
```

Required fields for V1 wiring:

```text id="qfp5bs"
term_id
display_term
start_offset or block offset
end_offset or block offset
match_text
match_type
```

Optional fields:

```text id="1y8b15"
annotation_id
source_term
definition
block_id
block_index
confidence
aliases
```

Do not expose internal-only fields, moderation metadata, private notes, prompt-only glossary hints, inactive aliases, or unpublished glossary terms.

## Visibility and safety rules

Only public-safe terms may be exposed.

Recommended visibility filters:

```text id="36wot6"
term is approved
term is active
term belongs to the public novel/chapter context
term is not private/internal-only
term definition is public-safe
alias/source term is allowed for public display
novel is published
chapter is published
```

If the glossary model has fields such as `status`, `visibility`, `approved_at`, `is_active`, or `public_enabled`, the service should use them.

If visibility metadata is incomplete, the API should prefer hiding annotations rather than leaking unsafe terms.

## Backend integration point

The public chapter API likely already performs:

```text id="vxgqm3"
1. Resolve public novel/chapter.
2. Check publication/availability.
3. Load translated chapter text and/or reader blocks.
4. Return reader response.
```

Add:

```text id="ugj7g1"
5. Call PublicGlossaryAnnotationsService.find_annotations(...)
6. Attach result as glossary_annotations.
```

Recommended call shape:

```python id="w355pd"
annotations = public_glossary_annotations_service.find_annotations(
    novel_id=novel.id,
    chapter_id=chapter.id,
    text=chapter_text,
    reader_blocks=reader_blocks,
    language_pair=language_pair,
)
```

Adapt parameters to existing service signature.

## Handling `text` and `reader_blocks`

If the public reader response includes plain `text`, annotations may use full-text offsets.

If the response includes `reader_blocks`, annotations should ideally use block-relative offsets.

Supported modes:

```text id="gysu8a"
text_only
reader_blocks_only
text_and_reader_blocks
```

Recommended behavior:

### Text-only

Return annotations with:

```text id="b1xmav"
start_offset
end_offset
```

Offsets are relative to the returned text.

### Reader-blocks-only

Return annotations with:

```text id="eiydk3"
block_index
block_id if available
start_offset
end_offset
```

Offsets are relative to the block text.

### Text and reader blocks

Prefer block-relative offsets for frontend rendering. Full-text offsets may be included if already available and consistent.

## Ordering and overlap behavior

Annotations should be deterministic.

Recommended ordering:

```text id="hxrge7"
block_index ascending
start_offset ascending
longer match first for same start
term priority if available
term_id ascending as final tie-breaker
```

Overlap policy should be owned by `PublicGlossaryAnnotationsService`.

Recommended policy:

```text id="xiihme"
prefer longest match
avoid overlapping annotations by default
allow nested/overlapping only if service explicitly supports it
```

The public API should not reimplement complex matching if the service already returns normalized annotations.

## Feature gating

This spec should not build the global/per-novel setting from scratch. That belongs to `public-glossary-annotations-setting`.

However, if settings already exist, this wiring must respect them.

Recommended behavior:

```text id="qcx2c4"
if global public annotations setting exists and is false -> return []
if per-novel public annotations setting exists and is false -> return []
if no setting exists yet -> return annotations according to service visibility rules
```

## Error handling

Annotation lookup should not break public chapter reading.

Expected behavior:

```text id="0w1txl"
service succeeds -> include annotations
service returns no matches -> include []
service unavailable/fails -> log safe warning and include []
malformed annotations -> filter invalid records and include valid records
chapter not published -> existing not-found/unavailable behavior
```

Public reader should remain available even if annotation generation fails.

## Performance

Annotation lookup should be bounded.

Recommended constraints:

```text id="zwac5w"
limit maximum annotations per chapter
avoid full glossary scan if indexed lookup exists
reuse existing chapter/glossary cache if available
avoid N+1 queries for term definitions/aliases
```

Recommended config:

```text id="1qof7i"
PUBLIC_GLOSSARY_ANNOTATIONS_MAX_PER_CHAPTER=500
PUBLIC_GLOSSARY_ANNOTATIONS_TIMEOUT_MS=500
```

If lookup exceeds limits, return a truncated safe list and log a warning. Optionally include admin-only diagnostics elsewhere, but do not expose internal performance details in public reader response.

## Response model compatibility

The new field must be additive.

Rules:

```text id="7adjo6"
old clients can ignore glossary_annotations
field defaults to []
do not remove or rename existing response fields
do not change text/reader_blocks shape
do not require frontend changes for reader to keep working
```

## Security and privacy

Public annotation responses must not leak private glossary information.

Never expose:

```text id="dmpj60"
private glossary notes
admin-only comments
term approval/moderation metadata
inactive or rejected terms
draft/unpublished glossary entries
raw prompt instructions
raw model diagnostics
user private data
internal source URLs if not already public
```

Allowed public-safe fields:

```text id="n8x7zj"
public term ID
public source/display term if allowed
public definition if approved
match offsets
match text from already-visible chapter content
match type
```

## Testing strategy

Backend tests should cover:

```text id="h4s0td"
public chapter response includes glossary_annotations
no annotations returns []
annotation service is called with correct novel/chapter/text context
unpublished chapter does not expose annotations
unpublished novel does not expose annotations
inactive term is hidden
unapproved term is hidden
private/internal term is hidden
alias visibility rules
offsets are valid for text mode
offsets are valid for reader_blocks mode
annotation failure does not fail chapter API
response model remains backward compatible
feature setting respected if already implemented
```

## Rollout plan

1. Inspect public chapter API response shape.
2. Inspect `PublicGlossaryAnnotationsService.find_annotations()` signature and output.
3. Define public annotation response model.
4. Wire service call into public chapter endpoint.
5. Add visibility/safety filtering if not already guaranteed by service.
6. Add response field defaulting to `[]`.
7. Add error isolation and safe logging.
8. Add tests.
9. Verify:

   * public chapter still loads without frontend changes.
   * annotations appear for approved active terms.
   * unsafe terms are hidden.
   * service failure returns chapter with empty annotations.
