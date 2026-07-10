# design.md

# Design: Glossary Diagnostics Pipeline Wiring

## Overview

`glossary-diagnostics-pipeline-wiring` connects glossary diagnostic normalization into the translation pipeline.

The codebase already has or plans to have `normalize_glossary_diagnostics()`, but the diagnostics are not yet consistently wired into `TranslateStage` or surfaced through activity metadata. This spec ensures glossary usage issues, term conflicts, missing glossary matches, alias handling problems, and prompt/translation diagnostic signals are normalized and persisted during translation.

This is follow-up technical debt and important before scale because glossary problems can silently reduce translation quality. Operators need visibility into glossary coverage and failures per translation activity.

## Goals

* Wire `normalize_glossary_diagnostics()` into `TranslateStage`.
* Capture glossary diagnostics during translation.
* Normalize diagnostic output into a stable schema.
* Aggregate diagnostics into activity metadata.
* Preserve existing translation behavior.
* Avoid failing translations because diagnostics are missing or malformed.
* Add tests for diagnostic normalization, pipeline wiring, aggregation, and metadata persistence.

## Non-goals

* No glossary UI redesign.
* No glossary editor changes.
* No new glossary matching algorithm unless required to expose diagnostics.
* No translation invalidation behavior. That belongs to `glossary-revision-translation-invalidation`.
* No public reader annotation wiring. That belongs to `public-reader-glossary-annotations-wiring`.
* No frontend tooltip rendering. That belongs to `frontend-glossary-annotation-rendering`.
* No prompt policy rewrite. That belongs to `jp-en-prompt-quality-policy`.

## Current problem

The translation pipeline may already collect partial glossary-related signals, such as:

```text id="y264s4"
matched terms
missed terms
alias matches
conflicting glossary entries
diagnostic warnings
prompt glossary section stats
model output glossary violations
```

However, these signals are not consistently:

```text id="0w1evk"
normalized
attached to TranslateStage output
aggregated across chapters/batches
persisted into activity metadata
available for diagnostics/operations
covered by tests
```

## Proposed architecture

Recommended components:

```text id="mi9xij"
TranslateStage
GlossaryService / GlossaryMatcher
normalize_glossary_diagnostics()
GlossaryDiagnosticsAggregator
ActivityQueueService / activity metadata patch path
Translation activity worker/orchestrator
```

High-level flow:

```text id="rdn34y"
1. Translation activity starts.
2. TranslateStage receives source text, glossary context, and translation settings.
3. Glossary service/matcher produces raw glossary diagnostic data.
4. TranslateStage calls normalize_glossary_diagnostics(raw_diagnostics).
5. TranslateStage returns translated text plus normalized glossary diagnostics.
6. Worker/orchestrator aggregates diagnostics across chapters or batches.
7. Activity metadata is patched with metadata.glossary_diagnostics.
8. Activity detail/status APIs expose the metadata through existing activity response shape.
```

## Diagnostic schema

Normalized diagnostics should be stable and safe.

Recommended normalized shape:

```json id="tx9tgv"
{
  "summary": {
    "terms_available": 120,
    "terms_considered": 32,
    "terms_matched": 18,
    "aliases_matched": 7,
    "terms_applied": 16,
    "terms_missed": 2,
    "conflicts": 1,
    "warnings": 3
  },
  "warnings": [
    {
      "code": "glossary_conflict",
      "severity": "warning",
      "message": "Multiple glossary entries matched the same source span",
      "term_id": "term_123",
      "source_term": "王都",
      "chapter_id": "chapter_456"
    }
  ],
  "term_events": [
    {
      "term_id": "term_123",
      "source_term": "王都",
      "display_term": "Royal Capital",
      "event": "applied",
      "match_type": "exact",
      "alias": null,
      "chapter_id": "chapter_456"
    }
  ]
}
```

Recommended top-level fields:

```text id="77k1ex"
summary
warnings
term_events
chapters
raw_count
normalized_at
version
```

## Activity metadata shape

Persist diagnostics under:

```text id="lt4zqj"
metadata.glossary_diagnostics
```

Recommended activity metadata:

```json id="j1yink"
{
  "glossary_diagnostics": {
    "version": 1,
    "summary": {
      "chapters_processed": 10,
      "terms_available": 120,
      "terms_considered": 55,
      "terms_matched": 30,
      "aliases_matched": 12,
      "terms_applied": 28,
      "terms_missed": 4,
      "conflicts": 2,
      "warnings": 5,
      "chapters_with_warnings": 3
    },
    "top_warnings": [
      {
        "code": "glossary_conflict",
        "count": 2,
        "severity": "warning"
      }
    ],
    "chapter_summaries": [
      {
        "chapter_id": "chapter_456",
        "terms_matched": 4,
        "terms_applied": 4,
        "warnings": 0,
        "conflicts": 0
      }
    ],
    "updated_at": "2026-07-10T00:00:00Z"
  }
}
```

The metadata should avoid becoming too large. Store full per-term details only if bounded. Prefer summaries and top warnings for activity metadata.

## Normalization rules

`normalize_glossary_diagnostics()` should accept inconsistent or partial raw diagnostic input and return a safe normalized structure.

Rules:

```text id="id84qi"
missing diagnostics -> empty normalized diagnostics
unknown fields -> ignored or stored only in safe metadata
invalid counts -> coerced to zero or omitted
unknown warning code -> unknown
unknown severity -> info
missing term_id -> null
missing source_term -> null
duplicate events -> deduplicated when possible
large arrays -> truncated to configured limits
unsafe strings -> sanitized/redacted
```

Recommended severity values:

```text id="5nbn2x"
info
warning
error
```

Recommended event values:

```text id="lac6j6"
available
considered
matched
alias_matched
applied
missed
conflict
ignored
```

Recommended warning codes:

```text id="zfb2b4"
glossary_conflict
missing_required_term
alias_ambiguous
term_not_applied
term_missing_definition
term_inactive
term_not_approved
prompt_glossary_truncated
model_output_violation
diagnostics_malformed
unknown
```

## TranslateStage integration

`TranslateStage` should call normalization after raw diagnostics are collected and before returning its result.

Recommended stage result shape:

```json id="m93qy7"
{
  "translated_text": "...",
  "metadata": {
    "glossary_diagnostics": {
      "summary": {},
      "warnings": [],
      "term_events": []
    }
  }
}
```

If existing stage output has a different structure, adapt without breaking current consumers.

Translation should not fail solely because diagnostics cannot be normalized. Instead:

```text id="57ks8b"
log safe warning
attach diagnostics_malformed warning
continue translation result
```

Only fail the translation if the existing translation logic would already fail.

## Aggregation design

Add a small aggregator for chapter/batch-level diagnostics.

Recommended component:

```text id="d5dvwv"
GlossaryDiagnosticsAggregator
```

Responsibilities:

```text id="c775u9"
merge summary counters
count warning codes
count chapters with warnings
create bounded chapter summaries
track top warning categories
truncate large warning/event lists
produce activity metadata patch
```

Recommended limits:

```text id="6dmeax"
GLOSSARY_DIAGNOSTICS_MAX_WARNINGS=50
GLOSSARY_DIAGNOSTICS_MAX_TERM_EVENTS=100
GLOSSARY_DIAGNOSTICS_MAX_CHAPTER_SUMMARIES=200
GLOSSARY_DIAGNOSTICS_MAX_METADATA_BYTES=65536
```

If metadata exceeds limits, the aggregator should truncate details and record:

```json id="l5rvld"
{
  "truncated": true,
  "truncation_reason": "metadata_size_limit"
}
```

## Activity metadata persistence

Use the existing activity metadata patch/update path where possible.

Recommended patch location:

```text id="2q7r6n"
metadata.glossary_diagnostics
```

Persistence timing:

```text id="bis1cs"
after each chapter or batch if progress metadata already updates frequently
at activity completion if no safe incremental patch path exists
on activity failure if partial diagnostics exist
```

Metadata updates should be safe:

```text id="37xjm7"
diagnostic persistence failure should not corrupt translation output
metadata patch should merge with existing metadata
progress metadata should be preserved
crawl_result metadata should be preserved
other diagnostic metadata should be preserved
```

If activity metadata patching fails, log a safe warning and continue unless the activity system requires metadata writes to succeed.

## Error handling

Diagnostic wiring should be resilient.

Expected behavior:

```text id="vdau9y"
raw diagnostics missing -> empty diagnostics
normalizer throws -> attach diagnostics_malformed warning and continue
aggregator throws -> log warning and continue translation
metadata patch fails -> log warning and continue translation if translation already succeeded
malformed term event -> omit or normalize as unknown
```

## API exposure

No new endpoint is required.

Activity detail/status APIs should naturally expose `metadata.glossary_diagnostics` if they already expose activity metadata.

If response models whitelist metadata fields, update them to include:

```text id="r46loc"
metadata.glossary_diagnostics
```

Do not expose raw prompt text, raw model output, API keys, provider errors with secrets, or private unpublished glossary data beyond what admins/activity owners are already allowed to see.

## Security and privacy

Diagnostics may include source terms, translated terms, chapter IDs, and warning messages. Treat them as operational metadata.

Rules:

```text id="1m7u4r"
do not include provider API keys
do not include raw prompts
do not include full source chapter text
do not include full translated chapter text
do not include private user data unrelated to diagnostics
truncate long strings
respect existing activity authorization
```

## Observability

Add structured logs for diagnostic pipeline events:

```text id="64efah"
glossary_diagnostics.normalized
glossary_diagnostics.malformed
glossary_diagnostics.aggregated
glossary_diagnostics.persisted
glossary_diagnostics.persistence_failed
```

Suggested safe log fields:

```text id="tltfx2"
activity_id
novel_id
chapter_id
warnings_count
conflicts_count
terms_matched
terms_applied
truncated
```

## Testing strategy

Tests should cover:

```text id="n7vpip"
normalizer empty input
normalizer malformed input
normalizer valid input
warning code normalization
severity normalization
event normalization
TranslateStage calls normalizer
TranslateStage preserves translation output
aggregator merges multiple chapter diagnostics
aggregator truncates large lists
activity metadata patch merges with existing metadata
metadata persists on success
partial diagnostics persist on failure when available
metadata write failure does not fail translation
API response includes metadata if whitelisted
```

## Rollout plan

1. Inspect existing diagnostic helper and translation stage output shape.
2. Stabilize normalized diagnostic schema.
3. Add/adjust `normalize_glossary_diagnostics()`.
4. Wire normalizer into `TranslateStage`.
5. Add aggregator.
6. Patch activity metadata during/after translation.
7. Update activity response models if needed.
8. Add redaction/truncation.
9. Add tests.
10. Verify:

    * translation still succeeds without diagnostics.
    * diagnostics appear in activity metadata.
    * malformed diagnostics do not fail translation.
    * metadata size remains bounded.
