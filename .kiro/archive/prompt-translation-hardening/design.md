# Design: Prompt and Translation Correctness Hardening

## Overview

All changes are confined to the prompt assembly layer and the metadata that records what each prompt contained. The pipeline architecture, storage topology, provider abstractions, and public API shapes are unchanged. The dependency direction (`api → services → domain → storage/providers`) is preserved throughout.

The work divides into four areas:
1. Template content additions (honorific policy, anti-hallucination rules, glossary authority, prompt version constant)
2. Builder logic changes (conflict resolution, style preset in system prompt, honorific policy parameter threading)
3. Glossary injection rendering change (locked vs. advisory sub-sections)
4. Metadata persistence change (prompt version + glossary hash into chunk state and translated chapter artifact)

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/prompts/templates.py` | Add `PROMPT_TEMPLATE_VERSION`, honorific policy blocks, system-level style suffix templates, strengthen existing system prompt copy |
| `backend/src/novelai/prompts/builders.py` | Thread `honorific_policy` parameter, add style preset to system prompt builder, add runtime/DB glossary conflict suppression |
| `backend/src/novelai/prompts/models.py` | Add `prompt_template_version`, `honorific_policy`, `conflict_warnings` fields to `TranslationRequest` |
| `backend/src/novelai/services/glossary_prompt_injection.py` | Split rendered block into locked/advisory sub-sections; add `locked_term_count` to `PromptGlossaryBlock` |
| `backend/src/novelai/translation/pipeline/stages/translate.py` | Read `honorific_policy` from `context.metadata`; pass to builder; write `prompt_template_version` + `glossary_hash` to chunk metadata |
| `backend/src/novelai/storage/translations.py` | Persist `prompt_template_version` and `glossary_hash` into translated chapter artifact |
| `backend/src/novelai/config/workflow_profiles.py` | Add `workflow_defaults` section with `style_preset`, `consistency_mode`, `honorific_policy` |
| `backend/src/novelai/api/routers/library.py` (admin chapter detail) | Expose `prompt_template_version` and `glossary_hash` in admin chapter response |
| `backend/tests/test_prompt_templates.py` | New — snapshot and regression tests |

### Files Not Touched

- `api/routers/public.py` — public reader response unchanged
- `translation/pipeline/stages/translation_qa.py` — QA stage unchanged
- `services/orchestration/` — orchestration flow unchanged
- `storage/glossary.py`, `storage/chapters.py` — raw chapter storage unchanged
- Any migration files — no DB schema change

## Component Design

### 1. `templates.py` Changes

#### `PROMPT_TEMPLATE_VERSION`
```python
PROMPT_TEMPLATE_VERSION: str = "v2"
```
Increment this string whenever any template that affects model output changes. Callers must not hard-code this value.

#### Strengthened `MULTILINGUAL_SYSTEM_PROMPT_TEMPLATE`

Add to the "Core rules" section (after existing marker rules):
```
- Never invent names, subjects, motives, scene details, or any content absent from the source text.
- When Japanese omits a subject and English requires one, resolve from immediate context only. If ambiguous, use the least committal natural phrasing rather than inventing an actor.
- If a source term is untranslatable or unknown, preserve the original source-language spelling verbatim rather than guessing.
- When a glossary is provided, it is authoritative. Use glossary translations exactly for listed terms regardless of your training-time knowledge.
- Follow the honorific/title policy specified in the request.
```

Apply equivalent additions to `JSON_SYSTEM_PROMPT_TEMPLATE`.

#### `HONORIFIC_POLICY_BLOCKS`
```python
HONORIFIC_POLICY_BLOCKS: dict[str, str] = {
    "retain": (
        "Honorific policy: RETAIN. "
        "Keep Japanese honorific suffixes (san, kun, sama, chan, senpai, sensei, etc.) "
        "attached to names in the output exactly as they appear in the source."
    ),
    "translate": (
        "Honorific policy: TRANSLATE. "
        "Render Japanese honorific suffixes as natural English equivalents appropriate to "
        "the character's relationship and social register. Do not keep raw Japanese suffixes."
    ),
    "omit": (
        "Honorific policy: OMIT. "
        "Drop Japanese honorific suffixes from names silently. "
        "Use the bare name or appropriate English title."
    ),
}
```

#### `STYLE_PRESET_SYSTEM_SUFFIX_TEMPLATES`
```python
STYLE_PRESET_SYSTEM_SUFFIX_TEMPLATES: dict[str, str] = {
    "fantasy": "Genre context: fantasy fiction. Treat magical systems, races, noble ranks, place names, and invented terms as high-priority glossary items even when not explicitly listed.",
    "romance": "Genre context: romance fiction. Emotional nuance, hesitation, subtext, and relationship dynamics carry primary meaning — preserve them over any other naturalness optimization.",
    "action": "Genre context: action fiction. Maintain pacing, spatial clarity, and physical impact. Do not flatten kinetic sequences.",
    "comedy": "Genre context: comedy fiction. Comedic timing, punchlines, and playful narration are load-bearing. Preserve them even when it requires a less literal rendering.",
}
```

#### Glossary Authority Statement
Add to `DEFAULT_USER_PROMPT_TEMPLATE` and `STRONG_CONSISTENCY_USER_PROMPT_TEMPLATE` immediately before `{additional_instructions}`:
```
- When a glossary is provided below, treat it as authoritative. Use the listed translations exactly when the source term appears, overriding your general knowledge of that term.
```
This must also appear in `JSON_USER_PROMPT_TEMPLATE`.

### 2. `builders.py` Changes

#### `build_system_prompt` and `build_json_system_prompt`

Accept optional `style_preset: str | None = None`. When supplied and valid, append the corresponding `STYLE_PRESET_SYSTEM_SUFFIX_TEMPLATES` entry as a new paragraph after the existing system prompt body.

```python
def build_system_prompt(
    source_language: str,
    target_language: str,
    style_preset: str | None = None,
) -> str:
    base = MULTILINGUAL_SYSTEM_PROMPT_TEMPLATE.format(...)
    suffix = _system_style_suffix(style_preset)
    return f"{base}\n\n{suffix}" if suffix else base
```

#### `_format_additional_instructions` — Conflict Resolution

Before assembling blocks, cross-check `glossary_entries` (runtime channel) against `prompt_glossary_block` (DB channel):

```python
def _format_additional_instructions(
    *,
    glossary_entries=None,
    prompt_glossary_block=None,
    style_preset=None,
    target_language,
    json_output=False,
    consistency_mode=False,
    honorific_policy=None,
) -> tuple[str, list[str]]:  # returns (assembled_string, conflict_warnings)
```

Conflict detection logic:
1. Parse term keys from `prompt_glossary_block` string (scan for lines matching `- {term} =>` or `- {term} =`).
2. For each entry in `glossary_entries`, if its `.source` key appears in the DB block term set with a different `.target`, suppress that entry from `glossary_entries` and record `"runtime_glossary_conflict_suppressed:{term}"` in `conflict_warnings`.
3. DB block always wins.

The return type changes to a `(str, list[str])` tuple. Callers that currently call `_format_additional_instructions` must unpack accordingly. Since this is a private function, the impact is limited to `builders.py` itself.

The honorific policy block is appended after the glossary authority statement and before the style block:
```
order: [glossary_authority_statement] [prompt_glossary_block] [filtered_glossary_entries] [honorific_policy_block] [style_block] [json_consistency_block]
```

#### `build_translation_request` Changes

```python
def build_translation_request(
    *,
    text,
    source_language,
    target_language,
    glossary_entries=None,
    prompt_glossary_block=None,
    style_preset=None,
    consistency_mode=False,
    json_output=False,
    honorific_policy=None,      # NEW
) -> TranslationRequest:
```

Pass `honorific_policy` and `style_preset` to both system prompt builders and user prompt builders. Populate `TranslationRequest.honorific_policy` and `TranslationRequest.prompt_template_version` from `PROMPT_TEMPLATE_VERSION`.

### 3. `glossary_prompt_injection.py` Changes

#### `PromptGlossaryBlock` — New Field

```python
@dataclass(frozen=True)
class PromptGlossaryBlock:
    rendered_text: str
    included_terms: tuple[PromptGlossaryTerm, ...]
    skipped_terms: tuple[SkippedGlossaryTerm, ...]
    warnings: tuple[str, ...]
    conflict_warnings: tuple[str, ...]
    empty: bool
    truncated: bool
    locked_term_count: int = 0    # NEW
```

#### `_render_text` — Split into Locked and Advisory Sub-sections

Current behavior: single flat list under "Use these approved translations consistently:".

New behavior:
```
GLOSSARY FOR THIS NOVEL
These are owner-approved translation rules. They are authoritative — use them exactly when the source term appears, overriding your general knowledge.

LOCKED (mandatory — do not deviate):
- {term} => {translation}
...

APPROVED (use consistently):
- {term} => {translation}
...

Avoid these rejected variants:
- {term}: avoid "{variant}"
...
```

Rules:
- "LOCKED" section appears only when at least one `owner_locked=True` term is included.
- "APPROVED" section appears only when at least one `owner_locked=False` term is included.
- "Avoid" section is unchanged — still appears only when avoid_variants exist.
- `locked_term_count` is set to the count of included terms where `owner_locked=True`.

### 4. `models.py` Changes

```python
@dataclass(frozen=True)
class TranslationRequest:
    source_language: str
    target_language: str
    text: str
    system_prompt: str
    user_prompt: str
    glossary_entries: tuple[GlossaryTerm, ...]
    prompt_glossary_block: str | None
    style_preset: str | None
    consistency_mode: bool
    json_output: bool
    honorific_policy: str | None = None           # NEW
    prompt_template_version: str = ""             # NEW
    runtime_glossary_conflict_warnings: tuple[str, ...] = ()  # NEW
```

### 5. `translate.py` (TranslateStage) Changes

#### Reading `honorific_policy`

In `_build_prompt_request`:
```python
honorific_policy = context.metadata.get("honorific_policy")
return build_translation_request(
    ...,
    honorific_policy=honorific_policy if isinstance(honorific_policy, str) else None,
)
```

#### Writing Audit Metadata Per Chunk

In `_record_prompt_glossary_metadata`, also record:
```python
records[-1]["prompt_template_version"] = PROMPT_TEMPLATE_VERSION
```

In `worker()`, after building the request, record `prompt_template_version` in `context.metadata["prompt_template_version"]` (overwrite each chunk — value is constant for the run).

### 6. `storage/translations.py` Changes

When writing the translated chapter JSON artifact, include:
```python
artifact["prompt_template_version"] = context.metadata.get("prompt_template_version", "")
artifact["glossary_hash"] = context.metadata.get("glossary_hash_final", "")  # or per-chunk hash if single-chunk
```

These fields must be written on every save, defaulting to empty string if absent (backward-compatible).

### 7. `workflow_profiles.py` Changes

```python
WORKFLOW_DEFAULTS_FIELDS = ("style_preset", "consistency_mode", "honorific_policy")

def default_workflow_defaults() -> dict[str, Any]:
    return {
        "style_preset": None,
        "consistency_mode": False,
        "honorific_policy": None,
    }

def normalize_workflow_profiles(value: Any) -> dict[str, Any]:
    result = {
        "steps": normalize_workflow_steps(value),        # existing logic renamed
        "defaults": normalize_workflow_defaults(value),  # new
    }
    return result
```

`normalize_workflow_defaults` validates `style_preset` against `STYLE_PRESET_TEMPLATES` keys (or `None`), `consistency_mode` as bool, `honorific_policy` against `HONORIFIC_POLICY_BLOCKS` keys (or `None`).

The translate orchestration path reads `profile["defaults"]` and uses them as fallbacks for `context.metadata` fields that are not already set.

### 8. Admin Chapter Detail API Change

The admin library chapter detail response (in `api/routers/library.py`) must include two new optional fields when loading a translated chapter artifact:
```json
{
  "prompt_template_version": "v2",
  "glossary_hash": "abc123..."
}
```

These are read from the translated chapter artifact and passed through. If absent (legacy artifacts), return `null`.

## Cache Key Invalidation

The existing cache key must include `prompt_template_version`. The audit confirms the reference doc already lists prompt version as a required cache key component. The implementation must verify that `TranslationCache.build_key(...)` (or equivalent) includes `prompt_template_version` as a parameter. If it does not, add it.

Cache invalidation triggers after this spec:
- Template version bump (`PROMPT_TEMPLATE_VERSION` changes)
- Glossary hash change (already implemented)
- Style preset change (already included per audit)
- Consistency mode change (already included per audit)
- Honorific policy change (must be added)

## Test Design

### `tests/test_prompt_templates.py`

**Snapshot tests** — assert exact rendered string for each template:
- `test_system_prompt_no_style` — baseline system prompt
- `test_system_prompt_with_fantasy_style` — system prompt + fantasy suffix
- `test_system_prompt_with_romance_style`
- `test_json_system_prompt_no_style`
- `test_json_system_prompt_with_action_style`
- `test_user_prompt_no_glossary_no_honorific`
- `test_user_prompt_with_locked_glossary_retain_honorific`
- `test_user_prompt_with_advisory_glossary_translate_honorific`
- `test_user_prompt_with_mixed_locked_advisory_glossary`
- `test_json_user_prompt_with_glossary_consistency`
- `test_strong_consistency_user_prompt`

**Conflict suppression tests:**
- `test_no_conflict` — runtime term not in DB block → both appear
- `test_single_conflict_db_wins` — same source term, different target → runtime suppressed, warning emitted
- `test_multiple_conflicts_all_suppressed`

**Honorific policy tests:**
- `test_honorific_retain_block_rendered`
- `test_honorific_translate_block_rendered`
- `test_honorific_omit_block_rendered`
- `test_honorific_none_no_block`

**Glossary lock rendering tests:**
- `test_locked_terms_produce_mandatory_section`
- `test_advisory_terms_produce_advisory_section`
- `test_mixed_terms_both_sections`
- `test_no_locked_terms_no_locked_section_header`
- `test_locked_term_count_field`

**Cache key tests (in existing cache test file or new):**
- `test_cache_key_changes_on_template_version_bump`
- `test_cache_key_changes_on_honorific_policy_change`
- `test_cache_key_stable_when_no_inputs_change`

## Migration and Backward Compatibility

- `TranslationRequest` new fields are all optional with sensible defaults — no call site breaks.
- `PromptGlossaryBlock` new `locked_term_count` field has a default of `0` — no call site breaks.
- `_format_additional_instructions` return type changes from `str` to `tuple[str, list[str]]`. This is a private function; all callers are in `builders.py` and must be updated in the same commit.
- Translated chapter artifacts gain two new fields. Readers that do not expect them are unaffected (JSON dict). Admin API must handle absent fields gracefully (return `null`).
- Workflow profile structure gains a `"defaults"` key. Existing stored profiles that do not have it will get the default values from `normalize_workflow_profiles`. No migration needed.
- Cache keys that do not yet include `prompt_template_version` will miss on first use after the change. This is intentional and correct — stale translations without version metadata should not be served indefinitely.

## Acceptance Criteria

1. Every translated chapter artifact includes `prompt_template_version` and `glossary_hash` fields after this change.
2. A prompt built with `honorific_policy="retain"` contains the retain instruction; one built with `honorific_policy="omit"` contains the omit instruction; one built without a policy contains neither.
3. A glossary block with one locked and two advisory terms renders with a "LOCKED" sub-section and an "APPROVED" sub-section; a block with only advisory terms renders with no "LOCKED" heading.
4. When the runtime glossary list contains a term also in the DB block with a different translation, the DB block translation is used and a conflict warning is recorded; the runtime term does not appear in the prompt.
5. Changing `PROMPT_TEMPLATE_VERSION` in `templates.py` causes all cache lookups for prior runs to miss.
6. All snapshot tests pass without modification after the initial commit.
7. `workflow_profiles.normalize_workflow_profiles` accepts `style_preset`, `consistency_mode`, and `honorific_policy` under a `workflow_defaults` key and returns them validated.
